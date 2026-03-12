"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useChatWithAgent } from "@/hooks/useApi";
import type { ChatResponse, Message, UUID } from "@/types";

interface ChatMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  latency_ms?: number | null;
  memories_used?: number;
  timestamp: Date;
}

interface AgentChatProps {
  agentId: UUID;
  agentName: string;
}

export function AgentChat({ agentId, agentName }: AgentChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<UUID | undefined>();
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const chatMutation = useChatWithAgent(agentId);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatMutation.isPending]);

  const sendMessage = useCallback(async () => {
    const content = input.trim();
    if (!content || chatMutation.isPending) return;

    setInput("");

    // Optimistically add user message
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
      // Remove optimistic user message on failure
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

  return (
    <div className="flex flex-col h-full bg-surface rounded-2xl border border-border overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-surface2">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent to-accent2 flex items-center justify-center font-bold text-sm font-syne">
            {agentName[0]}
          </div>
          <div>
            <p className="font-semibold text-sm">{agentName}</p>
            <p className="text-xs text-muted font-mono">
              {sessionId ? `Session ${sessionId.slice(0, 8)}` : "New session"}
            </p>
          </div>
        </div>
        {messages.length > 0 && (
          <button
            onClick={() => { setMessages([]); setSessionId(undefined); }}
            className="text-xs text-muted hover:text-foreground transition-colors px-3 py-1.5 rounded-lg hover:bg-surface3"
          >
            New chat
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 ? (
          <EmptyState agentName={agentName} />
        ) : (
          messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} agentName={agentName} />
          ))
        )}

        {/* Typing indicator */}
        {chatMutation.isPending && (
          <div className="flex items-center gap-3">
            <AgentAvatar name={agentName} />
            <div className="bg-surface3 rounded-2xl rounded-tl-sm px-4 py-3 border border-border">
              <TypingDots />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-6 pb-6 pt-2">
        <div className="flex items-end gap-3 bg-surface3 rounded-2xl border border-border focus-within:border-accent/50 transition-colors p-3">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Message ${agentName}…`}
            rows={1}
            className="flex-1 bg-transparent resize-none outline-none text-sm leading-relaxed max-h-40 scrollbar-thin placeholder:text-muted"
            style={{ minHeight: "1.5rem" }}
            onInput={(e) => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = Math.min(el.scrollHeight, 160) + "px";
            }}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || chatMutation.isPending}
            className="shrink-0 w-9 h-9 rounded-xl bg-accent hover:bg-accent/80 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-all"
            aria-label="Send message"
          >
            <SendIcon />
          </button>
        </div>
        <p className="text-[11px] text-muted text-center mt-2 font-mono">
          ↵ Send · Shift+↵ Newline
        </p>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────

function MessageBubble({ message, agentName }: { message: ChatMessage; agentName: string }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex items-end gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      {!isUser && <AgentAvatar name={agentName} />}

      <div className={`max-w-[75%] space-y-1 ${isUser ? "items-end" : "items-start"} flex flex-col`}>
        <div
          className={`px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words ${
            isUser
              ? "bg-accent text-white rounded-2xl rounded-br-sm"
              : "bg-surface3 border border-border rounded-2xl rounded-tl-sm"
          }`}
        >
          {message.content}
        </div>

        <div className="flex items-center gap-3 px-1">
          <span className="text-[10px] text-muted font-mono">
            {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
          {!isUser && message.latency_ms && (
            <span className="text-[10px] text-muted font-mono">{message.latency_ms}ms</span>
          )}
          {!isUser && (message.memories_used ?? 0) > 0 && (
            <span className="text-[10px] text-accent font-mono">
              ◎ {message.memories_used} memories
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function AgentAvatar({ name }: { name: string }) {
  return (
    <div className="w-8 h-8 shrink-0 rounded-xl bg-gradient-to-br from-accent to-accent2 flex items-center justify-center text-xs font-bold font-syne">
      {name[0]}
    </div>
  );
}

function EmptyState({ agentName }: { agentName: string }) {
  const suggestions = [
    "What do you remember about me?",
    "What are your current capabilities?",
    "Search your memory for recent tasks",
    "Who are you connected to on the network?",
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 py-8">
      <div className="text-center space-y-2">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-accent to-accent2 flex items-center justify-center text-2xl font-bold font-syne mx-auto">
          {agentName[0]}
        </div>
        <h3 className="font-semibold font-syne">{agentName}</h3>
        <p className="text-sm text-muted max-w-xs text-center">
          Your persistent AI agent. It remembers all past conversations and grows smarter over time.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-2 w-full max-w-sm">
        {suggestions.map((s) => (
          <button
            key={s}
            className="text-xs text-left px-3 py-2.5 rounded-xl border border-border bg-surface2 hover:border-accent/40 hover:bg-surface3 transition-all text-muted hover:text-foreground"
            onClick={() => {}}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function TypingDots() {
  return (
    <div className="flex items-center gap-1.5 py-0.5">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce"
          style={{ animationDelay: `${i * 150}ms` }}
        />
      ))}
    </div>
  );
}

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M14 8L2 2L5 8L2 14L14 8Z" fill="white" />
    </svg>
  );
}
