import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.session import init_db

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.agents import router as agents_router
from app.api.v1.endpoints.chain import router as chain_router
from app.api.v1.endpoints.memories import router as memories_router
from app.api.v1.endpoints.tasks import router as tasks_router
from app.api.v1.endpoints.network import router as network_router
from app.api.v1.endpoints.marketplace import router as marketplace_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _log_deployer_address():
    """Log deployer address so operator can verify it matches contract deployer (relayer)."""
    key = getattr(settings, "REVIVE_DEPLOYER_PRIVATE_KEY", None) or ""
    if not key or not key.strip():
        logger.info("REVIVE_DEPLOYER_PRIVATE_KEY not set; accept/complete on chain will be skipped.")
        return
    try:
        from eth_account import Account
        addr = Account.from_key(key.strip()).address
        logger.info(
            "Chain relayer (deployer) address: %s — must match 'deployer' in contracts/deployments.json for accept/complete to succeed.",
            addr,
        )
    except Exception as e:
        logger.warning("Could not derive deployer address from REVIVE_DEPLOYER_PRIVATE_KEY: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Life++ API v%s [%s]", settings.APP_VERSION, settings.ENVIRONMENT)
    _log_deployer_address()
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down Life++ API")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Life++ Agent Network API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{duration}ms"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s", str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(agents_router, prefix=settings.API_V1_PREFIX)
app.include_router(chain_router, prefix=settings.API_V1_PREFIX)
app.include_router(memories_router, prefix=settings.API_V1_PREFIX)
app.include_router(tasks_router, prefix=settings.API_V1_PREFIX)
app.include_router(network_router, prefix=settings.API_V1_PREFIX)
app.include_router(marketplace_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.is_development,
    )
