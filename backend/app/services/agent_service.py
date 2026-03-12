import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import Agent, AgentReputation
from app.schemas.schemas import AgentCreate, AgentUpdate


class AgentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, owner_id: uuid.UUID, data: AgentCreate) -> Agent:
        agent = Agent(
            id=uuid.uuid4(),
            owner_id=owner_id,
            name=data.name,
            description=data.description,
            model=data.model,
            system_prompt=data.system_prompt,
            personality=data.personality,
            capabilities=data.capabilities,
            is_public=data.is_public,
        )
        self.db.add(agent)
        await self.db.flush()

        reputation = AgentReputation(
            id=uuid.uuid4(),
            agent_id=agent.id,
        )
        self.db.add(reputation)
        await self.db.flush()

        result = await self.db.execute(
            select(Agent)
            .where(Agent.id == agent.id)
            .options(selectinload(Agent.reputation))
        )
        return result.scalar_one()

    async def get_by_id(
        self, agent_id: uuid.UUID, load_reputation: bool = True
    ) -> Optional[Agent]:
        stmt = select(Agent).where(Agent.id == agent_id)
        if load_reputation:
            stmt = stmt.options(selectinload(Agent.reputation))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_owner(
        self, owner_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[Agent], int]:
        count_result = await self.db.execute(
            select(func.count(Agent.id)).where(Agent.owner_id == owner_id)
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(Agent)
            .where(Agent.owner_id == owner_id)
            .options(selectinload(Agent.reputation))
            .order_by(Agent.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        agents = list(result.scalars().all())
        return agents, total

    async def list_public(
        self,
        capability: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Agent], int]:
        base = select(Agent).where(
            Agent.is_public == True,
            Agent.status != "terminated",
        )
        if capability:
            base = base.where(Agent.capabilities.contains([capability]))

        count_stmt = select(func.count()).select_from(base.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.db.execute(
            base.options(selectinload(Agent.reputation))
            .order_by(Agent.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        agents = list(result.scalars().all())
        return agents, total

    async def update(self, agent: Agent, data: AgentUpdate) -> Agent:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(agent, field, value)
        agent.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return agent

    async def set_status(self, agent: Agent, new_status: str) -> Agent:
        agent.status = new_status
        agent.last_active_at = datetime.now(timezone.utc)
        await self.db.flush()
        return agent

    async def delete(self, agent: Agent) -> None:
        await self.db.delete(agent)
        await self.db.flush()

    @staticmethod
    def assert_owner(agent: Agent, user_id: uuid.UUID) -> None:
        if agent.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not own this agent",
            )
