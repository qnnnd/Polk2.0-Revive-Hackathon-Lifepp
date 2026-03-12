-- ============================================================
-- Life++ Database Schema
-- PostgreSQL 15+
-- Author: Life++ Database Engineering Team
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";  -- pgvector for AI embeddings

-- NOTE: Using TEXT instead of ENUM types for ORM compatibility.

-- ────────────────────────────────────────────────────────────
-- USERS
-- ────────────────────────────────────────────────────────────

CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    did           TEXT UNIQUE NOT NULL,          -- Decentralized Identifier
    username      TEXT UNIQUE NOT NULL,
    email         TEXT UNIQUE,
    display_name  TEXT,
    avatar_url    TEXT,
    public_key    TEXT,                           -- Ed25519 public key
    cog_balance   NUMERIC(20, 8) NOT NULL DEFAULT 0,
    is_active     BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_did ON users(did);
CREATE INDEX idx_users_username ON users(username);

-- ────────────────────────────────────────────────────────────
-- AGENTS
-- ────────────────────────────────────────────────────────────

CREATE TABLE agents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'idle',
    model           TEXT NOT NULL DEFAULT 'claude-sonnet-4-20250514',
    system_prompt   TEXT,
    personality     JSONB NOT NULL DEFAULT '{}',
    capabilities    TEXT[] NOT NULL DEFAULT '{}',
    endpoint_url    TEXT,                          -- P2P network endpoint
    public_key      TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    is_public       BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at  TIMESTAMPTZ
);

CREATE INDEX idx_agents_owner_id    ON agents(owner_id);
CREATE INDEX idx_agents_status      ON agents(status);
CREATE INDEX idx_agents_capabilities ON agents USING GIN(capabilities);
CREATE INDEX idx_agents_is_public   ON agents(is_public) WHERE is_public = true;

-- ────────────────────────────────────────────────────────────
-- AGENT MEMORY
-- ────────────────────────────────────────────────────────────

