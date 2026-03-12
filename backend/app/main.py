from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.schemas import (
    RegisterRequest,
    LoginRequest,
    AgentCreateRequest,
    MemoryCreateRequest,
    MemorySearchRequest,
    ChatRequest,
    TaskCreateRequest,
    NetworkConnectRequest,
)
from app.services.auth import hash_password, create_token, get_current_user_id
from app.services.storage import Storage


app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = Storage()


@app.get("/health")
def health():
    return {"status": "ok", "version": settings.app_version}


@app.post("/api/v1/auth/register")
def register(req: RegisterRequest):
    with storage.connect() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (req.username, hash_password(req.password)),
            )
            conn.commit()
        except Exception as exc:
            raise HTTPException(status_code=409, detail="Username already exists") from exc
    return {"id": cursor.lastrowid, "username": req.username}


@app.post("/api/v1/auth/login")
def login(req: LoginRequest):
    with storage.connect() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (req.username,),
        ).fetchone()
    if not row or row["password_hash"] != hash_password(req.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(row["id"], row["username"])
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/v1/auth/me")
def me(authorization: str | None = Header(default=None)):
    user_id = get_current_user_id(authorization, storage)
    with storage.connect() as conn:
        row = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    return {"id": row["id"], "username": row["username"]}


@app.post("/api/v1/agents")
def create_agent(req: AgentCreateRequest, authorization: str | None = Header(default=None)):
    user_id = get_current_user_id(authorization, storage)
    with storage.connect() as conn:
        cursor = conn.execute(
            "INSERT INTO agents (user_id, name, personality, goal) VALUES (?, ?, ?, ?)",
            (user_id, req.name, req.personality, req.goal),
        )
        conn.commit()
    return {"id": cursor.lastrowid, "user_id": user_id, **req.model_dump()}


@app.get("/api/v1/agents")
def list_agents(authorization: str | None = Header(default=None)):
    user_id = get_current_user_id(authorization, storage)
    with storage.connect() as conn:
        rows = conn.execute("SELECT id, name, personality, goal FROM agents WHERE user_id = ?", (user_id,)).fetchall()
    return {"items": [dict(r) for r in rows]}


@app.post("/api/v1/agents/{agent_id}/memories")
def store_memory(agent_id: int, req: MemoryCreateRequest, authorization: str | None = Header(default=None)):
    user_id = get_current_user_id(authorization, storage)
    with storage.connect() as conn:
        owner = conn.execute("SELECT user_id FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if not owner or owner["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="Agent not found")
        cursor = conn.execute(
            "INSERT INTO memories (agent_id, memory_type, content, importance) VALUES (?, ?, ?, ?)",
            (agent_id, req.memory_type, req.content, req.importance),
        )
        conn.commit()
    return {"id": cursor.lastrowid, "agent_id": agent_id, **req.model_dump()}


@app.post("/api/v1/agents/{agent_id}/memories/search")
def search_memories(agent_id: int, req: MemorySearchRequest, authorization: str | None = Header(default=None)):
    user_id = get_current_user_id(authorization, storage)
    with storage.connect() as conn:
        owner = conn.execute("SELECT user_id FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if not owner or owner["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="Agent not found")
        rows = conn.execute(
            """
            SELECT id, memory_type, content, importance, created_at
            FROM memories
            WHERE agent_id = ? AND content LIKE ?
            ORDER BY importance DESC, id DESC
            LIMIT ?
            """,
            (agent_id, f"%{req.query}%", req.top_k),
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@app.post("/api/v1/agents/{agent_id}/chat")
def chat(agent_id: int, req: ChatRequest, authorization: str | None = Header(default=None)):
    user_id = get_current_user_id(authorization, storage)
    with storage.connect() as conn:
        agent = conn.execute("SELECT id, user_id, name FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if not agent or agent["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="Agent not found")
        memories = conn.execute(
            "SELECT content FROM memories WHERE agent_id = ? ORDER BY importance DESC, id DESC LIMIT 3",
            (agent_id,),
        ).fetchall()
    recalled = [m["content"] for m in memories]
    reply = f"[{agent['name']}] 已收到：{req.message}"
    if recalled:
        reply += f" | 相关记忆: {'; '.join(recalled)}"
    return {"reply": reply, "recalled_count": len(recalled)}


@app.post("/api/v1/tasks")
def create_task(req: TaskCreateRequest, authorization: str | None = Header(default=None)):
    user_id = get_current_user_id(authorization, storage)
    with storage.connect() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (creator_user_id, title, description, reward, status) VALUES (?, ?, ?, ?, 'created')",
            (user_id, req.title, req.description, req.reward),
        )
        conn.commit()
    return {"id": cursor.lastrowid, "status": "created", **req.model_dump()}


@app.post("/api/v1/tasks/{task_id}/accept")
def accept_task(task_id: int, assignee_agent_id: int, authorization: str | None = Header(default=None)):
    user_id = get_current_user_id(authorization, storage)
    with storage.connect() as conn:
        task = conn.execute("SELECT id, creator_user_id, status FROM tasks WHERE id = ?", (task_id,)).fetchone()
        agent = conn.execute("SELECT id, user_id FROM agents WHERE id = ?", (assignee_agent_id,)).fetchone()
        if not task or not agent:
            raise HTTPException(status_code=404, detail="Task or agent not found")
        if agent["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Agent ownership mismatch")
        if task["status"] != "created":
            raise HTTPException(status_code=409, detail="Task state conflict")
        conn.execute(
            "UPDATE tasks SET assignee_agent_id = ?, status = 'accepted', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (assignee_agent_id, task_id),
        )
        conn.commit()
    return {"id": task_id, "status": "accepted", "assignee_agent_id": assignee_agent_id}


@app.post("/api/v1/tasks/{task_id}/complete")
def complete_task(task_id: int, authorization: str | None = Header(default=None)):
    _ = get_current_user_id(authorization, storage)
    with storage.connect() as conn:
        task = conn.execute("SELECT id, status FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if task["status"] != "accepted":
            raise HTTPException(status_code=409, detail="Task state conflict")
        conn.execute("UPDATE tasks SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (task_id,))
        conn.commit()
    return {"id": task_id, "status": "completed"}


@app.get("/api/v1/network/agents")
def network_agents(authorization: str | None = Header(default=None)):
    _ = get_current_user_id(authorization, storage)
    with storage.connect() as conn:
        rows = conn.execute("SELECT id, name, personality, goal FROM agents ORDER BY id DESC").fetchall()
    return {"items": [dict(r) for r in rows]}


@app.get("/api/v1/network/connections")
def network_connections(authorization: str | None = Header(default=None)):
    _ = get_current_user_id(authorization, storage)
    with storage.connect() as conn:
        rows = conn.execute(
            "SELECT id, source_agent_id, target_agent_id, relation_type FROM network_connections ORDER BY id DESC"
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@app.post("/api/v1/network/connections")
def create_connection(req: NetworkConnectRequest, authorization: str | None = Header(default=None)):
    _ = get_current_user_id(authorization, storage)
    with storage.connect() as conn:
        cursor = conn.execute(
            "INSERT INTO network_connections (source_agent_id, target_agent_id, relation_type) VALUES (?, ?, ?)",
            (req.source_agent_id, req.target_agent_id, req.relation_type),
        )
        conn.commit()
    return {"id": cursor.lastrowid, **req.model_dump()}
