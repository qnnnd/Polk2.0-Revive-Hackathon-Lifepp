import os
import tempfile

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = os.path.join(tempfile.gettempdir(), "lifepp-test.db")

from app.main import app  # noqa: E402


client = TestClient(app)


def auth_headers(username: str = "alice", password: str = "password123"):
    client.post("/api/v1/auth/register", json={"username": username, "password": password})
    login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_full_p0_smoke_flow():
    headers = auth_headers()

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200

    created_agent = client.post(
        "/api/v1/agents",
        json={"name": "Nexus", "personality": "focused", "goal": "ship MVP"},
        headers=headers,
    )
    assert created_agent.status_code == 200
    agent_id = created_agent.json()["id"]

    listed_agents = client.get("/api/v1/agents", headers=headers)
    assert listed_agents.status_code == 200
    assert len(listed_agents.json()["items"]) >= 1

    memory = client.post(
        f"/api/v1/agents/{agent_id}/memories",
        json={"memory_type": "episodic", "content": "user prefers concise updates", "importance": 0.9},
        headers=headers,
    )
    assert memory.status_code == 200

    memory_search = client.post(
        f"/api/v1/agents/{agent_id}/memories/search",
        json={"query": "concise", "top_k": 5},
        headers=headers,
    )
    assert memory_search.status_code == 200
    assert len(memory_search.json()["items"]) == 1

    chat = client.post(
        f"/api/v1/agents/{agent_id}/chat",
        json={"message": "今天进展怎样？"},
        headers=headers,
    )
    assert chat.status_code == 200
    assert chat.json()["recalled_count"] >= 1

    task = client.post(
        "/api/v1/tasks",
        json={"title": "完成 demo", "description": "完成并彩排", "reward": 12},
        headers=headers,
    )
    assert task.status_code == 200
    task_id = task.json()["id"]

    accepted = client.post(f"/api/v1/tasks/{task_id}/accept", params={"assignee_agent_id": agent_id}, headers=headers)
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    completed = client.post(f"/api/v1/tasks/{task_id}/complete", headers=headers)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    net_agents = client.get("/api/v1/network/agents", headers=headers)
    assert net_agents.status_code == 200

    conn = client.post(
        "/api/v1/network/connections",
        json={"source_agent_id": agent_id, "target_agent_id": agent_id, "relation_type": "self-check"},
        headers=headers,
    )
    assert conn.status_code == 200

    net_conn = client.get("/api/v1/network/connections", headers=headers)
    assert net_conn.status_code == 200
    assert len(net_conn.json()["items"]) >= 1