CREATE TABLE agent_memories (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id      UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    memory_type   TEXT NOT NULL DEFAULT 'episodic',
    content       TEXT NOT NULL,
    summary       TEXT,                          -- LLM-compressed summary
    embedding     vector(1536),                  -- OpenAI/Claude embedding
    importance    FLOAT NOT NULL DEFAULT 0.5 CHECK (importance >= 0 AND importance <= 1),
    strength      FLOAT NOT NULL DEFAULT 1.0 CHECK (strength >= 0 AND strength <= 1),
    access_count  INTEGER NOT NULL DEFAULT 0,
    tags          TEXT[] NOT NULL DEFAULT '{}',
    source_task_id UUID,                         -- Which task created this memory
    is_shared     BOOLEAN NOT NULL DEFAULT false,
    metadata      JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_memories_agent_id      ON agent_memories(agent_id);
CREATE INDEX idx_memories_type          ON agent_memories(memory_type);
CREATE INDEX idx_memories_importance    ON agent_memories(importance DESC);
CREATE INDEX idx_memories_tags          ON agent_memories USING GIN(tags);
CREATE INDEX idx_memories_embedding     ON agent_memories USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ────────────────────────────────────────────────────────────
-- TASKS
-- ────────────────────────────────────────────────────────────

CREATE TABLE tasks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id        UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    parent_task_id  UUID REFERENCES tasks(id),   -- For sub-task hierarchies
    title           TEXT NOT NULL,
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    priority        TEXT NOT NULL DEFAULT 'normal',
    input_data      JSONB NOT NULL DEFAULT '{}',
    output_data     JSONB,
    error_message   TEXT,
    steps           JSONB NOT NULL DEFAULT '[]',  -- Execution steps log
    assigned_agents UUID[] NOT NULL DEFAULT '{}', -- Collaborating agent IDs
    reward_cog      NUMERIC(20, 8) NOT NULL DEFAULT 0,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    deadline_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tasks_agent_id      ON tasks(agent_id);
CREATE INDEX idx_tasks_status        ON tasks(status);
CREATE INDEX idx_tasks_priority      ON tasks(priority);
CREATE INDEX idx_tasks_parent        ON tasks(parent_task_id) WHERE parent_task_id IS NOT NULL;
CREATE INDEX idx_tasks_assigned      ON tasks USING GIN(assigned_agents);

-- ────────────────────────────────────────────────────────────
-- MESSAGES  (chat history per agent)
-- ────────────────────────────────────────────────────────────

CREATE TABLE messages (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id      UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    session_id    UUID NOT NULL,                 -- Groups messages into conversations
    role          TEXT NOT NULL,
    content       TEXT NOT NULL,
    tool_calls    JSONB,                         -- LLM tool use payloads
    tool_results  JSONB,
    token_count   INTEGER,
    latency_ms    INTEGER,
    metadata      JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_agent_id    ON messages(agent_id);
CREATE INDEX idx_messages_session_id  ON messages(session_id);
CREATE INDEX idx_messages_created_at  ON messages(created_at DESC);

-- ────────────────────────────────────────────────────────────
-- AGENT REPUTATION
-- ────────────────────────────────────────────────────────────

CREATE TABLE agent_reputations (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id          UUID UNIQUE NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    score             FLOAT NOT NULL DEFAULT 1.0 CHECK (score >= 0 AND score <= 5),
    tasks_completed   INTEGER NOT NULL DEFAULT 0,
    tasks_failed      INTEGER NOT NULL DEFAULT 0,
    tasks_cancelled   INTEGER NOT NULL DEFAULT 0,
    avg_quality_score FLOAT NOT NULL DEFAULT 0,
    total_cog_earned  NUMERIC(20, 8) NOT NULL DEFAULT 0,
    endorsements      INTEGER NOT NULL DEFAULT 0,
    penalties         INTEGER NOT NULL DEFAULT 0,
    computed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Reputation events ledger
CREATE TABLE reputation_events (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id    UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    event_type  TEXT NOT NULL,    -- 'task_complete', 'task_fail', 'endorsement', 'penalty'
    delta       FLOAT NOT NULL,
    reason      TEXT,
    task_id     UUID REFERENCES tasks(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rep_events_agent_id ON reputation_events(agent_id);
CREATE INDEX idx_rep_events_type     ON reputation_events(event_type);

-- ────────────────────────────────────────────────────────────
-- AGENT CONNECTIONS  (P2P graph)
-- ────────────────────────────────────────────────────────────

CREATE TABLE agent_connections (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_agent_id   UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    to_agent_id     UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    connection_type TEXT NOT NULL DEFAULT 'peer',   -- 'peer', 'collaborator', 'delegate'
    strength        FLOAT NOT NULL DEFAULT 1.0,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(from_agent_id, to_agent_id)
);

CREATE INDEX idx_connections_from ON agent_connections(from_agent_id);
CREATE INDEX idx_connections_to   ON agent_connections(to_agent_id);

-- ────────────────────────────────────────────────────────────
-- MARKETPLACE  (Task listings)
-- ────────────────────────────────────────────────────────────

CREATE TABLE task_listings (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    poster_agent_id       UUID NOT NULL REFERENCES agents(id),
    title                 TEXT NOT NULL,
    description           TEXT NOT NULL,
    required_capabilities TEXT[] NOT NULL DEFAULT '{}',
    reward_cog            NUMERIC(20, 8) NOT NULL,
    status                TEXT NOT NULL DEFAULT 'open',
    winning_agent_id      UUID REFERENCES agents(id),
    winning_task_id       UUID REFERENCES tasks(id),
    tx_hash               TEXT,
    deadline_at           TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ────────────────────────────────────────────────────────────
-- AUDIT / UPDATED_AT TRIGGERS
-- ────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at    BEFORE UPDATE ON users    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_agents_updated_at   BEFORE UPDATE ON agents   FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_tasks_updated_at    BEFORE UPDATE ON tasks    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_rep_updated_at      BEFORE UPDATE ON agent_reputations FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ────────────────────────────────────────────────────────────
-- MEMORY DECAY FUNCTION
-- ────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION decay_memory_strength()
RETURNS void AS $$
BEGIN
    -- Ebbinghaus forgetting curve applied hourly via pg_cron
    UPDATE agent_memories
    SET strength = GREATEST(
        0.05,
        strength * EXP(
            -0.01 / GREATEST(importance * (1 + LN(COALESCE(access_count, 1) + 1)), 0.1)
            * EXTRACT(EPOCH FROM (NOW() - last_accessed_at)) / 3600
        )
    )
    WHERE last_accessed_at < NOW() - INTERVAL '1 hour'
      AND strength > 0.05;
END;
$$ LANGUAGE plpgsql;
