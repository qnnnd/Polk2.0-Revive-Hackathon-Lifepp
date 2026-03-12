"""
Life++ API — Task Endpoints (per-agent)
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.v1.deps import CurrentUser
from app.db.session import DBSession
from app.models.models import Task
from app.schemas.schemas import TaskCreate, TaskListResponse, TaskResponse
from app.services.agent_service import AgentService

router = APIRouter(prefix="/agents/{agent_id}/tasks", tags=["Tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(agent_id: str, payload: TaskCreate, db: DBSession, current_user: CurrentUser):
    svc = AgentService(db)
    agent = await svc.get_by_id(agent_id, load_reputation=False)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await svc.assert_owner(agent, current_user.id)

    task = Task(
        agent_id=agent_id, title=payload.title, description=payload.description,
        priority=payload.priority, input_data=payload.input_data,
        deadline_at=payload.deadline_at, reward_cog=payload.reward_cog,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return TaskResponse.model_validate(task)


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    agent_id: str, db: DBSession, current_user: CurrentUser,
    task_status: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    q = select(Task).where(Task.agent_id == agent_id)
    if task_status:
        q = q.where(Task.status == task_status)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()
    q = q.order_by(Task.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    tasks = list(result.scalars().all())
    return TaskListResponse(tasks=[TaskResponse.model_validate(t) for t in tasks], total=total)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(agent_id: str, task_id: str, db: DBSession, current_user: CurrentUser):
    result = await db.execute(select(Task).where(Task.id == task_id, Task.agent_id == agent_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status in ("completed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Task is already {task.status}")
    task.status = "cancelled"
    task.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return TaskResponse.model_validate(task)
