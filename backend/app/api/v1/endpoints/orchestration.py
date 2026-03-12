from fastapi import APIRouter

router = APIRouter(prefix="/orchestration", tags=["orchestration"])


@router.get("/status")
async def orchestration_status():
    return {"status": "idle", "active_workflows": 0}
