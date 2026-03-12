"""
Life++ — Agent Service
Business logic for agent CRUD, status management, and registry.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import Agent, AgentReputation, AgentStatusEnum, User
from app.schemas.schemas import AgentCreate, AgentUpdate


class AgentService:
    """
    Encapsulates all agent-related database operations.
    Called by API endpoints; never touches HTTP directly.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, owner_id: uuid.UUID, data: AgentCreate) -> Agent:
        """Create a new agent and initialize its reputation record."""
        agent = Agent(
            owner_id=owner_id,
            name=data.name,
            description=data.description,
            model=data.model,
            system_prompt=data.system_prompt,
            personality=data.personality,
            capabilities=data.capabilities,
            is_public=data.is_public,
            status=AgentStatusEnum.idle,
        )
        self.db.add(agent)
        await self.db.flush()   # Get ID without committing

        # Bootstrap reputation
        reputation = AgentReputation(agent_id=agent.id)
        self.db.add(reputation)

        await self.db.flush()
        await self.db.refresh(agent, ["reputation"])
        return agent

    async def get_by_id(
        self,
        agent_id: uuid.UUID,
        load_reputation: bool = True,
    ) -> Optional[Agent]:
        q = select(Agent).where(Agent.id == agent_id)
        if load_reputation:
            q = q.options(selectinload(Agent.reputation))
        result = await self.db.execute(q)
        return result.scalar_one_or_none()

    async def get_by_owner(
        self,
        owner_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Agent], int]:
        offset = (page - 1) * page_size

        count_q = select(func.count()).select_from(Agent).where(Agent.owner_id == owner_id)
        total = (await self.db.execute(count_q)).scalar_one()

        q = (
            select(Agent)
            .where(Agent.owner_id == owner_id)
            .options(selectinload(Agent.reputation))
            .order_by(Agent.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(q)
        return result.scalars().all(), total

    async def list_public(
        self,
        capability: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Agent], int]:
        offset = (page - 1) * page_size

        base = select(Agent).where(Agent.is_public == True, Agent.status != AgentStatusEnum.terminated)

        if capability:
            base = base.where(Agent.capabilities.contains([capability]))

        count_q = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_q)).scalar_one()

        q = (
            base
            .options(selectinload(Agent.reputation))
            .order_by(Agent.last_active_at.desc().nullslast())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(q)
        return result.scalars().all(), total

    async def update(self, agent: Agent, data: AgentUpdate) -> Agent:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(agent, field, value)
        await self.db.flush()
        return agent

    async def set_status(self, agent: Agent, status: str) -> Agent:
        agent.status = status
        agent.last_active_at = datetime.now(timezone.utc)
        await self.db.flush()
        return agent

    async def delete(self, agent: Agent) -> None:
        await self.db.delete(agent)

    async def assert_owner(self, agent: Agent, user_id: uuid.UUID) -> None:
        """Raise if the requesting user is not the agent's owner."""
        if agent.owner_id != user_id:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Not the agent owner")
