import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AgentReputation, Task
from app.schemas.schemas import TaskCreate


class TaskService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, agent_id: uuid.UUID, data: TaskCreate) -> Task:
        task = Task(
            id=uuid.uuid4(),
            agent_id=agent_id,
            title=data.title,
            description=data.description,
            priority=data.priority,
            input_data=data.input_data,
            deadline_at=data.deadline_at,
            reward_cog=data.reward_cog,
        )
        self.db.add(task)
        await self.db.flush()
        return task

    async def get_by_id(self, task_id: uuid.UUID) -> Optional[Task]:
        result = await self.db.execute(
            select(Task).where(Task.id == task_id)
        )
        return result.scalar_one_or_none()

    async def list_by_agent(
        self,
        agent_id: uuid.UUID,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Task], int]:
        base = select(Task).where(Task.agent_id == agent_id)
        if status_filter:
            base = base.where(Task.status == status_filter)

        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.db.execute(
            base.order_by(Task.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        tasks = list(result.scalars().all())
        return tasks, total

    async def cancel(self, task: Task) -> Task:
        if task.status not in ("pending", "running"):
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel task with status '{task.status}'",
            )
        task.status = "cancelled"
        task.completed_at = datetime.now(timezone.utc)
        await self.db.flush()
        return task

    async def run_mock(self, task: Task) -> Task:
        now = datetime.now(timezone.utc)
        task.status = "running"
        task.started_at = now
        await self.db.flush()

        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)
        task.output_data = {
            "result": f"Mock execution result for '{task.title}'",
            "quality_score": 0.85,
            "execution_time_ms": 1234,
        }
        task.steps = [
            {"step": 1, "action": "analyze_input", "status": "completed"},
            {"step": 2, "action": "process_data", "status": "completed"},
            {"step": 3, "action": "generate_output", "status": "completed"},
        ]
        await self.db.flush()

        result = await self.db.execute(
            select(AgentReputation).where(AgentReputation.agent_id == task.agent_id)
        )
        reputation = result.scalar_one_or_none()
        if reputation:
            reputation.tasks_completed = (reputation.tasks_completed or 0) + 1
            reputation.score = min(5.0, reputation.score + 0.1)
            reputation.avg_quality_score = round(
                (reputation.avg_quality_score * max(0, reputation.tasks_completed - 1) + 0.85)
                / reputation.tasks_completed,
                4,
            )
            reputation.total_cog_earned = (reputation.total_cog_earned or 0) + float(task.reward_cog or 0)
            reputation.updated_at = datetime.now(timezone.utc)
            await self.db.flush()

        return task
