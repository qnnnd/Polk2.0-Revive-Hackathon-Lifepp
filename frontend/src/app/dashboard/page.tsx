"use client";

import { useState } from "react";
import { useAgents, useCreateAgent } from "@/hooks/useApi";
import { AgentChat } from "@/components/agent/AgentChat";
import { NetworkGraph } from "@/components/network/NetworkGraph";
import { MemoryViewer } from "@/components/memory/MemoryViewer";
import { toast } from "sonner";
import type { Agent, UUID } from "@/types";

type Tab = "agents" | "network";

export default function Dashboard() {
  const [tab, setTab] = useState<Tab>("agents");
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [agentView, setAgentView] = useState<"chat" | "memories">("chat");

  const { data: agentsData, isLoading } = useAgents();
  const createAgent = useCreateAgent();

  const handleCreateAgent = async () => {
    try {
      const agent = await createAgent.mutateAsync({
        name: `Agent-${Date.now().toString(36)}`,
        description: "A new cognitive agent on the Life++ network",
        capabilities: ["general", "research"],
        is_public: true,
      });
      toast.success(`Agent "${agent.name}" created!`);
      setSelectedAgent(agent);
    } catch (err: any) {
      toast.error(err.message ?? "Failed to create agent");
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-border px-6 py-3 flex items-center gap-6">
        <a href="/" className="text-lg font-bold font-syne bg-gradient-to-r from-accent to-accent2 bg-clip-text text-transparent">
          Life++
        </a>
        <nav className="flex gap-1">
          {(["agents", "network"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => { setTab(t); setSelectedAgent(null); }}
              className={`px-4 py-2 rounded-lg text-sm capitalize transition-all ${
                tab === t ? "bg-accent/20 text-accent" : "text-muted hover:text-foreground"
              }`}
            >
              {t}
            </button>
          ))}
        </nav>
      </header>

      <div className="flex-1 flex">
        {tab === "agents" && (
          <>
            <aside className="w-72 border-r border-border p-4 space-y-3 overflow-y-auto">
              <button
                onClick={handleCreateAgent}
                disabled={createAgent.isPending}
                className="w-full bg-accent hover:bg-accent/80 text-white rounded-xl py-2.5 text-sm font-semibold transition-all disabled:opacity-50"
              >
                + New Agent
              </button>

              {isLoading ? (
                <p className="text-sm text-muted animate-pulse text-center py-4">Loading...</p>
              ) : (
                (agentsData?.agents ?? []).map((agent) => (
                  <button
                    key={agent.id}
                    onClick={() => setSelectedAgent(agent)}
                    className={`w-full text-left p-3 rounded-xl border transition-all ${
                      selectedAgent?.id === agent.id
                        ? "border-accent/40 bg-accent/10"
                        : "border-border bg-surface2 hover:border-border/80"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-accent2 flex items-center justify-center text-xs font-bold">
                        {agent.name[0]}
                      </div>
                      <div>
                        <p className="text-sm font-semibold">{agent.name}</p>
                        <p className="text-xs text-muted capitalize">{agent.status}</p>
                      </div>
                    </div>
                  </button>
                ))
              )}
            </aside>

            <main className="flex-1 p-6">
              {selectedAgent ? (
                <div className="h-full flex flex-col gap-4">
                  <div className="flex items-center gap-2">
                    {(["chat", "memories"] as const).map((v) => (
                      <button
                        key={v}
                        onClick={() => setAgentView(v)}
                        className={`px-4 py-1.5 rounded-lg text-sm capitalize transition-all ${
                          agentView === v ? "bg-accent/20 text-accent" : "text-muted hover:text-foreground"
                        }`}
                      >
                        {v}
                      </button>
                    ))}
                  </div>
                  <div className="flex-1 min-h-0">
                    {agentView === "chat" ? (
                      <AgentChat agentId={selectedAgent.id} agentName={selectedAgent.name} />
                    ) : (
                      <MemoryViewer agentId={selectedAgent.id} />
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-center h-full text-muted text-sm">
                  Select an agent or create a new one
                </div>
              )}
            </main>
          </>
        )}

        {tab === "network" && (
          <main className="flex-1 p-6">
            <NetworkGraph />
          </main>
        )}
      </div>
    </div>
  );
}
