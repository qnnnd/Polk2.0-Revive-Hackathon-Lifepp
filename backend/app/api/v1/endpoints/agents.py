import asyncio
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
    ReputationResponse,
)
from app.services.agent_service import AgentService
from app.services import chain_service

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(data: AgentCreate, db: DBSession, user: CurrentUser):
    service = AgentService(db)
    agent = await service.create(user.id, data)
    # Register on Revive AgentRegistry (13.4: must use Revive)
    tx_hash = await asyncio.to_thread(
        chain_service.register_agent,
        str(agent.id),
        agent.name,
        "",  # metadata URI placeholder
    )
    if tx_hash:
        agent.chain_registered_tx_hash = tx_hash
        db.add(agent)
        await db.flush()
        await db.refresh(agent)
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
    response = AgentResponse.model_validate(agent)
    # Overlay Revive chain reputation when available (13.4)
    chain_rep = await asyncio.to_thread(chain_service.reputation_for_ui, str(agent.id))
    if chain_rep:
        response.reputation = ReputationResponse(
            score=chain_rep["score"],
            tasks_completed=chain_rep["tasks_completed"],
            tasks_failed=chain_rep["tasks_failed"],
            avg_quality_score=chain_rep["score"],
            total_cog_earned=chain_rep["total_cog_earned"],
            endorsements=chain_rep["endorsements"],
        )
    return response


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
