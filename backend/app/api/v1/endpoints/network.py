from fastapi import APIRouter

from app.db.session import DBSession
from app.schemas.schemas import NetworkGraphResponse
from app.services.network_service import NetworkService

router = APIRouter(prefix="/network", tags=["Network"])


@router.get("/graph", response_model=NetworkGraphResponse)
async def get_network_graph(db: DBSession):
    service = NetworkService(db)
    graph = await service.get_graph()
    return graph


@router.get("/stats")
async def get_network_stats(db: DBSession):
    service = NetworkService(db)
    stats = await service.get_stats()
    return stats
