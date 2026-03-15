import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserCreate(BaseModel):
    did: str
    username: str
    display_name: Optional[str] = None
    email: Optional[str] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    did: str
    username: str
    display_name: Optional[str] = None
    wallet_address: Optional[str] = None
    cog_balance: float
    created_at: datetime


class UserWalletUpdate(BaseModel):
    wallet_address: Optional[str] = None


class ReputationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: float
    tasks_completed: int
    tasks_failed: int
    avg_quality_score: float
    total_cog_earned: float
    endorsements: int


class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    model: str = "claude-sonnet-4-20250514"
    system_prompt: Optional[str] = None
    personality: Dict[str, Any] = {}
    capabilities: List[str] = []
    is_public: bool = False


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    personality: Optional[Dict[str, Any]] = None
    capabilities: Optional[List[str]] = None
    is_public: Optional[bool] = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    description: Optional[str] = None
    status: str
    model: str
    capabilities: List[str] = []
    is_public: bool
    created_at: datetime
    last_active_at: Optional[datetime] = None
    reputation: Optional[ReputationResponse] = None


class AgentListResponse(BaseModel):
    agents: List[AgentResponse]
    total: int
    page: int
    page_size: int


class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=32000)
    session_id: Optional[uuid.UUID] = None
    stream: bool = False


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    session_id: Optional[uuid.UUID] = None
    role: str
    content: Optional[str] = None
    token_count: Optional[int] = None
    latency_ms: Optional[int] = None
    created_at: datetime


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    user_message: MessageResponse
    agent_message: MessageResponse
    memories_used: int = 0


class MemoryCreate(BaseModel):
    content: str
    memory_type: str = "episodic"
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: List[str] = []
    is_shared: bool = False


class MemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    memory_type: str
    content: str
    summary: Optional[str] = None
    importance: float
    strength: float
    access_count: int
    tags: List[str] = []
    is_shared: bool
    created_at: datetime
    last_accessed_at: Optional[datetime] = None
    relevance_score: Optional[float] = None


class MemorySearchRequest(BaseModel):
    query: str
    memory_type: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=50)
    min_strength: float = 0.1


class MemorySearchResponse(BaseModel):
    memories: List[MemoryResponse]
    query: str
    total_found: int


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "normal"
    input_data: Dict[str, Any] = {}
    deadline_at: Optional[datetime] = None
    reward_cog: float = Field(default=0.0, ge=0.0)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        allowed = {"low", "normal", "high", "critical"}
        if v not in allowed:
            raise ValueError(f"priority must be one of {allowed}")
        return v


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    input_data: Dict[str, Any] = {}
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    steps: List[Any] = []
    reward_cog: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int


# ── Marketplace ────────────────────────────────────────────────────────

class TaskListingCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1, default="No description")
    required_capabilities: List[str] = Field(default_factory=list)
    reward_cog: float = Field(default=0.0, ge=0.0)
    deadline_at: Optional[datetime] = None

class ChainTxParams(BaseModel):
    """Tx params for publisher to sign createTask in wallet (publisher pays IVE)."""
    to: str
    data: str
    value: str
    chain_id: int


class ChainCreatedUpdate(BaseModel):
    """Body for PATCH /tasks/:id/chain_created after publisher signed createTask."""
    tx_hash: str = Field(min_length=1)


class TaskListingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    poster_agent_id: uuid.UUID
    title: str
    description: str
    required_capabilities: List[str]
    reward_cog: float
    status: str
    winning_agent_id: Optional[uuid.UUID] = None
    chain_task_id: Optional[int] = None
    tx_hash: Optional[str] = None
    deadline_at: Optional[datetime] = None
    created_at: datetime
    chain_tx_params: Optional[ChainTxParams] = None


# ── Network ────────────────────────────────────────────────────────────

class NetworkNode(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    capabilities: List[str] = []
    reputation_score: float
    x: Optional[float] = None
    y: Optional[float] = None


class NetworkEdge(BaseModel):
    from_id: uuid.UUID
    to_id: uuid.UUID
    connection_type: str
    strength: float


class NetworkGraphResponse(BaseModel):
    nodes: List[NetworkNode]
    edges: List[NetworkEdge]
    total_agents: int
    online_agents: int
