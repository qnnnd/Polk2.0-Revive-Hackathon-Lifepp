import hashlib
import math
import uuid
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import AgentMemory
from app.schemas.schemas import MemoryCreate


class MemoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def store(
        self,
        agent_id: uuid.UUID,
        data: MemoryCreate,
        source_task_id: Optional[uuid.UUID] = None,
    ) -> AgentMemory:
        embedding = await self._embed(data.content)
        summary = self._summarize(data.content)

        memory = AgentMemory(
            id=uuid.uuid4(),
            agent_id=agent_id,
            memory_type=data.memory_type,
            content=data.content,
            summary=summary,
            embedding=embedding,
            importance=data.importance,
            tags=data.tags,
            is_shared=data.is_shared,
            source_task_id=source_task_id,
            last_accessed_at=datetime.now(timezone.utc),
        )
        self.db.add(memory)
        await self.db.flush()
        return memory

    async def search(
        self,
        agent_id: uuid.UUID,
        query: str,
        memory_type: Optional[str] = None,
        top_k: int = 5,
        min_strength: float = 0.1,
    ) -> list[AgentMemory]:
        query_embedding = await self._embed(query)

        stmt = (
            select(
                AgentMemory,
                AgentMemory.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .where(
                AgentMemory.agent_id == agent_id,
                AgentMemory.strength >= min_strength,
            )
        )
        if memory_type:
            stmt = stmt.where(AgentMemory.memory_type == memory_type)

        stmt = stmt.order_by("distance").limit(top_k * 3)
        result = await self.db.execute(stmt)
        rows = result.all()

        now = datetime.now(timezone.utc)
        scored_memories = []
        for memory_obj, distance in rows:
            similarity = max(0.0, 1.0 - distance)

            created = memory_obj.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_hours = max(1.0, (now - created).total_seconds() / 3600)
            recency = 1.0 / (1.0 + math.log(age_hours))

            composite = similarity * 0.5 + memory_obj.importance * 0.3 + recency * 0.2
            scored_memories.append((memory_obj, composite))

        scored_memories.sort(key=lambda x: x[1], reverse=True)
        top_memories = scored_memories[:top_k]

        memory_ids = [m.id for m, _ in top_memories]
        if memory_ids:
            await self.db.execute(
                update(AgentMemory)
                .where(AgentMemory.id.in_(memory_ids))
                .values(
                    access_count=AgentMemory.access_count + 1,
                    last_accessed_at=now,
                )
            )

        results = []
        for memory_obj, score in top_memories:
            memory_obj.relevance_score = round(score, 4)
            results.append(memory_obj)
        return results

    async def get_all(
        self,
        agent_id: uuid.UUID,
        memory_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AgentMemory], int]:
        base = select(AgentMemory).where(AgentMemory.agent_id == agent_id)
        if memory_type:
            base = base.where(AgentMemory.memory_type == memory_type)

        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.db.execute(
            base.order_by(AgentMemory.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        memories = list(result.scalars().all())
        return memories, total

    async def consolidate(self, agent_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            select(AgentMemory).where(AgentMemory.agent_id == agent_id)
        )
        memories = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        pruned = 0
        strengthened = 0

        for memory in memories:
            new_strength = self._compute_strength(memory, now)
            if new_strength < 0.05:
                await self.db.delete(memory)
                pruned += 1
            else:
                if memory.access_count > 3:
                    new_strength = min(1.0, new_strength * 1.2)
                    strengthened += 1
                memory.strength = new_strength

        await self.db.flush()
        return {
            "pruned": pruned,
            "strengthened": strengthened,
            "total": len(memories) - pruned,
        }

    async def _embed(self, text: str) -> list[float]:
        if settings.OPENAI_API_KEY:
            try:
                import httpx

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.openai.com/v1/embeddings",
                        headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                        json={"input": text, "model": settings.EMBEDDING_MODEL},
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data["data"][0]["embedding"]
            except Exception:
                pass

        return self._mock_embed(text)

    @staticmethod
    def _mock_embed(text: str) -> list[float]:
        hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()
        rng = np.random.RandomState(
            int.from_bytes(hash_bytes[:4], byteorder="big")
        )
        vec = rng.randn(1536).astype(np.float64)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    @staticmethod
    def _compute_strength(memory: AgentMemory, now: datetime) -> float:
        created = memory.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        elapsed_hours = max(0.0, (now - created).total_seconds() / 3600)
        stability = max(1.0, memory.access_count * 2.0)
        return math.exp(-elapsed_hours / (stability * 24))

    @staticmethod
    def _summarize(content: str, max_length: int = 200) -> str:
        if len(content) <= max_length:
            return content
        truncated = content[:max_length]
        last_space = truncated.rfind(" ")
        if last_space > max_length // 2:
            truncated = truncated[:last_space]
        return truncated + "..."
