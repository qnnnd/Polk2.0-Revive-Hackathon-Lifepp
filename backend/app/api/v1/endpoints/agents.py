import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.agents.runtime.agent_runtime import AgentRuntime
from app.api.v1.deps import CurrentUser
from app.db.session import DBSession
from app.schemas.schemas import (
    AgentCreate,
    AgentListResponse,
    AgentResponse,
    AgentUpdate,
    ChatRequest,
    ChatResponse,
)
from app.services.agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(data: AgentCreate, db: DBSession, user: CurrentUser):
    service = AgentService(db)
    agent = await service.create(user.id, data)
    return agent


@router.get("", response_model=AgentListResponse)
async def list_agents(
    db: DBSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = AgentService(db)
    agents, total = await service.get_by_owner(user.id, page, page_size)
    return AgentListResponse(agents=agents, total=total, page=page, page_size=page_size)


@router.get("/discover", response_model=AgentListResponse)
async def discover_agents(
    db: DBSession,
    capability: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = AgentService(db)
    agents, total = await service.list_public(capability, page, page_size)
    return AgentListResponse(agents=agents, total=total, page=page, page_size=page_size)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: uuid.UUID, db: DBSession):
    service = AgentService(db)
    agent = await service.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: uuid.UUID, data: AgentUpdate, db: DBSession, user: CurrentUser
):
    service = AgentService(db)
    agent = await service.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    service.assert_owner(agent, user.id)
    updated = await service.update(agent, data)
    return updated


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: uuid.UUID, db: DBSession, user: CurrentUser):
    service = AgentService(db)
    agent = await service.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    service.assert_owner(agent, user.id)
    await service.delete(agent)


@router.post("/{agent_id}/chat", response_model=ChatResponse)
async def chat_with_agent(
    agent_id: uuid.UUID, data: ChatRequest, db: DBSession, user: CurrentUser
):
    service = AgentService(db)
    agent = await service.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    runtime = AgentRuntime(db, agent)
    result = await runtime.chat(data.content, data.session_id)
    return result


@router.post("/{agent_id}/chat/stream")
async def chat_stream(
    agent_id: uuid.UUID, data: ChatRequest, db: DBSession, user: CurrentUser
):
    service = AgentService(db)
    agent = await service.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    runtime = AgentRuntime(db, agent)
    return StreamingResponse(
        runtime.chat_stream(data.content, data.session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
