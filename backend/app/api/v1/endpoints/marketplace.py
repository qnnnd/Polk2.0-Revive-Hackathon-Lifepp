"""
Life++ API — Marketplace Endpoints
Task listing, acceptance, completion with on-chain settlement.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.v1.deps import CurrentUser
from app.db.session import DBSession
from app.models.models import (
    Agent, AgentReputation, ReputationEvent, Task, TaskListing, User,
)
from app.schemas.schemas import TaskCreate, TaskListingCreate, TaskListingResponse, TaskResponse

router = APIRouter(prefix="/tasks", tags=["Marketplace"])


@router.post("", response_model=TaskListingResponse, status_code=status.HTTP_201_CREATED)
async def publish_task(payload: TaskListingCreate, db: DBSession, current_user: CurrentUser):
    """Publish a task to the marketplace. Locks reward_cog from poster's balance."""
    agents_q = select(Agent).where(Agent.owner_id == current_user.id).limit(1)
    result = await db.execute(agents_q)
    poster_agent = result.scalar_one_or_none()
    if not poster_agent:
        raise HTTPException(status_code=400, detail="You need at least one agent to publish tasks")

    if current_user.cog_balance < payload.reward_cog:
        raise HTTPException(status_code=400, detail="Insufficient COG balance for escrow")

    current_user.cog_balance -= payload.reward_cog

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
    await db.refresh(listing)
    return TaskListingResponse.model_validate(listing)


@router.get("", response_model=list[TaskListingResponse])
async def list_tasks(
    db: DBSession,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    q = select(TaskListing)
    if status_filter:
        q = q.where(TaskListing.status == status_filter)
    q = q.order_by(TaskListing.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    listings = result.scalars().all()
    return [TaskListingResponse.model_validate(l) for l in listings]


@router.post("/{listing_id}/accept", response_model=TaskListingResponse)
async def accept_task(listing_id: str, agent_id: str, db: DBSession, current_user: CurrentUser):
    """Agent accepts a marketplace task."""
    listing_q = select(TaskListing).where(TaskListing.id == listing_id)
    listing = (await db.execute(listing_q)).scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Task listing not found")
    if listing.status != "open":
        raise HTTPException(status_code=400, detail=f"Task is {listing.status}, not open")

    agent_q = select(Agent).where(Agent.id == agent_id, Agent.owner_id == current_user.id)
    agent = (await db.execute(agent_q)).scalar_one_or_none()
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
        escrow_status="locked",
        started_at=datetime.now(timezone.utc),
    )
    db.add(task)
    await db.flush()
    listing.winning_task_id = task.id
    await db.flush()
    await db.refresh(listing)
    return TaskListingResponse.model_validate(listing)


@router.post("/{listing_id}/complete", response_model=TaskListingResponse)
async def complete_task(listing_id: str, db: DBSession, current_user: CurrentUser):
    """Complete a task: release escrow, update reputation."""
    listing_q = select(TaskListing).where(TaskListing.id == listing_id)
    listing = (await db.execute(listing_q)).scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Task listing not found")
    if listing.status != "accepted":
        raise HTTPException(status_code=400, detail="Task must be in accepted state")

    task_q = select(Task).where(Task.id == listing.winning_task_id)
    task = (await db.execute(task_q)).scalar_one_or_none()
    if task:
        task.status = "completed"
        task.escrow_status = "released"
        task.completed_at = datetime.now(timezone.utc)

    winning_agent_q = select(Agent).where(Agent.id == listing.winning_agent_id)
    winning_agent = (await db.execute(winning_agent_q)).scalar_one_or_none()
    if winning_agent:
        owner_q = select(User).where(User.id == winning_agent.owner_id)
        owner = (await db.execute(owner_q)).scalar_one_or_none()
        if owner:
            owner.cog_balance += listing.reward_cog

        rep_q = select(AgentReputation).where(AgentReputation.agent_id == winning_agent.id)
        rep = (await db.execute(rep_q)).scalar_one_or_none()
        if rep:
            rep.tasks_completed += 1
            rep.total_cog_earned += listing.reward_cog
            rep.score = min(5.0, rep.score + 0.1)

        rep_event = ReputationEvent(
            agent_id=winning_agent.id,
            event_type="task_complete",
            delta=0.1,
            reason=f"Completed task: {listing.title}",
            task_id=task.id if task else None,
        )
        db.add(rep_event)

    listing.status = "completed"
    await db.flush()
    await db.refresh(listing)
    return TaskListingResponse.model_validate(listing)
