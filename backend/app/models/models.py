"""
Life++ ORM Models
SQLAlchemy 2.0 declarative models — SQLite-compatible.
Uses JSON strings for arrays/dicts; plain String for enums.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint,
    TypeDecorator, event, func,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


# ── Custom Types for SQLite ────────────────────────────────────────────

class JSONList(TypeDecorator):
    """Store Python lists as JSON strings in SQLite."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return "[]"
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        return json.loads(value)


class JSONDict(TypeDecorator):
    """Store Python dicts as JSON strings in SQLite."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return "{}"
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return {}
        return json.loads(value)


class JSONFloatList(TypeDecorator):
    """Store embedding vectors as JSON float arrays in SQLite."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── USER ───────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id           = Column(String(36), primary_key=True, default=new_uuid)
    did          = Column(Text, unique=True, nullable=False)
    username     = Column(Text, unique=True, nullable=False)
    email        = Column(Text, unique=True, nullable=True)
    display_name = Column(Text, nullable=True)
    avatar_url   = Column(Text, nullable=True)
    public_key   = Column(Text, nullable=True)
    wallet_address = Column(Text, nullable=True)
    cog_balance  = Column(Float, nullable=False, default=100.0)
    is_active    = Column(Boolean, nullable=False, default=True)
    created_at   = Column(DateTime, nullable=False, default=utcnow)
    updated_at   = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    agents = relationship("Agent", back_populates="owner", cascade="all, delete-orphan")


# ── AGENT ──────────────────────────────────────────────────────────────

class Agent(Base):
    __tablename__ = "agents"

    id            = Column(String(36), primary_key=True, default=new_uuid)
    owner_id      = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name          = Column(Text, nullable=False)
    description   = Column(Text, nullable=True)
    status        = Column(String(20), nullable=False, default="idle")
    model         = Column(Text, nullable=False, default="claude-sonnet-4-20250514")
    system_prompt = Column(Text, nullable=True)
    personality   = Column(JSONDict, nullable=False, default=dict)
    capabilities  = Column(JSONList, nullable=False, default=list)
    endpoint_url  = Column(Text, nullable=True)
    public_key    = Column(Text, nullable=True)
    on_chain_id   = Column(Text, nullable=True)
    metadata_     = Column("metadata", JSONDict, nullable=False, default=dict)
    is_public     = Column(Boolean, nullable=False, default=False)
    created_at    = Column(DateTime, nullable=False, default=utcnow)
    updated_at    = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    last_active_at = Column(DateTime, nullable=True)

    owner       = relationship("User", back_populates="agents")
    memories    = relationship("AgentMemory", back_populates="agent", cascade="all, delete-orphan")
    tasks       = relationship("Task", back_populates="agent", cascade="all, delete-orphan", foreign_keys="Task.agent_id")
    messages    = relationship("Message", back_populates="agent", cascade="all, delete-orphan")
    reputation  = relationship("AgentReputation", back_populates="agent", uselist=False, cascade="all, delete-orphan")


# ── AGENT MEMORY ───────────────────────────────────────────────────────

class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id               = Column(String(36), primary_key=True, default=new_uuid)
    agent_id         = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    memory_type      = Column(String(20), nullable=False, default="episodic")
    content          = Column(Text, nullable=False)
    summary          = Column(Text, nullable=True)
    embedding        = Column(JSONFloatList, nullable=True)
    importance       = Column(Float, nullable=False, default=0.5)
    strength         = Column(Float, nullable=False, default=1.0)
    access_count     = Column(Integer, nullable=False, default=0)
    tags             = Column(JSONList, nullable=False, default=list)
    source_task_id   = Column(String(36), ForeignKey("tasks.id"), nullable=True)
    is_shared        = Column(Boolean, nullable=False, default=False)
    metadata_        = Column("metadata", JSONDict, nullable=False, default=dict)
    created_at       = Column(DateTime, nullable=False, default=utcnow)
    last_accessed_at = Column(DateTime, nullable=False, default=utcnow)

    agent = relationship("Agent", back_populates="memories")


# ── TASK ───────────────────────────────────────────────────────────────

