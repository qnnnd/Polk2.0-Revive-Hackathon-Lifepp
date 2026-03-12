"""
Life++ — Agent Runtime
Core AI reasoning loop with memory augmentation and tool use.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Agent, Message
from app.schemas.schemas import ChatRequest, ChatResponse, MemoryCreate
from app.services.memory_service import MemoryService

AGENT_TOOLS: list[dict] = [
    {
        "name": "search_memory",
        "description": "Search your persistent memory for relevant information about a topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for in memory"},
                "memory_type": {
                    "type": "string",
                    "enum": ["episodic", "semantic", "procedural", "social"],
                },
                "top_k": {"type": "integer", "default": 3},
            },
            "required": ["query"],
        },
    },
    {
        "name": "store_memory",
        "description": "Store important information in your persistent memory for future use.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Information to remember"},
                "memory_type": {
                    "type": "string",
                    "enum": ["episodic", "semantic", "procedural", "social"],
                    "default": "episodic",
                },
                "importance": {"type": "number", "default": 0.6},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["content"],
        },
    },
    {
        "name": "get_network_agents",
        "description": "Discover other AI agents on the Life++ network with specific capabilities.",
        "input_schema": {
            "type": "object",
            "properties": {
                "capability": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
        },
    },
]


class AgentRuntime:
    def __init__(self, agent: Agent, db: AsyncSession):
        self.agent = agent
        self.db = db
        self.memory_svc = MemoryService(db)
        self._client = None
        if settings.ANTHROPIC_API_KEY:
            try:
                import anthropic
                self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            except ImportError:
                pass
        self._memories_used = 0

    async def chat(self, request: ChatRequest) -> ChatResponse:
        session_id = request.session_id or str(uuid.uuid4())
        start_ts = time.monotonic()
        self._memories_used = 0

        history = await self._load_session_history(session_id, limit=20)
        system_prompt = await self._build_system_prompt()
        api_messages = self._format_history(history)
        api_messages.append({"role": "user", "content": request.content})

        assistant_content = await self._run_inference(system_prompt, api_messages)
        latency_ms = int((time.monotonic() - start_ts) * 1000)

        user_msg = Message(
            agent_id=self.agent.id,
            session_id=session_id,
            role="user",
            content=request.content,
        )
        self.db.add(user_msg)

        agent_msg = Message(
            agent_id=self.agent.id,
            session_id=session_id,
            role="agent",
            content=assistant_content,
            latency_ms=latency_ms,
        )
        self.db.add(agent_msg)

        await self.memory_svc.store(
            agent_id=self.agent.id,
            data=MemoryCreate(
                content=f"User said: {request.content[:200]}\nI responded: {assistant_content[:200]}",
                memory_type="episodic",
                importance=0.5,
                tags=["conversation"],
            ),
        )

        await self.db.flush()
        await self.db.refresh(user_msg)
        await self.db.refresh(agent_msg)

        from app.schemas.schemas import MessageResponse
        return ChatResponse(
            session_id=session_id,
            user_message=MessageResponse.model_validate(user_msg),
            agent_message=MessageResponse.model_validate(agent_msg),
            memories_used=self._memories_used,
        )

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        history = await self._load_session_history(request.session_id or str(uuid.uuid4()), limit=20)
        system_prompt = await self._build_system_prompt()
        api_messages = self._format_history(history)
        api_messages.append({"role": "user", "content": request.content})

        if not self._client:
            yield "data: [Demo mode — configure ANTHROPIC_API_KEY for live responses]\n\n"
            yield f"data: I received: '{request.content[:100]}'\n\n"
            yield "data: [DONE]\n\n"
            return

        async with self._client.messages.stream(
            model=self.agent.model,
            max_tokens=settings.MAX_TOKENS,
            system=system_prompt,
            messages=api_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {text}\n\n"
        yield "data: [DONE]\n\n"

    async def _run_inference(
        self, system: str, messages: list[dict], depth: int = 0, max_depth: int = 5,
    ) -> str:
        if not self._client:
            return self._mock_response(messages[-1]["content"])

        if depth >= max_depth:
            return "I've reached the maximum reasoning depth for this request."

        response = await self._client.messages.create(
            model=self.agent.model,
            max_tokens=settings.MAX_TOKENS,
            system=system,
            messages=messages,
            tools=AGENT_TOOLS,
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await self._execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })
            messages = messages + [
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": tool_results},
            ]
            return await self._run_inference(system, messages, depth + 1, max_depth)

        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""

    async def _execute_tool(self, name: str, inputs: Dict[str, Any]) -> Any:
        if name == "search_memory":
            memories = await self.memory_svc.search(
                agent_id=self.agent.id,
                query=inputs["query"],
                memory_type=inputs.get("memory_type"),
                top_k=inputs.get("top_k", 3),
            )
            self._memories_used += len(memories)
            return [
                {"content": m.content, "type": m.memory_type, "importance": m.importance}
                for m in memories
            ]
        elif name == "store_memory":
            await self.memory_svc.store(
                agent_id=self.agent.id,
                data=MemoryCreate(
                    content=inputs["content"],
                    memory_type=inputs.get("memory_type", "episodic"),
                    importance=inputs.get("importance", 0.6),
                    tags=inputs.get("tags", []),
                ),
            )
            return {"stored": True}
        elif name == "get_network_agents":
            from sqlalchemy import select
            from app.models.models import Agent as AgentModel
            q = select(AgentModel).where(
                AgentModel.is_public == True,
                AgentModel.id != self.agent.id,
            ).limit(inputs.get("limit", 5))
            result = await self.db.execute(q)
            agents = result.scalars().all()
            return [
                {"name": a.name, "capabilities": a.capabilities, "status": a.status}
                for a in agents
            ]
        return {"error": f"Unknown tool: {name}"}

    async def _build_system_prompt(self) -> str:
        base = self.agent.system_prompt or (
            f"You are {self.agent.name}, a persistent AI agent on the Life++ network. "
            f"You have long-term memory and can learn and grow over time. "
            f"Your capabilities: {', '.join(self.agent.capabilities or [])}."
        )
        personality = self.agent.personality or {}
        traits = "\n".join(f"- {k}: {v}" for k, v in personality.items())
        if traits:
            base += f"\n\nYour personality traits:\n{traits}"
        base += (
            "\n\nYou have access to tools for searching and storing memories. "
            "Use search_memory to recall relevant past information before responding. "
            "Use store_memory to remember important facts from this conversation."
        )
        return base

    async def _load_session_history(self, session_id: str, limit: int = 20) -> list[Message]:
        from sqlalchemy import select
        q = (
            select(Message)
            .where(Message.agent_id == self.agent.id, Message.session_id == session_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        result = await self.db.execute(q)
        return list(result.scalars().all())

    @staticmethod
    def _format_history(messages: list[Message]) -> list[dict]:
        formatted = []
        for msg in messages:
            role = "user" if msg.role == "user" else "assistant"
            formatted.append({"role": role, "content": msg.content})
        return formatted

    @staticmethod
    def _mock_response(user_content: str) -> str:
        return (
            f"[Demo mode — configure ANTHROPIC_API_KEY for live responses]\n\n"
            f"I received your message: '{user_content[:100]}'. "
            f"I'm your persistent AI agent on the Life++ network. "
            f"I maintain long-term memory and can collaborate with other agents."
        )
