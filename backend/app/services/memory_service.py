"""
Life++ — Memory Service
Vector-based memory storage, retrieval, and lifecycle management.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import AgentMemory
from app.schemas.schemas import MemoryCreate, MemoryResponse


class MemoryService:
    """
    Manages the full lifecycle of agent memories:
    - Storage with embedding generation
    - Semantic retrieval via cosine similarity
    - Strength decay (Ebbinghaus forgetting curve)
    - Consolidation (pruning + association)
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._embedding_client = None   # Lazy-initialized

    # ── Write ─────────────────────────────────────────────────────────────

    async def store(
        self,
        agent_id: uuid.UUID,
        data: MemoryCreate,
        source_task_id: Optional[uuid.UUID] = None,
    ) -> AgentMemory:
        embedding = await self._embed(data.content)
        summary = self._summarize(data.content)

        memory = AgentMemory(
            agent_id=agent_id,
            memory_type=data.memory_type,
            content=data.content,
            summary=summary,
            embedding=embedding,
            importance=data.importance,
            tags=data.tags,
            is_shared=data.is_shared,
            source_task_id=source_task_id,
        )
        self.db.add(memory)
        await self.db.flush()
        return memory

    # ── Read ──────────────────────────────────────────────────────────────

    async def search(
        self,
        agent_id: uuid.UUID,
        query: str,
        memory_type: Optional[str] = None,
        top_k: int = 5,
        min_strength: float = 0.1,
    ) -> list[AgentMemory]:
        """
        Retrieve memories by semantic similarity + recency + importance.
        Uses pgvector cosine distance for fast ANN search.
        """
        query_embedding = await self._embed(query)

        q = (
            select(
                AgentMemory,
                (1 - AgentMemory.embedding.cosine_distance(query_embedding)).label("similarity"),
            )
            .where(
                AgentMemory.agent_id == agent_id,
                AgentMemory.strength >= min_strength,
            )
            .order_by(
                # Composite ranking: similarity + recency + importance
                (
                    (1 - AgentMemory.embedding.cosine_distance(query_embedding)) * 0.5
                    + AgentMemory.importance * 0.3
                    + func.extract(
                        "epoch",
                        AgentMemory.last_accessed_at
                    ) / 1e9 * 0.2
                ).desc()
            )
            .limit(top_k)
        )

        if memory_type:
            q = q.where(AgentMemory.memory_type == memory_type)

        result = await self.db.execute(q)
        rows = result.all()

        memories = []
        for row in rows:
            mem = row[0]
            sim = float(row[1]) if row[1] is not None else 0.0
            # Attach relevance score as transient attribute
            mem.__dict__["relevance_score"] = sim
            # Update access tracking
            mem.access_count += 1
            mem.last_accessed_at = datetime.now(timezone.utc)
            memories.append(mem)

        await self.db.flush()
        return memories

    async def get_all(
        self,
        agent_id: uuid.UUID,
        memory_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AgentMemory], int]:
        q = select(AgentMemory).where(AgentMemory.agent_id == agent_id)
        if memory_type:
            q = q.where(AgentMemory.memory_type == memory_type)

        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar_one()

        q = q.order_by(AgentMemory.importance.desc(), AgentMemory.created_at.desc())
        q = q.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(q)
        return result.scalars().all(), total

    # ── Maintenance ───────────────────────────────────────────────────────

    async def consolidate(self, agent_id: uuid.UUID) -> dict:
        """
        Memory consolidation pass:
        1. Apply Ebbinghaus decay to all memories
        2. Prune memories below survival threshold
        3. Return consolidation stats
        """
        q = select(AgentMemory).where(AgentMemory.agent_id == agent_id)
        result = await self.db.execute(q)
        memories = result.scalars().all()

        pruned = 0
        strengthened = 0

        for mem in memories:
            new_strength = self._compute_strength(
                current_strength=mem.strength,
                importance=mem.importance,
                access_count=mem.access_count,
                last_accessed_at=mem.last_accessed_at,
            )
            mem.strength = new_strength

            if new_strength < 0.05 and mem.importance < 0.3:
                await self.db.delete(mem)
                pruned += 1
            elif new_strength > mem.strength:
                strengthened += 1

        await self.db.flush()
        return {"pruned": pruned, "strengthened": strengthened, "total": len(memories)}

    # ── Private helpers ───────────────────────────────────────────────────

    async def _embed(self, text: str) -> list[float]:
        """
        Generate embedding vector for text.
        Production: calls OpenAI text-embedding-3-small or Anthropic.
        Development: deterministic mock using hash projection.
        """
        if settings.OPENAI_API_KEY:
            try:
                import openai
                client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                response = await client.embeddings.create(
                    input=text,
                    model=settings.EMBEDDING_MODEL,
                )
                return response.data[0].embedding
            except Exception:
                pass  # Fall through to mock

        # Deterministic mock embedding (1536-dim)
        import hashlib
        seed_bytes = hashlib.sha256(text.encode()).digest()
        rng = np.random.default_rng(list(seed_bytes[:8]))
        vec = rng.standard_normal(1536).astype(np.float32)
        # L2 normalize
        norm = np.linalg.norm(vec)
        return (vec / norm).tolist() if norm > 0 else vec.tolist()

    @staticmethod
    def _compute_strength(
        current_strength: float,
        importance: float,
        access_count: int,
        last_accessed_at: datetime,
    ) -> float:
        """Ebbinghaus forgetting curve: R = e^(-t/S)."""
        hours_elapsed = (
            datetime.now(timezone.utc) - last_accessed_at.replace(tzinfo=timezone.utc)
        ).total_seconds() / 3600

        stability = importance * (1 + math.log1p(max(access_count, 0)))
        raw = math.exp(-0.01 * hours_elapsed / max(stability, 0.01))
        return max(0.0, min(1.0, raw * importance))

    @staticmethod
    def _summarize(content: str, max_length: int = 200) -> str:
        """Simple extractive summary for storage efficiency."""
        if len(content) <= max_length:
            return content
        return content[:max_length - 3] + "..."
