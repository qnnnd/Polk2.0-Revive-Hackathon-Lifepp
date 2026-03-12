"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { Topbar } from "@/components/ui/Topbar";
import { useAgent, useChatWithAgent, useMemories } from "@/hooks/useApi";
import type { UUID, Memory } from "@/types";

interface ChatMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  latency_ms?: number | null;
  memories_used?: number;
  timestamp: Date;
}

export default function AgentDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const { data: agent, isLoading, error } = useAgent(id);
  const { data: memoriesData } = useMemories(id);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<UUID | undefined>();
  const bottomRef = useRef<HTMLDivElement>(null);
  const chatMutation = useChatWithAgent(id);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatMutation.isPending]);

  const sendMessage = useCallback(async () => {
    const content = input.trim();
    if (!content || chatMutation.isPending) return;
    setInput("");

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const response = await chatMutation.mutateAsync({
        content,
        session_id: sessionId,
      });
      setSessionId(response.session_id);

      const agentMsg: ChatMessage = {
        id: response.agent_message.id,
        role: "agent",
        content: response.agent_message.content,
        latency_ms: response.agent_message.latency_ms,
        memories_used: response.memories_used,
        timestamp: new Date(response.agent_message.created_at),
      };
      setMessages((prev) => [...prev, agentMsg]);
    } catch (err: any) {
      toast.error(err.message ?? "Failed to send message");
      setMessages((prev) => prev.filter((m) => m.id !== userMsg.id));
      setInput(content);
    }
  }, [input, sessionId, chatMutation]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (isLoading) {
    return (
      <>
        <Topbar title="AgentChat" description="Loading agent..." />
        <div className="page-content" style={{ textAlign: "center", padding: 60, color: "var(--text-3)" }}>
          Loading agent…
        </div>
      </>
    );
  }

  if (error || !agent) {
    return (
      <>
        <Topbar title="AgentChat" description="Agent not found" />
        <div className="page-content" style={{ textAlign: "center", padding: 60 }}>
          <p style={{ color: "var(--text-3)" }}>Agent not found</p>
          <Link href="/dashboard" style={{ color: "var(--brand)", fontSize: 13, marginTop: 12, display: "inline-block" }}>
            ← Back to Dashboard
          </Link>
        </div>
      </>
    );
  }

  const memories: Memory[] = memoriesData?.memories ?? [];

  return (
    <>
      <Topbar title="AgentChat" description={`Chatting with ${agent.name}`} />
      <div className="page-content">
        <Link href="/dashboard" style={{ color: "var(--brand)", fontSize: 12, display: "inline-block", marginBottom: 16 }}>
          ← Back to Dashboard
        </Link>

        <div className="chat-layout">
          {/* Left: Chat shell */}
          <div className="card chat-shell" style={{ padding: 0 }}>
            <div className="chat-header">
              <h3 style={{ margin: 0 }}>AgentChat</h3>
              <span className="tag green">SSE Ready</span>
            </div>

            <div className="chat-messages">
              {messages.length === 0 && (
                <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-3)", fontSize: 13 }}>
                  Start a conversation with {agent.name}
                </div>
              )}
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`message ${msg.role}`}
                >
                  {msg.content}
                </div>
              ))}
              {chatMutation.isPending && (
                <div className="typing-indicator">
                  <span /><span /><span />
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            <div className="chat-input-area">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={`Message ${agent.name}…`}
                rows={1}
              />
              <button
                onClick={sendMessage}
                disabled={!input.trim() || chatMutation.isPending}
              >
                Send
              </button>
            </div>
          </div>

          {/* Right: Agent info + memories */}
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {/* Current Agent card */}
            <div className="card">
              <h3>Current Agent</h3>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                <div className="avatar" style={{
                  width: 44, height: 44, borderRadius: 14,
                  background: "linear-gradient(135deg, var(--brand), var(--brand-2))",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontWeight: 700, fontSize: 18,
                }}>
                  {agent.name[0]}
                </div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>{agent.name}</div>
                  <div style={{ fontSize: 12, color: "var(--text-3)" }}>
                    {agent.capabilities?.join(", ") || "general"}
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 16 }}>
                <span className={`tag ${agent.status === "active" ? "green" : "amber"}`}>
                  {agent.status}
                </span>
                <span className="tag">★ {agent.reputation?.score?.toFixed(1) ?? "0.0"}</span>
                <span className="tag cyan">Tasks: {agent.reputation?.tasks_completed ?? 0}</span>
                <span className="tag brand2">Memory: {memories.length}</span>
              </div>

              <div className="metric-grid">
                <div className="metric-item">
                  <div className="label">Session ID</div>
                  <div className="value">{sessionId ? sessionId.slice(0, 8) : "—"}</div>
                </div>
                <div className="metric-item">
                  <div className="label">Runtime</div>
                  <div className="value">Active</div>
                </div>
                <div className="metric-item">
                  <div className="label">Memory Tool</div>
                  <div className="value" style={{ color: "var(--green)" }}>Enabled</div>
                </div>
                <div className="metric-item">
                  <div className="label">Network Tool</div>
                  <div className="value" style={{ color: "var(--green)" }}>Enabled</div>
                </div>
              </div>
            </div>

            {/* Session Memories card */}
            <div className="card" style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
              <h3>Session Memories</h3>
              <div style={{ flex: 1, overflowY: "auto" }}>
                {memories.length === 0 ? (
                  <p style={{ color: "var(--text-3)", fontSize: 12 }}>
                    No memories yet. Chat to generate memories.
                  </p>
                ) : (
                  memories.slice(0, 10).map((mem) => (
                    <div key={mem.id} className="memory-item">
                      <div className="mem-type">{mem.memory_type}</div>
                      {mem.content}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
