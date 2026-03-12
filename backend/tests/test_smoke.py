"""
Life++ Smoke Tests
Async tests using httpx.AsyncClient against the FastAPI app.
"""
import uuid

import pytest
from httpx import AsyncClient


async def _register_user(client: AsyncClient, suffix: str = "") -> dict:
    uid = uuid.uuid4().hex[:8]
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "did": f"did:key:z{uid}{suffix}",
            "username": f"user_{uid}{suffix}",
            "display_name": f"Test User {uid}",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _login(client: AsyncClient, username: str) -> str:
    resp = await client.post(f"/api/v1/auth/token?username={username}")
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _auth_headers(client: AsyncClient, suffix: str = "") -> tuple[dict, dict]:
    user = await _register_user(client, suffix)
    token = await _login(client, user["username"])
    return {"Authorization": f"Bearer {token}"}, user


@pytest.mark.asyncio(loop_scope="session")
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_register_and_login(client: AsyncClient):
    user = await _register_user(client, "_auth")
    assert "id" in user
    assert "username" in user

    token = await _login(client, user["username"])
    assert len(token) > 0


@pytest.mark.asyncio(loop_scope="session")
async def test_create_agent(client: AsyncClient):
    headers, user = await _auth_headers(client, "_agent")

    resp = await client.post(
        "/api/v1/agents",
        json={
            "name": "TestBot",
            "description": "A test agent",
            "capabilities": ["chat", "search"],
            "is_public": True,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    agent = resp.json()
    assert agent["name"] == "TestBot"
    assert agent["capabilities"] == ["chat", "search"]
    assert agent["reputation"] is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_memory_store_search(client: AsyncClient):
    headers, user = await _auth_headers(client, "_mem")

    agent_resp = await client.post(
        "/api/v1/agents",
        json={"name": "MemBot"},
        headers=headers,
    )
    assert agent_resp.status_code == 201
    agent_id = agent_resp.json()["id"]

    store_resp = await client.post(
        f"/api/v1/agents/{agent_id}/memories",
        json={
            "content": "The capital of France is Paris.",
            "importance": 0.9,
            "tags": ["geography"],
        },
        headers=headers,
    )
    assert store_resp.status_code == 201, store_resp.text
    memory = store_resp.json()
    assert memory["content"] == "The capital of France is Paris."

    search_resp = await client.post(
        f"/api/v1/agents/{agent_id}/memories/search",
        json={"query": "What is the capital of France?"},
        headers=headers,
    )
    assert search_resp.status_code == 200, search_resp.text
    search_data = search_resp.json()
    assert search_data["total_found"] >= 1


@pytest.mark.asyncio(loop_scope="session")
async def test_task_create_list(client: AsyncClient):
    headers, user = await _auth_headers(client, "_task")

    agent_resp = await client.post(
        "/api/v1/agents",
        json={"name": "TaskBot"},
        headers=headers,
    )
    assert agent_resp.status_code == 201
    agent_id = agent_resp.json()["id"]

    task_resp = await client.post(
        f"/api/v1/agents/{agent_id}/tasks",
        json={
            "title": "Analyze data",
            "description": "Process the test dataset",
            "priority": "high",
        },
        headers=headers,
    )
    assert task_resp.status_code == 201, task_resp.text
    task = task_resp.json()
    assert task["title"] == "Analyze data"
    assert task["status"] == "completed"

    list_resp = await client.get(
        f"/api/v1/agents/{agent_id}/tasks",
        headers=headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    list_data = list_resp.json()
    assert list_data["total"] >= 1
