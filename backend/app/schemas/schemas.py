"""
Life++ Pydantic Schemas
Request/response validation and serialization.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Base ──────────────────────────────────────────────────────────────────

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ── User ──────────────────────────────────────────────────────────────────

class UserCreate(BaseSchema):
    did: str
    username: str = Field(min_length=3, max_length=50)
    display_name: Optional[str] = None
    email: Optional[str] = None

class UserResponse(BaseSchema):
    id: uuid.UUID
    did: str
    username: str
    display_name: Optional[str]
    cog_balance: float
    created_at: datetime

class UserUpdate(BaseSchema):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


# ── Agent ─────────────────────────────────────────────────────────────────

class AgentCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    model: str = "claude-sonnet-4-20250514"
    system_prompt: Optional[str] = None
    personality: Dict[str, Any] = Field(default_factory=dict)
    capabilities: List[str] = Field(default_factory=list)
    is_public: bool = False

class AgentUpdate(BaseSchema):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    personality: Optional[Dict[str, Any]] = None
    capabilities: Optional[List[str]] = None
    is_public: Optional[bool] = None

class AgentResponse(BaseSchema):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    description: Optional[str]
    status: str
    model: str
    capabilities: List[str]
    is_public: bool
    created_at: datetime
    last_active_at: Optional[datetime]
    reputation: Optional[ReputationResponse] = None

class AgentListResponse(BaseSchema):
    agents: List[AgentResponse]
    total: int
    page: int
    page_size: int


# ── Message / Chat ────────────────────────────────────────────────────────

class ChatRequest(BaseSchema):
    content: str = Field(min_length=1, max_length=32_000)
    session_id: Optional[uuid.UUID] = None   # None = start new session
    stream: bool = False

class MessageResponse(BaseSchema):
    id: uuid.UUID
    agent_id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    token_count: Optional[int]
    latency_ms: Optional[int]
    created_at: datetime

class ChatResponse(BaseSchema):
    session_id: uuid.UUID
    user_message: MessageResponse
    agent_message: MessageResponse
    memories_used: int = 0


# ── Memory ────────────────────────────────────────────────────────────────

class MemoryCreate(BaseSchema):
    content: str = Field(min_length=1)
    memory_type: str = "episodic"
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)
    is_shared: bool = False

class MemoryResponse(BaseSchema):
    id: uuid.UUID
    agent_id: uuid.UUID
    memory_type: str
    content: str
    summary: Optional[str]
    importance: float
    strength: float
    access_count: int
    tags: List[str]
    is_shared: bool
    created_at: datetime
    last_accessed_at: datetime
    relevance_score: Optional[float] = None   # Set during retrieval

class MemorySearchRequest(BaseSchema):
    query: str = Field(min_length=1)
    memory_type: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=50)
    min_strength: float = Field(default=0.1, ge=0.0, le=1.0)

class MemorySearchResponse(BaseSchema):
    memories: List[MemoryResponse]
    query: str
    total_found: int


# ── Task ──────────────────────────────────────────────────────────────────

class TaskCreate(BaseSchema):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    priority: str = "normal"
    input_data: Dict[str, Any] = Field(default_factory=dict)
    deadline_at: Optional[datetime] = None
    reward_cog: float = Field(default=0.0, ge=0.0)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        allowed = {"low", "normal", "high", "critical"}
        if v not in allowed:
            raise ValueError(f"priority must be one of {allowed}")
        return v

class TaskResponse(BaseSchema):
    id: uuid.UUID
    agent_id: uuid.UUID
    title: str
    description: Optional[str]
    status: str
    priority: str
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    steps: List[Dict[str, Any]]
    reward_cog: float
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

class TaskListResponse(BaseSchema):
    tasks: List[TaskResponse]
    total: int


# ── Reputation ────────────────────────────────────────────────────────────

class ReputationResponse(BaseSchema):
    score: float
    tasks_completed: int
    tasks_failed: int
    avg_quality_score: float
    total_cog_earned: float
    endorsements: int


# ── Network ───────────────────────────────────────────────────────────────

class NetworkNode(BaseSchema):
    id: uuid.UUID
    name: str
    status: str
    capabilities: List[str]
    reputation_score: float
    x: Optional[float] = None   # layout coords for visualization
    y: Optional[float] = None

class NetworkEdge(BaseSchema):
    from_id: uuid.UUID
    to_id: uuid.UUID
    connection_type: str
    strength: float

class NetworkGraphResponse(BaseSchema):
    nodes: List[NetworkNode]
    edges: List[NetworkEdge]
    total_agents: int
    online_agents: int


# ── WebSocket Events ──────────────────────────────────────────────────────

class WSEvent(BaseSchema):
    event: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
