"""
Life++ API — Agent Endpoints
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.agents.runtime.agent_runtime import AgentRuntime
from app.db.session import DBSession
from app.schemas.schemas import (
    AgentCreate, AgentListResponse, AgentResponse, AgentUpdate,
    ChatRequest, ChatResponse,
)
from app.services.agent_service import AgentService
from app.api.v1.deps import CurrentUser

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(payload: AgentCreate, db: DBSession, current_user: CurrentUser):
    svc = AgentService(db)
    agent = await svc.create(owner_id=current_user.id, data=payload)
    return AgentResponse.model_validate(agent)


@router.get("", response_model=AgentListResponse)
async def list_my_agents(
    db: DBSession, current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    svc = AgentService(db)
    agents, total = await svc.get_by_owner(owner_id=current_user.id, page=page, page_size=page_size)
    return AgentListResponse(
        agents=[AgentResponse.model_validate(a) for a in agents],
        total=total, page=page, page_size=page_size,
    )


@router.get("/discover", response_model=AgentListResponse)
async def discover_agents(
    db: DBSession, capability: Optional[str] = None,
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
):
    svc = AgentService(db)
    agents, total = await svc.list_public(capability=capability, page=page, page_size=page_size)
    return AgentListResponse(
        agents=[AgentResponse.model_validate(a) for a in agents],
        total=total, page=page, page_size=page_size,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, db: DBSession):
    svc = AgentService(db)
    agent = await svc.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse.model_validate(agent)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, payload: AgentUpdate, db: DBSession, current_user: CurrentUser):
    svc = AgentService(db)
    agent = await svc.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await svc.assert_owner(agent, current_user.id)
    agent = await svc.update(agent, payload)
    return AgentResponse.model_validate(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: str, db: DBSession, current_user: CurrentUser):
    svc = AgentService(db)
    agent = await svc.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await svc.assert_owner(agent, current_user.id)
    await svc.delete(agent)


@router.post("/{agent_id}/chat", response_model=ChatResponse)
async def chat_with_agent(agent_id: str, payload: ChatRequest, db: DBSession, current_user: CurrentUser):
    svc = AgentService(db)
    agent = await svc.get_by_id(agent_id, load_reputation=False)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if not agent.is_public:
        await svc.assert_owner(agent, current_user.id)

    runtime = AgentRuntime(agent=agent, db=db)
    response = await runtime.chat(payload)
    await svc.set_status(agent, "active")
    return response


@router.post("/{agent_id}/chat/stream")
async def chat_stream(agent_id: str, payload: ChatRequest, db: DBSession, current_user: CurrentUser):
    svc = AgentService(db)
    agent = await svc.get_by_id(agent_id, load_reputation=False)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if not agent.is_public:
        await svc.assert_owner(agent, current_user.id)

    runtime = AgentRuntime(agent=agent, db=db)
    return StreamingResponse(
        runtime.chat_stream(payload),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
