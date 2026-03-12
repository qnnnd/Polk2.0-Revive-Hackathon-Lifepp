import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.api.v1.deps import CurrentUser
from app.db.session import DBSession
from app.schemas.schemas import TaskCreate, TaskListResponse, TaskResponse
from app.services.agent_service import AgentService
from app.services.task_service import TaskService

router = APIRouter(prefix="/agents/{agent_id}/tasks", tags=["Tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    agent_id: uuid.UUID, data: TaskCreate, db: DBSession, user: CurrentUser
):
    agent_service = AgentService(db)
    agent = await agent_service.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    agent_service.assert_owner(agent, user.id)

    task_service = TaskService(db)
    task = await task_service.create(agent_id, data)
    task = await task_service.run_mock(task)
    return task


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    agent_id: uuid.UUID,
    db: DBSession,
    user: CurrentUser,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    agent_service = AgentService(db)
    agent = await agent_service.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    agent_service.assert_owner(agent, user.id)

    task_service = TaskService(db)
    tasks, total = await task_service.list_by_agent(agent_id, status_filter, page, page_size)
    return TaskListResponse(tasks=tasks, total=total)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    agent_id: uuid.UUID, task_id: uuid.UUID, db: DBSession, user: CurrentUser
):
    agent_service = AgentService(db)
    agent = await agent_service.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    agent_service.assert_owner(agent, user.id)

    task_service = TaskService(db)
    task = await task_service.get_by_id(task_id)
    if task is None or task.agent_id != agent_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(
    agent_id: uuid.UUID, task_id: uuid.UUID, db: DBSession, user: CurrentUser
):
    agent_service = AgentService(db)
    agent = await agent_service.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    agent_service.assert_owner(agent, user.id)

    task_service = TaskService(db)
    task = await task_service.get_by_id(task_id)
    if task is None or task.agent_id != agent_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    cancelled = await task_service.cancel(task)
    return cancelled
