"""
Life++ API — Agent Endpoints
/api/v1/agents/*
"""
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.agents.runtime.agent_runtime import AgentRuntime
from app.db.session import DBSession
from app.models.models import User
from app.schemas.schemas import (
    AgentCreate,
    AgentListResponse,
    AgentResponse,
    AgentUpdate,
    ChatRequest,
    ChatResponse,
)
from app.services.agent_service import AgentService
from app.api.v1.deps import CurrentUser

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Create a new persistent AI agent owned by the authenticated user."""
    svc = AgentService(db)
    agent = await svc.create(owner_id=current_user.id, data=payload)
    return AgentResponse.model_validate(agent)


@router.get("", response_model=AgentListResponse)
async def list_my_agents(
    db: DBSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List all agents owned by the current user."""
    svc = AgentService(db)
    agents, total = await svc.get_by_owner(
        owner_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    return AgentListResponse(
        agents=[AgentResponse.model_validate(a) for a in agents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/discover", response_model=AgentListResponse)
async def discover_agents(
    db: DBSession,
    capability: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Discover public agents on the Life++ network, optionally filtered by capability."""
    svc = AgentService(db)
    agents, total = await svc.list_public(
        capability=capability,
        page=page,
        page_size=page_size,
    )
    return AgentListResponse(
        agents=[AgentResponse.model_validate(a) for a in agents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: uuid.UUID, db: DBSession):
    """Get a specific agent by ID."""
    svc = AgentService(db)
    agent = await svc.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse.model_validate(agent)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: uuid.UUID,
    payload: AgentUpdate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Update an agent (owner only)."""
    svc = AgentService(db)
    agent = await svc.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await svc.assert_owner(agent, current_user.id)
    agent = await svc.update(agent, payload)
    return AgentResponse.model_validate(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Permanently delete an agent (owner only)."""
    svc = AgentService(db)
    agent = await svc.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await svc.assert_owner(agent, current_user.id)
    await svc.delete(agent)


@router.post("/{agent_id}/chat", response_model=ChatResponse)
async def chat_with_agent(
    agent_id: uuid.UUID,
    payload: ChatRequest,
    db: DBSession,
    current_user: CurrentUser,
):
    """
    Send a message to an agent and receive a memory-augmented response.
    The agent uses its persistent memory and may call tools during reasoning.
    """
    svc = AgentService(db)
    agent = await svc.get_by_id(agent_id, load_reputation=False)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Allow owner or any user to chat with public agents
    if not agent.is_public:
        await svc.assert_owner(agent, current_user.id)

    runtime = AgentRuntime(agent=agent, db=db)
    response = await runtime.chat(payload)

    # Update agent status to active
    from app.models.models import AgentStatusEnum
    await svc.set_status(agent, AgentStatusEnum.active)

    return response


@router.post("/{agent_id}/chat/stream")
async def chat_stream(
    agent_id: uuid.UUID,
    payload: ChatRequest,
    db: DBSession,
    current_user: CurrentUser,
):
    """Streaming chat — returns Server-Sent Events."""
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
