import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.api.v1.deps import CurrentUser
from app.db.session import DBSession
from app.schemas.schemas import (
    MemoryCreate,
    MemoryResponse,
    MemorySearchRequest,
    MemorySearchResponse,
)
from app.services.agent_service import AgentService
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/agents/{agent_id}/memories", tags=["Memories"])


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def store_memory(
    agent_id: uuid.UUID, data: MemoryCreate, db: DBSession, user: CurrentUser
):
    agent_service = AgentService(db)
    agent = await agent_service.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    agent_service.assert_owner(agent, user.id)

    memory_service = MemoryService(db)
    memory = await memory_service.store(agent_id, data)
    return memory


@router.get("")
async def list_memories(
    agent_id: uuid.UUID,
    db: DBSession,
    user: CurrentUser,
    memory_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    agent_service = AgentService(db)
    agent = await agent_service.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    agent_service.assert_owner(agent, user.id)

    memory_service = MemoryService(db)
    memories, total = await memory_service.get_all(agent_id, memory_type, page, page_size)
    return {"memories": memories, "total": total}


@router.post("/search", response_model=MemorySearchResponse)
async def search_memories(
    agent_id: uuid.UUID, data: MemorySearchRequest, db: DBSession, user: CurrentUser
):
    agent_service = AgentService(db)
    agent = await agent_service.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    agent_service.assert_owner(agent, user.id)

    memory_service = MemoryService(db)
    memories = await memory_service.search(
        agent_id,
        data.query,
        data.memory_type,
        data.top_k,
        data.min_strength,
    )
    return MemorySearchResponse(
        memories=memories,
        query=data.query,
        total_found=len(memories),
    )


@router.post("/consolidate")
async def consolidate_memories(
    agent_id: uuid.UUID, db: DBSession, user: CurrentUser
):
    agent_service = AgentService(db)
    agent = await agent_service.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    agent_service.assert_owner(agent, user.id)

    memory_service = MemoryService(db)
    result = await memory_service.consolidate(agent_id)
    return result
