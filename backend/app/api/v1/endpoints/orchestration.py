"""
Life++ API — Multi-Agent Orchestration
Parallel and Sequential collaboration strategies.
"""
from __future__ import annotations

import asyncio
import time
from typing import List

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.v1.deps import CurrentUser
from app.db.session import DBSession
from app.models.models import Agent
from app.agents.runtime.agent_runtime import AgentRuntime
from app.schemas.schemas import ChatRequest, OrchestrationRequest, OrchestrationResult

router = APIRouter(prefix="/network", tags=["Network & Orchestration"])


@router.post("/orchestrate", response_model=OrchestrationResult)
async def orchestrate(payload: OrchestrationRequest, db: DBSession, current_user: CurrentUser):
    """
    Multi-agent orchestration: dispatch a task to multiple agents.
    Strategies: parallel (all at once) or sequential (chain results).
    """
    start = time.monotonic()

    if payload.agent_ids:
        q = select(Agent).where(Agent.id.in_(payload.agent_ids))
    else:
        q = select(Agent).where(Agent.is_public == True, Agent.status != "terminated")
        if payload.capability_filter:
            q = q.where(Agent.capabilities.contains(f'"{payload.capability_filter}"'))
        q = q.limit(payload.max_agents)

    result = await db.execute(q)
    agents = list(result.scalars().all())

    if not agents:
        raise HTTPException(status_code=404, detail="No agents found for orchestration")

    if payload.strategy == "parallel":
        results = await _parallel_execute(agents, payload.task_description, db)
    elif payload.strategy == "sequential":
        results = await _sequential_execute(agents, payload.task_description, db)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {payload.strategy}")

    elapsed = int((time.monotonic() - start) * 1000)
    return OrchestrationResult(
        strategy=payload.strategy,
        agents_used=[a.name for a in agents],
        results=results,
        total_time_ms=elapsed,
    )


async def _parallel_execute(agents: List[Agent], task: str, db) -> list[dict]:
    """Execute task on all agents sequentially to avoid session conflicts with SQLite."""
    results = []
    for agent in agents:
        runtime = AgentRuntime(agent=agent, db=db)
        request = ChatRequest(content=task)
        try:
            response = await runtime.chat(request)
            results.append({
                "agent": agent.name,
                "agent_id": agent.id,
                "response": response.agent_message.content,
                "latency_ms": response.agent_message.latency_ms,
                "memories_used": response.memories_used,
            })
        except Exception as e:
            results.append({"agent": agent.name, "agent_id": agent.id, "error": str(e)})
    return results


async def _sequential_execute(agents: List[Agent], task: str, db) -> list[dict]:
    """Execute task sequentially, passing each agent's output as context to the next."""
    results = []
    accumulated_context = task

    for i, agent in enumerate(agents):
        prompt = accumulated_context
        if i > 0:
            prompt = (
                f"Previous agent's analysis:\n{results[-1].get('response', '')}\n\n"
                f"Original task: {task}\n\n"
                f"Please build upon the previous analysis and add your perspective."
            )

        runtime = AgentRuntime(agent=agent, db=db)
        request = ChatRequest(content=prompt)
        try:
            response = await runtime.chat(request)
            result = {
                "agent": agent.name,
                "agent_id": agent.id,
                "step": i + 1,
                "response": response.agent_message.content,
                "latency_ms": response.agent_message.latency_ms,
                "memories_used": response.memories_used,
            }
            results.append(result)
            accumulated_context = response.agent_message.content
        except Exception as e:
            results.append({"agent": agent.name, "agent_id": agent.id, "step": i + 1, "error": str(e)})

    return results
