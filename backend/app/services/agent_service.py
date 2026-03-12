"""
Life++ — Agent Service
Business logic for agent CRUD, status management, and registry.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import Agent, AgentReputation
from app.schemas.schemas import AgentCreate, AgentUpdate


class AgentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, owner_id: str, data: AgentCreate) -> Agent:
        agent = Agent(
            owner_id=owner_id,
            name=data.name,
            description=data.description,
            model=data.model,
            system_prompt=data.system_prompt,
            personality=data.personality,
            capabilities=data.capabilities,
            is_public=data.is_public,
            status="idle",
        )
        self.db.add(agent)
        await self.db.flush()

        reputation = AgentReputation(agent_id=agent.id)
        self.db.add(reputation)
        await self.db.flush()
        await self.db.refresh(agent)

        rep_q = select(AgentReputation).where(AgentReputation.agent_id == agent.id)
        rep_result = await self.db.execute(rep_q)
        agent.__dict__["reputation"] = rep_result.scalar_one_or_none()
        return agent

    async def get_by_id(self, agent_id: str, load_reputation: bool = True) -> Optional[Agent]:
        q = select(Agent).where(Agent.id == agent_id)
        result = await self.db.execute(q)
        agent = result.scalar_one_or_none()
        if agent and load_reputation:
            rep_q = select(AgentReputation).where(AgentReputation.agent_id == agent.id)
            rep_result = await self.db.execute(rep_q)
            agent.__dict__["reputation"] = rep_result.scalar_one_or_none()
        return agent

    async def get_by_owner(
        self, owner_id: str, page: int = 1, page_size: int = 20,
    ) -> tuple[List[Agent], int]:
        offset = (page - 1) * page_size
        count_q = select(func.count()).select_from(Agent).where(Agent.owner_id == owner_id)
        total = (await self.db.execute(count_q)).scalar_one()

        q = (
            select(Agent)
            .where(Agent.owner_id == owner_id)
            .order_by(Agent.created_at.desc())
            .offset(offset).limit(page_size)
        )
        result = await self.db.execute(q)
        agents = list(result.scalars().all())

        for agent in agents:
            rep_q = select(AgentReputation).where(AgentReputation.agent_id == agent.id)
            rep_result = await self.db.execute(rep_q)
            agent.__dict__["reputation"] = rep_result.scalar_one_or_none()

        return agents, total

    async def list_public(
        self, capability: Optional[str] = None, page: int = 1, page_size: int = 20,
    ) -> tuple[List[Agent], int]:
        offset = (page - 1) * page_size
        q = select(Agent).where(Agent.is_public == True, Agent.status != "terminated")

        if capability:
            q = q.where(Agent.capabilities.contains(f'"{capability}"'))

        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar_one()

        q = q.order_by(Agent.created_at.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(q)
        agents = list(result.scalars().all())

        for agent in agents:
            rep_q = select(AgentReputation).where(AgentReputation.agent_id == agent.id)
            rep_result = await self.db.execute(rep_q)
            agent.__dict__["reputation"] = rep_result.scalar_one_or_none()

        return agents, total

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

    async def assert_owner(self, agent: Agent, user_id: str) -> None:
        if agent.owner_id != user_id:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Not the agent owner")
