"""
Life++ — Memory Service
In-memory vector search with cosine similarity (no pgvector dependency).
"""
from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import List, Optional

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import AgentMemory
from app.schemas.schemas import MemoryCreate


class MemoryService:
    """
    Manages agent memories with in-memory cosine similarity search.
    Follows the spec: similarity 50%, importance 30%, recency 20%.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def store(
        self,
        agent_id: str,
        data: MemoryCreate,
        source_task_id: Optional[str] = None,
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

    async def search(
        self,
        agent_id: str,
        query: str,
        memory_type: Optional[str] = None,
        top_k: int = 5,
        min_strength: float = 0.1,
    ) -> List[AgentMemory]:
        """
        In-memory cosine similarity search with composite ranking:
        similarity * 0.5 + importance * 0.3 + recency * 0.2
        """
        query_embedding = await self._embed(query)
        query_vec = np.array(query_embedding, dtype=np.float32)

        q = select(AgentMemory).where(
            AgentMemory.agent_id == agent_id,
            AgentMemory.strength >= min_strength,
        )
        if memory_type:
            q = q.where(AgentMemory.memory_type == memory_type)

        result = await self.db.execute(q)
        candidates = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        scored = []
        for mem in candidates:
            if mem.embedding is None:
                continue

            mem_vec = np.array(mem.embedding, dtype=np.float32)
            similarity = self._cosine_similarity(query_vec, mem_vec)

            hours_ago = (now - mem.last_accessed_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            recency = max(0, 1.0 - hours_ago / 720)  # decay over 30 days

            composite = similarity * 0.5 + mem.importance * 0.3 + recency * 0.2
            scored.append((mem, composite, similarity))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        memories = []
        for mem, composite, sim in top:
            mem.__dict__["relevance_score"] = round(sim, 4)
            mem.access_count += 1
            mem.last_accessed_at = now
            memories.append(mem)

        await self.db.flush()
        return memories

    async def get_all(
        self,
        agent_id: str,
        memory_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[AgentMemory], int]:
        from sqlalchemy import func

        q = select(AgentMemory).where(AgentMemory.agent_id == agent_id)
        if memory_type:
            q = q.where(AgentMemory.memory_type == memory_type)

        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar_one()

        q = q.order_by(AgentMemory.importance.desc(), AgentMemory.created_at.desc())
        q = q.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(q)
        return list(result.scalars().all()), total

    async def consolidate(self, agent_id: str) -> dict:
        q = select(AgentMemory).where(AgentMemory.agent_id == agent_id)
        result = await self.db.execute(q)
        memories = list(result.scalars().all())

        pruned = 0
        strengthened = 0

        for mem in memories:
            new_strength = self._compute_strength(
                current_strength=mem.strength,
                importance=mem.importance,
                access_count=mem.access_count,
                last_accessed_at=mem.last_accessed_at,
            )
            if new_strength < 0.05 and mem.importance < 0.3:
                await self.db.delete(mem)
                pruned += 1
            else:
                if new_strength > mem.strength:
                    strengthened += 1
                mem.strength = new_strength

        await self.db.flush()
        return {"pruned": pruned, "strengthened": strengthened, "total": len(memories)}

    # ── Private helpers ───────────────────────────────────────────────

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    async def _embed(self, text: str) -> list[float]:
        """
        Generate embedding vector. Uses OpenAI if available, else deterministic mock.
        """
        if settings.OPENAI_API_KEY:
            try:
                import openai
                client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                response = await client.embeddings.create(
                    input=text, model=settings.EMBEDDING_MODEL,
                )
                return response.data[0].embedding
            except Exception:
                pass

        dim = settings.EMBEDDING_DIM
        seed_bytes = hashlib.sha256(text.encode()).digest()
        rng = np.random.default_rng(list(seed_bytes[:8]))
        vec = rng.standard_normal(dim).astype(np.float32)
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
        if len(content) <= max_length:
            return content
        return content[:max_length - 3] + "..."
