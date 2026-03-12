"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useAgent } from "@/hooks/useApi";
import { AgentChat } from "@/components/agent/AgentChat";
import { MemoryViewer } from "@/components/memory/MemoryViewer";

type Tab = "chat" | "memories";

export default function AgentDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [tab, setTab] = useState<Tab>("chat");

  const { data: agent, isLoading, error } = useAgent(id);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <span className="text-muted text-sm font-mono animate-pulse">Loading agent…</span>
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <p className="text-muted text-sm">Agent not found</p>
        <a href="/dashboard" className="text-accent text-sm hover:underline">
          ← Back to Dashboard
        </a>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-border px-6 py-3 flex items-center gap-6">
        <a
          href="/dashboard"
          className="text-lg font-bold font-syne bg-gradient-to-r from-accent to-accent2 bg-clip-text text-transparent"
        >
          Life++
        </a>
        <a href="/dashboard" className="text-xs text-muted hover:text-foreground transition-colors">
          ← Dashboard
        </a>
      </header>

      <div className="flex-1 flex flex-col p-6 gap-4 max-w-5xl mx-auto w-full">
        {/* Agent info */}
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-accent to-accent2 flex items-center justify-center text-lg font-bold font-syne">
            {agent.name[0]}
          </div>
          <div>
            <h1 className="text-xl font-bold font-syne">{agent.name}</h1>
            <div className="flex items-center gap-3 mt-0.5">
              <span className="text-xs text-muted capitalize font-mono">{agent.status}</span>
              {agent.capabilities.length > 0 && (
                <div className="flex gap-1">
                  {agent.capabilities.map((cap) => (
                    <span
                      key={cap}
                      className="text-[10px] px-2 py-0.5 rounded-md bg-surface3 border border-border font-mono text-muted"
                    >
                      {cap}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Tab switcher */}
        <div className="flex items-center gap-2">
          {(["chat", "memories"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-1.5 rounded-lg text-sm capitalize transition-all ${
                tab === t
                  ? "bg-accent/20 text-accent"
                  : "text-muted hover:text-foreground"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 min-h-0" style={{ height: "calc(100vh - 220px)" }}>
          {tab === "chat" ? (
            <AgentChat agentId={agent.id} agentName={agent.name} />
          ) : (
            <MemoryViewer agentId={agent.id} />
          )}
        </div>
      </div>
    </div>
  );
}
