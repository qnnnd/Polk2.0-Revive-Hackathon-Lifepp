"""
Life++ API — Marketplace Endpoints
Global task listing, acceptance, completion. Revive chain integration (13.4).
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.v1.deps import CurrentUser

logger = logging.getLogger(__name__)
from app.db.session import DBSession
from app.models.models import Agent, AgentReputation, ReputationEvent, Task, TaskListing, User
from app.schemas.schemas import TaskListingCreate, TaskListingResponse
from app.services import chain_service

COG_DECIMALS = 18


def _reward_to_wei(reward_cog: float) -> int:
    return int(Decimal(str(reward_cog)) * (10**COG_DECIMALS))


router = APIRouter(prefix="/tasks", tags=["Marketplace"])


@router.post("", response_model=TaskListingResponse, status_code=status.HTTP_201_CREATED)
async def publish_task(payload: TaskListingCreate, db: DBSession, user: CurrentUser):
    agents_q = select(Agent).where(Agent.owner_id == user.id).limit(1)
    result = await db.execute(agents_q)
    poster_agent = result.scalar_one_or_none()
    if not poster_agent:
        raise HTTPException(status_code=400, detail="You need at least one agent to publish tasks")

    listing = TaskListing(
        poster_agent_id=poster_agent.id,
        title=payload.title,
        description=payload.description,
        required_capabilities=payload.required_capabilities,
        reward_cog=payload.reward_cog,
        status="open",
        deadline_at=payload.deadline_at,
    )
    db.add(listing)
    await db.flush()

    # Revive: create task on chain (escrow COG)
    reward_wei = _reward_to_wei(payload.reward_cog)
    if reward_wei > 0:
        balance_wei = await asyncio.to_thread(chain_service.deployer_cog_balance_wei)
        if balance_wei is None:
            raise HTTPException(
                status_code=503,
                detail="Cannot check deployer COG balance (Revive RPC or config unavailable).",
            )
        if balance_wei < reward_wei:
            balance_cog = float(balance_wei) / (10**COG_DECIMALS)
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient COG for reward. Deployer balance: {balance_cog:.2f} COG; "
                    f"required: {payload.reward_cog} COG. Top up deployer COG or reduce the task reward."
                ),
            )
        logger.info("publish_task: creating on chain listing_id=%s reward_wei=%s", listing.id, reward_wei)
        chain_result = await asyncio.to_thread(
            chain_service.create_task_on_chain,
            str(poster_agent.id),
            payload.title,
            reward_wei,
        )
        if chain_result:
            chain_task_id, tx_hash = chain_result
            listing.chain_task_id = chain_task_id
            listing.tx_hash = tx_hash
            db.add(listing)
            await db.flush()
            logger.info("publish_task: chain created listing_id=%s chain_task_id=%s tx_hash=%s", listing.id, chain_task_id, tx_hash)
        else:
            logger.warning("publish_task: chain create failed (listing has no chain_task_id); check chain_service logs. listing_id=%s", listing.id)
    else:
        logger.info("publish_task: reward_wei=0, skipping chain. listing_id=%s", listing.id)

    await db.refresh(listing)
    return listing


@router.get("", response_model=List[TaskListingResponse])
async def list_marketplace_tasks(
    db: DBSession,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    q = select(TaskListing)
    if status_filter:
        q = q.where(TaskListing.status == status_filter)
    q = q.order_by(TaskListing.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.post("/{listing_id}/cancel", response_model=TaskListingResponse)
async def cancel_listing(listing_id: uuid.UUID, db: DBSession, user: CurrentUser):
    """Cancel a listing you published. Only allowed when status is 'open'."""
    listing = (await db.execute(select(TaskListing).where(TaskListing.id == listing_id))).scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.status != "open":
        raise HTTPException(status_code=400, detail=f"Cannot cancel listing with status {listing.status}")
    poster = (await db.execute(select(Agent).where(Agent.id == listing.poster_agent_id))).scalar_one_or_none()
    if not poster or poster.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the publisher can cancel this listing")
    listing.status = "cancelled"
    db.add(listing)
    await db.flush()
    await db.refresh(listing)
    return listing


@router.post("/{listing_id}/accept", response_model=TaskListingResponse)
async def accept_task(
    listing_id: uuid.UUID, db: DBSession, user: CurrentUser, agent_id: uuid.UUID = Query(...),
):
    listing = (await db.execute(select(TaskListing).where(TaskListing.id == listing_id))).scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.status != "open":
        raise HTTPException(status_code=400, detail=f"Listing is {listing.status}")

    agent = (await db.execute(select(Agent).where(Agent.id == agent_id, Agent.owner_id == user.id))).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found or not owned by you")

    listing.status = "accepted"
    listing.winning_agent_id = agent.id

    task = Task(
        agent_id=agent.id,
        title=listing.title,
        description=listing.description,
        status="running",
        reward_cog=listing.reward_cog,
        started_at=datetime.now(timezone.utc),
    )
    db.add(task)
    await db.flush()
    listing.winning_task_id = task.id

    if listing.chain_task_id is not None:
        if not user.wallet_address or not user.wallet_address.strip():
            raise HTTPException(
                status_code=400,
                detail="Connect your wallet (e.g. MetaMask) to receive on-chain COG reward when the task is completed.",
            )
        logger.info("accept_task: calling chain listing_id=%s chain_task_id=%s reward_recipient=%s", listing_id, listing.chain_task_id, user.wallet_address[:10] + "..." if len(user.wallet_address or "") > 10 else user.wallet_address)
        tx_hash = await asyncio.to_thread(
            chain_service.accept_task_on_chain,
            listing.chain_task_id,
            str(agent.id),
            user.wallet_address.strip(),
        )
        if tx_hash:
            listing.tx_hash = tx_hash
            logger.info("accept_task: chain accept ok listing_id=%s tx_hash=%s", listing_id, tx_hash)
        else:
            logger.warning("accept_task: chain accept failed (see chain_service logs). listing_id=%s chain_task_id=%s", listing_id, listing.chain_task_id)
    else:
        logger.info("accept_task: listing has no chain_task_id, skipping chain. listing_id=%s", listing_id)

    await db.flush()
    await db.refresh(listing)
    return listing


@router.post("/{listing_id}/complete", response_model=TaskListingResponse)
async def complete_task(listing_id: uuid.UUID, db: DBSession, user: CurrentUser):
    listing = (await db.execute(select(TaskListing).where(TaskListing.id == listing_id))).scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.status != "accepted":
        raise HTTPException(status_code=400, detail="Listing must be accepted first")

    if listing.winning_task_id:
        task = (await db.execute(select(Task).where(Task.id == listing.winning_task_id))).scalar_one_or_none()
        if task:
            task.status = "completed"
            task.completed_at = datetime.now(timezone.utc)

    if listing.chain_task_id is not None:
        logger.info("complete_task: calling chain listing_id=%s chain_task_id=%s", listing_id, listing.chain_task_id)
        tx_hash = await asyncio.to_thread(chain_service.complete_task_on_chain, listing.chain_task_id)
        if not tx_hash:
            logger.warning("complete_task: chain complete failed (see chain_service logs). listing_id=%s chain_task_id=%s", listing_id, listing.chain_task_id)
            raise HTTPException(
                status_code=503,
                detail="Chain completion failed. Check Revive RPC and deployer balance; retry later.",
            )
        listing.tx_hash = tx_hash
        logger.info("complete_task: chain complete ok listing_id=%s tx_hash=%s (COG sent to rewardRecipient)", listing_id, tx_hash)
        if listing.winning_agent_id:
            reward_wei = _reward_to_wei(float(listing.reward_cog))
            await asyncio.to_thread(
                chain_service.record_reputation_task_complete,
                str(listing.winning_agent_id),
                reward_wei,
            )
    else:
        logger.info("complete_task: listing has no chain_task_id, skipping chain (no COG transfer). listing_id=%s", listing_id)

    if listing.winning_agent_id:
        rep = (await db.execute(
            select(AgentReputation).where(AgentReputation.agent_id == listing.winning_agent_id)
        )).scalar_one_or_none()
        if rep:
            rep.tasks_completed += 1
            rep.total_cog_earned += Decimal(str(listing.reward_cog))
            rep.score = min(5.0, rep.score + 0.1)

        db.add(ReputationEvent(
            agent_id=listing.winning_agent_id,
            event_type="task_complete",
            delta=0.1,
            reason=f"Completed: {listing.title}",
            task_id=listing.winning_task_id,
        ))

    listing.status = "completed"
    await db.flush()
    await db.refresh(listing)
    return listing
