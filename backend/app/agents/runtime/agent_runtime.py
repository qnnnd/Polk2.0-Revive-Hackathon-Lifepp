"""
Life++ — Agent Runtime
Core AI reasoning loop with memory augmentation and tool use.
Integrates with Anthropic Claude via the official SDK.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Agent, Message, MessageRoleEnum
from app.schemas.schemas import ChatRequest, ChatResponse, MemoryCreate
from app.services.memory_service import MemoryService


# ── Built-in Agent Tools ──────────────────────────────────────────────────

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
                    "description": "Type of memory to search (optional)",
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
                "importance": {
                    "type": "number",
                    "description": "Importance 0.0–1.0, higher = remembered longer",
                    "default": 0.6,
                },
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
                "capability": {"type": "string", "description": "Required capability, e.g. 'legal'"},
                "limit": {"type": "integer", "default": 5},
            },
        },
    },
]


class AgentRuntime:
    """
    Stateful agent execution engine.
    Wraps Anthropic Claude with tool use, memory, and session management.
    """

    def __init__(self, agent: Agent, db: AsyncSession):
        self.agent = agent
        self.db = db
        self.memory_svc = MemoryService(db)
        self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None
        self._memories_used = 0

    # ── Public interface ──────────────────────────────────────────────────

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """
        Process a user message through the full cognitive loop:
        1. Retrieve relevant memories
        2. Build enriched system prompt
        3. Call LLM (with tool use loop)
        4. Store interaction as episodic memory
        5. Persist messages to database
        """
        session_id = request.session_id or uuid.uuid4()
        start_ts = time.monotonic()
        self._memories_used = 0

        # Retrieve recent conversation context from DB
        history = await self._load_session_history(session_id, limit=20)

        # Build system prompt with memory context
        system_prompt = await self._build_system_prompt()

        # Build message list for the API
        api_messages = self._format_history(history)
        api_messages.append({"role": "user", "content": request.content})

        # Execute LLM with agentic tool loop
        assistant_content = await self._run_inference(system_prompt, api_messages)

        latency_ms = int((time.monotonic() - start_ts) * 1000)

        # Persist user message
        user_msg = Message(
            agent_id=self.agent.id,
            session_id=session_id,
            role=MessageRoleEnum.user,
            content=request.content,
        )
        self.db.add(user_msg)

        # Persist agent response
        agent_msg = Message(
            agent_id=self.agent.id,
            session_id=session_id,
            role=MessageRoleEnum.agent,
            content=assistant_content,
            latency_ms=latency_ms,
        )
        self.db.add(agent_msg)

        # Store interaction as episodic memory
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

    async def chat_stream(
        self,
        request: ChatRequest,
    ) -> AsyncIterator[str]:
        """Streaming variant — yields SSE-compatible chunks."""
        history = await self._load_session_history(request.session_id or uuid.uuid4(), limit=20)
        system_prompt = await self._build_system_prompt()
        api_messages = self._format_history(history)
        api_messages.append({"role": "user", "content": request.content})

        if not self._client:
            yield "data: Agent runtime unavailable — configure ANTHROPIC_API_KEY\n\n"
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

    # ── LLM Inference ─────────────────────────────────────────────────────

    async def _run_inference(
        self,
        system: str,
        messages: list[dict],
        depth: int = 0,
        max_depth: int = 5,
    ) -> str:
        """
        Agentic inference loop with tool use.
        Recursively handles tool calls until the model produces a final text response.
        """
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

        # If model wants to use tools, execute them and recurse
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

            # Append assistant's tool call message + tool results
            messages = messages + [
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": tool_results},
            ]
            return await self._run_inference(system, messages, depth + 1, max_depth)

        # Extract final text
        for block in response.content:
            if hasattr(block, "text"):
                return block.text

        return ""

    async def _execute_tool(self, name: str, inputs: Dict[str, Any]) -> Any:
        """Dispatch tool calls to their implementations."""
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
            # In production: query registry service
            return [
                {"name": "Nexus", "capabilities": ["legal"], "reputation": 4.6},
                {"name": "Cipher", "capabilities": ["coding", "security"], "reputation": 4.9},
            ]

        return {"error": f"Unknown tool: {name}"}

    # ── Helpers ───────────────────────────────────────────────────────────

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

    async def _load_session_history(
        self,
        session_id: uuid.UUID,
        limit: int = 20,
    ) -> list[Message]:
        from sqlalchemy import select
        q = (
            select(Message)
            .where(
                Message.agent_id == self.agent.id,
                Message.session_id == session_id,
            )
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        result = await self.db.execute(q)
        return result.scalars().all()

    @staticmethod
    def _format_history(messages: list[Message]) -> list[dict]:
        formatted = []
        for msg in messages:
            role_str = msg.role.value if hasattr(msg.role, 'value') else str(msg.role)
            role = "user" if role_str == "user" else "assistant"
            formatted.append({"role": role, "content": msg.content})
        return formatted

    @staticmethod
    def _mock_response(user_content: str) -> str:
        """Fallback response when no API key is configured."""
        return (
            f"[Demo mode — configure ANTHROPIC_API_KEY for live responses]\n\n"
            f"I received your message: '{user_content[:100]}'. "
            f"I'm your persistent AI agent on the Life++ network. "
            f"I maintain long-term memory and can collaborate with other agents."
        )
