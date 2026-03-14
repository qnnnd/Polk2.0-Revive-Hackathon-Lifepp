import asyncio

from fastapi import APIRouter

from app.core.config import settings
from app.db.session import DBSession
from app.schemas.schemas import NetworkGraphResponse
from app.services import chain_service
from app.services.network_service import NetworkService

router = APIRouter(prefix="/network", tags=["Network"])


@router.get("/graph", response_model=NetworkGraphResponse)
async def get_network_graph(db: DBSession):
    service = NetworkService(db)
    graph = await service.get_graph()
    # Overlay Revive chain reputation when configured (13.4)
    if settings.revive_configured:
        for node in graph.get("nodes", []):
            chain_rep = await asyncio.to_thread(
                chain_service.reputation_for_ui, str(node["id"])
            )
            if chain_rep:
                node["reputation_score"] = chain_rep["score"]
    return graph


@router.get("/stats")
async def get_network_stats(db: DBSession):
    service = NetworkService(db)
    stats = await service.get_stats()
    return stats
