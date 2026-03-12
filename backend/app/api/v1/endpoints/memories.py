"""
Life++ API — Memory Endpoints
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.api.v1.deps import CurrentUser
from app.db.session import DBSession
from app.schemas.schemas import (
    MemoryCreate, MemoryResponse, MemorySearchRequest, MemorySearchResponse,
)
from app.services.agent_service import AgentService
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/agents/{agent_id}/memories", tags=["Memories"])


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def store_memory(agent_id: str, payload: MemoryCreate, db: DBSession, current_user: CurrentUser):
    svc = AgentService(db)
    agent = await svc.get_by_id(agent_id, load_reputation=False)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await svc.assert_owner(agent, current_user.id)
    mem_svc = MemoryService(db)
    memory = await mem_svc.store(agent_id=agent_id, data=payload)
    return MemoryResponse.model_validate(memory)


@router.get("")
async def list_memories(
    agent_id: str, db: DBSession, current_user: CurrentUser,
    memory_type: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    mem_svc = MemoryService(db)
    memories, total = await mem_svc.get_all(
        agent_id=agent_id, memory_type=memory_type, page=page, page_size=page_size,
    )
    return {
        "memories": [MemoryResponse.model_validate(m) for m in memories],
        "total": total,
    }


@router.post("/search", response_model=MemorySearchResponse)
async def search_memories(agent_id: str, payload: MemorySearchRequest, db: DBSession, current_user: CurrentUser):
    mem_svc = MemoryService(db)
    memories = await mem_svc.search(
        agent_id=agent_id, query=payload.query,
        memory_type=payload.memory_type, top_k=payload.top_k, min_strength=payload.min_strength,
    )
    return MemorySearchResponse(
        memories=[MemoryResponse.model_validate(m) for m in memories],
        query=payload.query, total_found=len(memories),
    )


@router.post("/consolidate")
async def consolidate_memories(agent_id: str, db: DBSession, current_user: CurrentUser):
    svc = AgentService(db)
    agent = await svc.get_by_id(agent_id, load_reputation=False)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await svc.assert_owner(agent, current_user.id)
    mem_svc = MemoryService(db)
    return await mem_svc.consolidate(agent_id=agent_id)
