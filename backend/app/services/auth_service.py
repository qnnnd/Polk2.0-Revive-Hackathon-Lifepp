import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import User
from app.schemas.schemas import UserCreate


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, data: UserCreate) -> User:
        result = await self.db.execute(
            select(User).where(User.username == data.username)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Username '{data.username}' is already taken",
            )

        user = User(
            id=uuid.uuid4(),
            did=data.did,
            username=data.username,
            display_name=data.display_name,
            email=data.email,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def get_user_by_username(self, username: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def update_wallet_address(self, user_id: uuid.UUID, wallet_address: Optional[str]) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        user.wallet_address = wallet_address
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    @staticmethod
    def create_token(user: User) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
            "iat": now,
        }
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
