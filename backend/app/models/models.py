"""
Life++ ORM Models
SQLAlchemy 2.0 declarative models mapping to PostgreSQL schema.
"""
import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY, Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base

import enum

class AgentStatusEnum(str, enum.Enum):
    active = "active"
    idle = "idle"
    sleeping = "sleeping"
    error = "error"
    terminated = "terminated"

class TaskStatusEnum(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"

class TaskPriorityEnum(str, enum.Enum):
    low = "low"
    normal = "normal"
    high = "high"
    critical = "critical"

class MemoryTypeEnum(str, enum.Enum):
    episodic = "episodic"
    semantic = "semantic"
    procedural = "procedural"
    social = "social"
    working = "working"

class MessageRoleEnum(str, enum.Enum):
    user = "user"
    agent = "agent"
    system = "system"


def uuid_pk():
    return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

def now_col():
    return Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ────────────────────────────────────────────────────────────
# USER
# ────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id           = uuid_pk()
    did          = Column(Text, unique=True, nullable=False)
    username     = Column(Text, unique=True, nullable=False)
    email        = Column(Text, unique=True)
    display_name = Column(Text)
    avatar_url   = Column(Text)
    public_key   = Column(Text)
    cog_balance  = Column(Numeric(20, 8), nullable=False, default=0)
    is_active    = Column(Boolean, nullable=False, default=True)
    created_at   = now_col()
    updated_at   = now_col()

    agents = relationship("Agent", back_populates="owner", cascade="all, delete-orphan")


# ────────────────────────────────────────────────────────────
# AGENT
# ────────────────────────────────────────────────────────────

class Agent(Base):
    __tablename__ = "agents"

    id            = uuid_pk()
    owner_id      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name          = Column(Text, nullable=False)
    description   = Column(Text)
    status        = Column(Enum(AgentStatusEnum, name="agent_status", create_type=False), nullable=False, default=AgentStatusEnum.idle)
    model         = Column(Text, nullable=False, default="claude-sonnet-4-20250514")
    system_prompt = Column(Text)
    personality   = Column(JSONB, nullable=False, default=dict)
    capabilities  = Column(ARRAY(Text), nullable=False, default=list)
    endpoint_url  = Column(Text)
    public_key    = Column(Text)
    metadata_     = Column("metadata", JSONB, nullable=False, default=dict)
    is_public     = Column(Boolean, nullable=False, default=False)
    created_at    = now_col()
    updated_at    = now_col()
    last_active_at = Column(DateTime(timezone=True))

    owner       = relationship("User", back_populates="agents")
    memories    = relationship("AgentMemory", back_populates="agent", cascade="all, delete-orphan")
    tasks       = relationship("Task", back_populates="agent", cascade="all, delete-orphan", foreign_keys="Task.agent_id")
    messages    = relationship("Message", back_populates="agent", cascade="all, delete-orphan")
    reputation  = relationship("AgentReputation", back_populates="agent", uselist=False, cascade="all, delete-orphan")


# ────────────────────────────────────────────────────────────
# AGENT MEMORY
# ────────────────────────────────────────────────────────────

class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id               = uuid_pk()
    agent_id         = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    memory_type      = Column(Enum(MemoryTypeEnum, name="memory_type", create_type=False), nullable=False, default=MemoryTypeEnum.episodic)
    content          = Column(Text, nullable=False)
    summary          = Column(Text)
    embedding        = Column(Vector(1536))
    importance       = Column(Float, nullable=False, default=0.5)
    strength         = Column(Float, nullable=False, default=1.0)
    access_count     = Column(Integer, nullable=False, default=0)
    tags             = Column(ARRAY(Text), nullable=False, default=list)
    source_task_id   = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    is_shared        = Column(Boolean, nullable=False, default=False)
    metadata_        = Column("metadata", JSONB, nullable=False, default=dict)
    created_at       = now_col()
    last_accessed_at = now_col()

    agent = relationship("Agent", back_populates="memories")


# ────────────────────────────────────────────────────────────
# TASK
# ────────────────────────────────────────────────────────────

class Task(Base):
    __tablename__ = "tasks"

    id              = uuid_pk()
    agent_id        = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    parent_task_id  = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    title           = Column(Text, nullable=False)
    description     = Column(Text)
    status          = Column(Enum(TaskStatusEnum, name="task_status", create_type=False), nullable=False, default=TaskStatusEnum.pending)
    priority        = Column(Enum(TaskPriorityEnum, name="task_priority", create_type=False), nullable=False, default=TaskPriorityEnum.normal)
    input_data      = Column(JSONB, nullable=False, default=dict)
    output_data     = Column(JSONB)
    error_message   = Column(Text)
    steps           = Column(JSONB, nullable=False, default=list)
    assigned_agents = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    reward_cog      = Column(Numeric(20, 8), nullable=False, default=0)
    started_at      = Column(DateTime(timezone=True))
    completed_at    = Column(DateTime(timezone=True))
    deadline_at     = Column(DateTime(timezone=True))
    created_at      = now_col()
    updated_at      = now_col()

    agent    = relationship("Agent", back_populates="tasks", foreign_keys=[agent_id])
    subtasks = relationship("Task", backref="parent", remote_side="Task.id")


# ────────────────────────────────────────────────────────────
# MESSAGE
# ────────────────────────────────────────────────────────────

class Message(Base):
    __tablename__ = "messages"

    id           = uuid_pk()
    agent_id     = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    session_id   = Column(UUID(as_uuid=True), nullable=False)
    role         = Column(Enum(MessageRoleEnum, name="message_role", create_type=False), nullable=False)
    content      = Column(Text, nullable=False)
    tool_calls   = Column(JSONB)
    tool_results = Column(JSONB)
    token_count  = Column(Integer)
    latency_ms   = Column(Integer)
    metadata_    = Column("metadata", JSONB, nullable=False, default=dict)
    created_at   = now_col()

    agent = relationship("Agent", back_populates="messages")


# ────────────────────────────────────────────────────────────
# AGENT REPUTATION
# ────────────────────────────────────────────────────────────

class AgentReputation(Base):
    __tablename__ = "agent_reputations"

    id                = uuid_pk()
    agent_id          = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), unique=True, nullable=False)
    score             = Column(Float, nullable=False, default=1.0)
    tasks_completed   = Column(Integer, nullable=False, default=0)
    tasks_failed      = Column(Integer, nullable=False, default=0)
    tasks_cancelled   = Column(Integer, nullable=False, default=0)
    avg_quality_score = Column(Float, nullable=False, default=0)
    total_cog_earned  = Column(Numeric(20, 8), nullable=False, default=0)
    endorsements      = Column(Integer, nullable=False, default=0)
    penalties         = Column(Integer, nullable=False, default=0)
    computed_at       = now_col()
    updated_at        = now_col()

    agent = relationship("Agent", back_populates="reputation")


# ────────────────────────────────────────────────────────────
# AGENT CONNECTION
# ────────────────────────────────────────────────────────────

class AgentConnection(Base):
    __tablename__ = "agent_connections"
    __table_args__ = (UniqueConstraint("from_agent_id", "to_agent_id"),)

    id              = uuid_pk()
    from_agent_id   = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    to_agent_id     = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    connection_type = Column(Text, nullable=False, default="peer")
    strength        = Column(Float, nullable=False, default=1.0)
    metadata_       = Column("metadata", JSONB, nullable=False, default=dict)
    created_at      = now_col()
