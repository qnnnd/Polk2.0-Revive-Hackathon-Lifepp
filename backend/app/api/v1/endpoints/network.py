"""
Life++ API — Network & Auth Endpoints
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.config import settings
from app.db.session import DBSession
from app.models.models import Agent, AgentConnection, AgentReputation, User
from app.schemas.schemas import (
    NetworkEdge, NetworkGraphResponse, NetworkNode,
    UserCreate, UserResponse,
)

network_router = APIRouter(prefix="/network", tags=["Network"])
auth_router = APIRouter(prefix="/auth", tags=["Auth"])


@auth_router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: DBSession):
    existing = await db.execute(select(User).where(User.username == payload.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already taken")

    user = User(
        did=payload.did,
        username=payload.username,
        display_name=payload.display_name,
        email=payload.email,
        wallet_address=payload.wallet_address,
        cog_balance=100.0,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@auth_router.post("/token")
async def login(db: DBSession, username: str = Query(...)):
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = jwt.encode(
        {
            "sub": str(user.id),
            "username": user.username,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"access_token": token, "token_type": "bearer"}


@network_router.get("/graph", response_model=NetworkGraphResponse)
async def network_graph(db: DBSession):
    result = await db.execute(select(Agent).where(Agent.is_public == True))
    agents = list(result.scalars().all())

    nodes = []
    for i, agent in enumerate(agents):
        rep_q = select(AgentReputation).where(AgentReputation.agent_id == agent.id)
        rep = (await db.execute(rep_q)).scalar_one_or_none()
        nodes.append(NetworkNode(
            id=agent.id, name=agent.name, status=agent.status,
            capabilities=agent.capabilities or [],
            reputation_score=rep.score if rep else 1.0,
            x=150 + (i % 5) * 180, y=100 + (i // 5) * 150,
        ))

    conn_result = await db.execute(select(AgentConnection))
    connections = list(conn_result.scalars().all())
    edges = [
        NetworkEdge(
            from_id=c.from_agent_id, to_id=c.to_agent_id,
            connection_type=c.connection_type, strength=c.strength,
        )
        for c in connections
    ]

    online = sum(1 for n in nodes if n.status == "active")
    return NetworkGraphResponse(
        nodes=nodes, edges=edges, total_agents=len(nodes), online_agents=online,
    )


@network_router.get("/stats")
async def network_stats(db: DBSession):
    total = (await db.execute(select(func.count()).select_from(Agent))).scalar_one()
    online = (await db.execute(
        select(func.count()).select_from(Agent).where(Agent.status == "active")
    )).scalar_one()
    return {
        "total_agents": total, "online_agents": online,
        "network_health": "healthy" if online > 0 else "quiet",
    }
