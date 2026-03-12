from fastapi import APIRouter

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.get("")
async def list_marketplace():
    return {"listings": [], "total": 0}
