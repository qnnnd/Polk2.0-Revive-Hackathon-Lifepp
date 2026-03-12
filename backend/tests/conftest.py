import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.session import engine, Base
from main import app


@pytest_asyncio.fixture(loop_scope="session", scope="session", autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture(loop_scope="session")
async def client(setup_database):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
