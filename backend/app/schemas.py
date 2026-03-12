from typing import Literal

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=200)


class LoginRequest(BaseModel):
    username: str
    password: str


class AgentCreateRequest(BaseModel):
    name: str
    personality: str = "helpful"
    goal: str = "assist user"


class MemoryCreateRequest(BaseModel):
    memory_type: Literal["episodic", "semantic", "procedural", "social"] = "episodic"
    content: str
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class ChatRequest(BaseModel):
    message: str


class TaskCreateRequest(BaseModel):
    title: str
    description: str
    reward: float = Field(gt=0)


class NetworkConnectRequest(BaseModel):
    source_agent_id: int
    target_agent_id: int
    relation_type: str = "collaborates"
