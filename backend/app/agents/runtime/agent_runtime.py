import json
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Agent, Message
from app.schemas.schemas import MemoryCreate
from app.services.memory_service import MemoryService


class AgentRuntime:
    def __init__(self, db: AsyncSession, agent: Agent):
        self.db = db
        self.agent = agent
        self.memory_service = MemoryService(db)

    async def chat(self, content: str, session_id: Optional[uuid.UUID] = None) -> dict:
        if session_id is None:
            session_id = uuid.uuid4()

        start_time = time.time()

        user_message = Message(
            id=uuid.uuid4(),
            agent_id=self.agent.id,
            session_id=session_id,
            role="user",
            content=content,
        )
        self.db.add(user_message)
        await self.db.flush()

        history = await self._load_history(session_id)
        memory_context = await self._get_memory_context(content)
        memories_used = len(memory_context)

        system_prompt = self._build_system_prompt(memory_context)
        messages = self._build_messages(history, content)

        response_text = await self._run_inference(system_prompt, messages)

        latency_ms = int((time.time() - start_time) * 1000)

        agent_message = Message(
            id=uuid.uuid4(),
            agent_id=self.agent.id,
            session_id=session_id,
            role="agent",
            content=response_text,
            token_count=len(response_text.split()),
            latency_ms=latency_ms,
        )
        self.db.add(agent_message)
        await self.db.flush()

        await self._store_interaction_memory(content, response_text)

        return {
            "session_id": session_id,
            "user_message": user_message,
            "agent_message": agent_message,
            "memories_used": memories_used,
        }

    async def chat_stream(
        self, content: str, session_id: Optional[uuid.UUID] = None
    ) -> AsyncGenerator[str, None]:
        if session_id is None:
            session_id = uuid.uuid4()

        user_message = Message(
            id=uuid.uuid4(),
            agent_id=self.agent.id,
            session_id=session_id,
            role="user",
            content=content,
        )
        self.db.add(user_message)
        await self.db.flush()

        memory_context = await self._get_memory_context(content)
        system_prompt = self._build_system_prompt(memory_context)
        history = await self._load_history(session_id, exclude_id=user_message.id)
        messages = self._build_messages(history, content)

        yield f"data: {json.dumps({'type': 'session', 'session_id': str(session_id)})}\n\n"

        full_response = ""

        if settings.ANTHROPIC_API_KEY:
            try:
                import anthropic

                client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
                async with client.messages.stream(
                    model=self.agent.model or "claude-sonnet-4-20250514",
                    max_tokens=settings.MAX_TOKENS,
                    system=system_prompt,
                    messages=messages,
                ) as stream:
                    async for text in stream.text_stream:
                        full_response += text
                        yield f"data: {json.dumps({'type': 'content', 'text': text})}\n\n"
            except Exception as e:
                full_response = f"Error during streaming: {str(e)}"
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        else:
            mock_response = self._mock_response(content)
            for word in mock_response.split(" "):
                chunk = word + " "
                full_response += chunk
                yield f"data: {json.dumps({'type': 'content', 'text': chunk})}\n\n"

        agent_message = Message(
            id=uuid.uuid4(),
            agent_id=self.agent.id,
            session_id=session_id,
            role="agent",
            content=full_response.strip(),
            token_count=len(full_response.split()),
        )
        self.db.add(agent_message)
        await self.db.flush()

        await self._store_interaction_memory(content, full_response.strip())

        yield f"data: {json.dumps({'type': 'done', 'message_id': str(agent_message.id)})}\n\n"

    async def _load_history(
        self, session_id: uuid.UUID, exclude_id: Optional[uuid.UUID] = None, limit: int = 20
    ) -> list[Message]:
        stmt = (
            select(Message)
            .where(
                Message.agent_id == self.agent.id,
                Message.session_id == session_id,
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        if exclude_id is not None:
            stmt = stmt.where(Message.id != exclude_id)

        result = await self.db.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse()
        return messages

    async def _get_memory_context(self, query: str, top_k: int = 3) -> list:
        try:
            memories = await self.memory_service.search(
                agent_id=self.agent.id,
                query=query,
                top_k=top_k,
            )
            return memories
        except Exception:
            return []

    def _build_system_prompt(self, memory_context: list) -> str:
        base_prompt = self.agent.system_prompt or (
            f"You are {self.agent.name}, an AI agent in the Life++ network. "
            "You are helpful, knowledgeable, and collaborative."
        )

        personality = self.agent.personality or {}
        if personality:
            traits = ", ".join(f"{k}: {v}" for k, v in personality.items())
            base_prompt += f"\n\nPersonality traits: {traits}"

        if memory_context:
            memory_text = "\n".join(
                f"- [{m.memory_type}] {m.summary or m.content[:150]}"
                for m in memory_context
            )
            base_prompt += f"\n\nRelevant memories:\n{memory_text}"

        return base_prompt

    def _build_messages(self, history: list[Message], current_content: str) -> list[dict]:
        messages = []
        for msg in history:
            role = "user" if msg.role == "user" else "assistant"
            if msg.content:
                messages.append({"role": role, "content": msg.content})
        messages.append({"role": "user", "content": current_content})
        return messages

    async def _run_inference(self, system_prompt: str, messages: list[dict]) -> str:
        if settings.ANTHROPIC_API_KEY:
            try:
                import anthropic

                client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

                tools = [
                    {
                        "name": "search_memory",
                        "description": "Search the agent's memory for relevant information",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The search query",
                                },
                            },
                            "required": ["query"],
                        },
                    },
                    {
                        "name": "store_memory",
                        "description": "Store new information in the agent's memory",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "content": {
                                    "type": "string",
                                    "description": "The content to store",
                                },
                                "importance": {
                                    "type": "number",
                                    "description": "Importance score from 0 to 1",
                                },
                            },
                            "required": ["content"],
                        },
                    },
                    {
                        "name": "get_network_agents",
                        "description": "Get information about other agents in the Life++ network",
                        "input_schema": {
                            "type": "object",
                            "properties": {},
                        },
                    },
                ]

                response = await client.messages.create(
                    model=self.agent.model or "claude-sonnet-4-20250514",
                    max_tokens=settings.MAX_TOKENS,
                    system=system_prompt,
                    messages=messages,
                    tools=tools,
                )

                while response.stop_reason == "tool_use":
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            result = await self._handle_tool_call(
                                block.name, block.input
                            )
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": json.dumps(result),
                                }
                            )

                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": tool_results})

                    response = await client.messages.create(
                        model=self.agent.model or "claude-sonnet-4-20250514",
                        max_tokens=settings.MAX_TOKENS,
                        system=system_prompt,
                        messages=messages,
                        tools=tools,
                    )

                text_parts = [
                    block.text for block in response.content if hasattr(block, "text")
                ]
                return " ".join(text_parts) if text_parts else "I processed your request."

            except Exception as e:
                return f"I encountered an issue with the AI service: {str(e)}. Let me respond based on my knowledge."

        return self._mock_response(messages[-1]["content"] if messages else "")

    async def _handle_tool_call(self, tool_name: str, tool_input: dict) -> dict:
        if tool_name == "search_memory":
            query = tool_input.get("query", "")
            memories = await self.memory_service.search(
                agent_id=self.agent.id, query=query, top_k=3
            )
            return {
                "results": [
                    {"content": m.content, "importance": m.importance}
                    for m in memories
                ]
            }
        elif tool_name == "store_memory":
            content_text = tool_input.get("content", "")
            importance = tool_input.get("importance", 0.5)
            memory_data = MemoryCreate(
                content=content_text, importance=importance
            )
            await self.memory_service.store(self.agent.id, memory_data)
            return {"status": "stored"}
        elif tool_name == "get_network_agents":
            from app.services.network_service import NetworkService

            network_svc = NetworkService(self.db)
            graph = await network_svc.get_graph()
            return {
                "agents": [
                    {"name": n["name"], "status": n["status"]}
                    for n in graph.get("nodes", [])[:10]
                ]
            }
        return {"error": f"Unknown tool: {tool_name}"}

    async def _store_interaction_memory(self, user_input: str, agent_response: str) -> None:
        try:
            summary = f"User asked: {user_input[:100]}. Agent responded: {agent_response[:100]}"
            memory_data = MemoryCreate(
                content=summary,
                memory_type="episodic",
                importance=0.3,
                tags=["conversation"],
            )
            await self.memory_service.store(self.agent.id, memory_data)
        except Exception:
            pass

    @staticmethod
    def _mock_response(user_content: str) -> str:
        content_lower = user_content.lower()
        if "hello" in content_lower or "hi" in content_lower:
            return "Hello! I'm an AI agent in the Life++ network. How can I help you today?"
        elif "help" in content_lower:
            return (
                "I can help you with various tasks! I can search my memory, "
                "store new information, and connect with other agents in the network. "
                "What would you like to do?"
            )
        elif "memory" in content_lower or "remember" in content_lower:
            return (
                "I have a sophisticated memory system that allows me to store and recall "
                "information. I use episodic, semantic, and procedural memory types. "
                "Would you like me to search for something specific?"
            )
        else:
            return (
                f"I've processed your message about '{user_content[:50]}'. "
                "As an AI agent in the Life++ network, I'm here to assist you. "
                "I can help with tasks, share knowledge, and collaborate with other agents."
            )
