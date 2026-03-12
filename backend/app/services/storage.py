"""
Life++ — Storage Abstraction Layer
Unified storage interface that wraps SQLAlchemy for SQLite.
Designed to be swappable to PostgreSQL or distributed storage later.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Type, TypeVar
from uuid import uuid4

from sqlalchemy import func, select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import Base

T = TypeVar("T", bound=Base)


class Storage:
    """
    Generic storage operations.
    All methods operate through SQLAlchemy async sessions on SQLite.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, model_class: Type[T], **kwargs) -> T:
        obj = model_class(**kwargs)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, model_class: Type[T], id: str) -> Optional[T]:
        result = await self.db.execute(
            select(model_class).where(model_class.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        model_class: Type[T],
        filters: Optional[Dict[str, Any]] = None,
        order_by=None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[List[T], int]:
        q = select(model_class)
        count_q = select(func.count()).select_from(model_class)

        if filters:
            for key, value in filters.items():
                col = getattr(model_class, key, None)
                if col is not None:
                    q = q.where(col == value)
                    count_q = count_q.where(col == value)

        total = (await self.db.execute(count_q)).scalar_one()

        if order_by is not None:
            q = q.order_by(order_by)
        q = q.offset(offset).limit(limit)

        result = await self.db.execute(q)
        return list(result.scalars().all()), total

    async def update_obj(self, obj: T, **kwargs) -> T:
        for key, value in kwargs.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        await self.db.flush()
        return obj

    async def delete_obj(self, obj: T) -> None:
        await self.db.delete(obj)

    async def count(self, model_class: Type[T], **filters) -> int:
        q = select(func.count()).select_from(model_class)
        for key, value in filters.items():
            col = getattr(model_class, key, None)
            if col is not None:
                q = q.where(col == value)
        return (await self.db.execute(q)).scalar_one()
