import math

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import Agent, AgentConnection, AgentReputation


class NetworkService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_graph(self) -> dict:
        result = await self.db.execute(
            select(Agent)
            .where(Agent.is_public == True)
            .options(selectinload(Agent.reputation))
        )
        agents = list(result.scalars().all())

        conn_result = await self.db.execute(select(AgentConnection))
        connections = list(conn_result.scalars().all())

        nodes = []
        total_agents = len(agents)
        online_count = 0
        for i, agent in enumerate(agents):
            angle = (2 * math.pi * i) / max(1, total_agents)
            radius = 200
            rep_score = agent.reputation.score if agent.reputation else 1.0
            nodes.append({
                "id": agent.id,
                "name": agent.name,
                "status": agent.status,
                "capabilities": agent.capabilities or [],
                "reputation_score": rep_score,
                "x": round(radius * math.cos(angle), 2),
                "y": round(radius * math.sin(angle), 2),
            })
            if agent.status == "active":
                online_count += 1

        edges = []
        for conn in connections:
            edges.append({
                "from_id": conn.from_agent_id,
                "to_id": conn.to_agent_id,
                "connection_type": conn.connection_type,
                "strength": conn.strength,
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "total_agents": total_agents,
            "online_agents": online_count,
        }

    async def get_stats(self) -> dict:
        total_result = await self.db.execute(select(func.count(Agent.id)))
        total_agents = total_result.scalar() or 0

        online_result = await self.db.execute(
            select(func.count(Agent.id)).where(Agent.status == "active")
        )
        online_agents = online_result.scalar() or 0

        network_health = round(
            min(1.0, online_agents / max(1, total_agents)) * 0.7 + 0.3,
            3,
        )

        return {
            "total_agents": total_agents,
            "online_agents": online_agents,
            "network_health": network_health,
        }
