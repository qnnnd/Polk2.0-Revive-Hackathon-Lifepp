"""
Life++ API — Marketplace Endpoints
Global task listing, acceptance, completion. Revive chain integration (13.4).
"""
import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.v1.deps import CurrentUser
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
        tx_hash = await asyncio.to_thread(
            chain_service.accept_task_on_chain,
            listing.chain_task_id,
            str(agent.id),
        )
        if tx_hash:
            listing.tx_hash = tx_hash

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
        tx_hash = await asyncio.to_thread(chain_service.complete_task_on_chain, listing.chain_task_id)
        if tx_hash:
            listing.tx_hash = tx_hash
        if listing.winning_agent_id:
            reward_wei = _reward_to_wei(float(listing.reward_cog))
            await asyncio.to_thread(
                chain_service.record_reputation_task_complete,
                str(listing.winning_agent_id),
                reward_wei,
            )

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
