"""
Life++ — FastAPI Application Entry Point
Production-grade server with structured logging, CORS, lifespan events.
SQLite-based storage — zero external dependencies.
"""
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.session import init_db
from app.api.v1.endpoints.agents import router as agents_router
from app.api.v1.endpoints.memories import router as memories_router
from app.api.v1.endpoints.tasks import router as tasks_router
from app.api.v1.endpoints.network import network_router, auth_router
from app.api.v1.endpoints.marketplace import router as marketplace_router
from app.api.v1.endpoints.orchestration import router as orchestration_router

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("lifeplusplus")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.ENVIRONMENT}]")
    logger.info(f"Database: {settings.DATABASE_URL}")
    await init_db()
    logger.info("Database tables initialized")
    yield
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Peer-to-Peer Cognitive Agent Network API",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
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
async def add_request_id(request: Request, call_next):
    import uuid
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.method} {request.url}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


PREFIX = settings.API_V1_PREFIX

app.include_router(auth_router,          prefix=PREFIX)
app.include_router(agents_router,        prefix=PREFIX)
app.include_router(memories_router,      prefix=PREFIX)
app.include_router(tasks_router,         prefix=PREFIX)
app.include_router(network_router,       prefix=PREFIX)
app.include_router(marketplace_router,   prefix=PREFIX)
app.include_router(orchestration_router, prefix=PREFIX)


@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/", tags=["System"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "tagline": "Peer-to-Peer Cognitive Agent Network",
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_level="debug" if settings.DEBUG else "info",
    )
