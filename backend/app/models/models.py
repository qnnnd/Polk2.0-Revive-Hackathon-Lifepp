"""
Life++ ORM Models
SQLAlchemy 2.0 declarative models — PostgreSQL with pgvector.
Uses native JSONB, ARRAY, UUID, and Vector types.
"""
import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    did = Column(Text, unique=True, nullable=False)
    username = Column(Text, unique=True, nullable=False)
    email = Column(Text, unique=True, nullable=True)
    display_name = Column(Text, nullable=True)
    avatar_url = Column(Text, nullable=True)
    public_key = Column(Text, nullable=True)
    wallet_address = Column(Text, nullable=True)  # EVM address for Revive COG / chain ops
    cog_balance = Column(Numeric(20, 8), nullable=False, default=0, server_default="0")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    agents = relationship("Agent", back_populates="owner", cascade="all, delete-orphan")


class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="idle")
    model = Column(Text, nullable=False, default="claude-sonnet-4-20250514")
    system_prompt = Column(Text, nullable=True)
    personality = Column(JSONB, nullable=False, default=dict, server_default="{}")
    capabilities = Column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    endpoint_url = Column(Text, nullable=True)
    public_key = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict, server_default="{}")
    is_public = Column(Boolean, nullable=False, default=False, server_default="false")
    chain_registered_tx_hash = Column(Text, nullable=True)  # AgentRegistry.register tx on Revive
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    last_active_at = Column(DateTime(timezone=True), nullable=True)

    owner = relationship("User", back_populates="agents")
    memories = relationship("AgentMemory", back_populates="agent", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="agent", cascade="all, delete-orphan", foreign_keys="Task.agent_id")
    messages = relationship("Message", back_populates="agent", cascade="all, delete-orphan")
    reputation = relationship("AgentReputation", back_populates="agent", uselist=False, cascade="all, delete-orphan")


class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    memory_type = Column(String(20), nullable=False, default="episodic")
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    embedding = Column(Vector(1536), nullable=True)
    importance = Column(Float, nullable=False, default=0.5)
    strength = Column(Float, nullable=False, default=1.0)
    access_count = Column(Integer, nullable=False, default=0)
    tags = Column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    source_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    is_shared = Column(Boolean, nullable=False, default=False)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict, server_default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_accessed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    agent = relationship("Agent", back_populates="memories")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    parent_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    priority = Column(String(20), nullable=False, default="normal")
    input_data = Column(JSONB, nullable=False, default=dict, server_default="{}")
    output_data = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    steps = Column(JSONB, nullable=False, default=list, server_default="[]")
    assigned_agents = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default="{}")
    reward_cog = Column(Numeric(20, 8), nullable=False, default=0, server_default="0")
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    deadline_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    agent = relationship("Agent", back_populates="tasks", foreign_keys=[agent_id])
    subtasks = relationship("Task", backref="parent", remote_side="Task.id")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(UUID(as_uuid=True), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    tool_calls = Column(JSONB, nullable=True)
    tool_results = Column(JSONB, nullable=True)
    token_count = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict, server_default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    agent = relationship("Agent", back_populates="messages")


class AgentReputation(Base):
    __tablename__ = "agent_reputations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), unique=True, nullable=False)
    score = Column(Float, nullable=False, default=1.0)
    tasks_completed = Column(Integer, nullable=False, default=0)
    tasks_failed = Column(Integer, nullable=False, default=0)
    tasks_cancelled = Column(Integer, nullable=False, default=0)
    avg_quality_score = Column(Float, nullable=False, default=0)
    total_cog_earned = Column(Numeric(20, 8), nullable=False, default=0, server_default="0")
    endorsements = Column(Integer, nullable=False, default=0)
    penalties = Column(Integer, nullable=False, default=0)
    computed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    agent = relationship("Agent", back_populates="reputation")


class ReputationEvent(Base):
    __tablename__ = "reputation_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(Text, nullable=False)
    delta = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TaskListing(Base):
    __tablename__ = "task_listings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    poster_agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    required_capabilities = Column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    reward_cog = Column(Numeric(20, 8), nullable=False)
    status = Column(Text, nullable=False, default="open")
    winning_agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    winning_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    chain_task_id = Column(BigInteger, nullable=True)  # TaskMarket task id on Revive
    tx_hash = Column(Text, nullable=True)
    deadline_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AgentConnection(Base):
    __tablename__ = "agent_connections"
    __table_args__ = (UniqueConstraint("from_agent_id", "to_agent_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    to_agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    connection_type = Column(String(20), nullable=False, default="peer")
    strength = Column(Float, nullable=False, default=1.0)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict, server_default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