class Task(Base):
    __tablename__ = "tasks"

    id              = Column(String(36), primary_key=True, default=new_uuid)
    agent_id        = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    parent_task_id  = Column(String(36), ForeignKey("tasks.id"), nullable=True)
    title           = Column(Text, nullable=False)
    description     = Column(Text, nullable=True)
    status          = Column(String(20), nullable=False, default="pending")
    priority        = Column(String(20), nullable=False, default="normal")
    input_data      = Column(JSONDict, nullable=False, default=dict)
    output_data     = Column(JSONDict, nullable=True)
    error_message   = Column(Text, nullable=True)
    steps           = Column(JSONList, nullable=False, default=list)
    assigned_agents = Column(JSONList, nullable=False, default=list)
    reward_cog      = Column(Float, nullable=False, default=0)
    escrow_status   = Column(String(20), nullable=False, default="none")
    tx_hash         = Column(Text, nullable=True)
    started_at      = Column(DateTime, nullable=True)
    completed_at    = Column(DateTime, nullable=True)
    deadline_at     = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, nullable=False, default=utcnow)
    updated_at      = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    agent    = relationship("Agent", back_populates="tasks", foreign_keys=[agent_id])
    subtasks = relationship("Task", backref="parent", remote_side="Task.id")


# ── MESSAGE ────────────────────────────────────────────────────────────

class Message(Base):
    __tablename__ = "messages"

    id           = Column(String(36), primary_key=True, default=new_uuid)
    agent_id     = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    session_id   = Column(String(36), nullable=False)
    role         = Column(String(20), nullable=False)
    content      = Column(Text, nullable=False)
    tool_calls   = Column(JSONDict, nullable=True)
    tool_results = Column(JSONDict, nullable=True)
    token_count  = Column(Integer, nullable=True)
    latency_ms   = Column(Integer, nullable=True)
    metadata_    = Column("metadata", JSONDict, nullable=False, default=dict)
    created_at   = Column(DateTime, nullable=False, default=utcnow)

    agent = relationship("Agent", back_populates="messages")


# ── AGENT REPUTATION ───────────────────────────────────────────────────

class AgentReputation(Base):
    __tablename__ = "agent_reputations"

    id                = Column(String(36), primary_key=True, default=new_uuid)
    agent_id          = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), unique=True, nullable=False)
    score             = Column(Float, nullable=False, default=1.0)
    tasks_completed   = Column(Integer, nullable=False, default=0)
    tasks_failed      = Column(Integer, nullable=False, default=0)
    tasks_cancelled   = Column(Integer, nullable=False, default=0)
    avg_quality_score = Column(Float, nullable=False, default=0)
    total_cog_earned  = Column(Float, nullable=False, default=0)
    endorsements      = Column(Integer, nullable=False, default=0)
    penalties         = Column(Integer, nullable=False, default=0)
    computed_at       = Column(DateTime, nullable=False, default=utcnow)
    updated_at        = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    agent = relationship("Agent", back_populates="reputation")


# ── REPUTATION EVENTS ─────────────────────────────────────────────────

class ReputationEvent(Base):
    __tablename__ = "reputation_events"

    id         = Column(String(36), primary_key=True, default=new_uuid)
    agent_id   = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(Text, nullable=False)
    delta      = Column(Float, nullable=False)
    reason     = Column(Text, nullable=True)
    task_id    = Column(String(36), ForeignKey("tasks.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)


# ── AGENT CONNECTION ───────────────────────────────────────────────────

class AgentConnection(Base):
    __tablename__ = "agent_connections"
    __table_args__ = (UniqueConstraint("from_agent_id", "to_agent_id"),)

    id              = Column(String(36), primary_key=True, default=new_uuid)
    from_agent_id   = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    to_agent_id     = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    connection_type = Column(Text, nullable=False, default="peer")
    strength        = Column(Float, nullable=False, default=1.0)
    metadata_       = Column("metadata", JSONDict, nullable=False, default=dict)
    created_at      = Column(DateTime, nullable=False, default=utcnow)


# ── TASK LISTING (Marketplace) ─────────────────────────────────────────

class TaskListing(Base):
    __tablename__ = "task_listings"

    id                    = Column(String(36), primary_key=True, default=new_uuid)
    poster_agent_id       = Column(String(36), ForeignKey("agents.id"), nullable=False)
    title                 = Column(Text, nullable=False)
    description           = Column(Text, nullable=False)
    required_capabilities = Column(JSONList, nullable=False, default=list)
    reward_cog            = Column(Float, nullable=False)
    status                = Column(Text, nullable=False, default="open")
    winning_agent_id      = Column(String(36), ForeignKey("agents.id"), nullable=True)
    winning_task_id       = Column(String(36), ForeignKey("tasks.id"), nullable=True)
    tx_hash               = Column(Text, nullable=True)
    deadline_at           = Column(DateTime, nullable=True)
    created_at            = Column(DateTime, nullable=False, default=utcnow)
