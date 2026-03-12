from fastapi import APIRouter, HTTPException, Query, status

from app.db.session import DBSession
from app.schemas.schemas import UserCreate, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: DBSession):
    service = AuthService(db)
    user = await service.create_user(data)
    return user


@router.post("/token")
async def login(username: str = Query(...), db: DBSession = None):
    service = AuthService(db)
    user = await service.get_user_by_username(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    token = service.create_token(user)
    return {"access_token": token, "token_type": "bearer"}
