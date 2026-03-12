"use client";

import { NetworkGraph } from "@/components/network/NetworkGraph";
import { useNetworkStats } from "@/hooks/useApi";

export default function NetworkPage() {
  const { data: stats } = useNetworkStats();

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
        <span className="text-sm font-syne text-foreground">Network</span>

        <div className="ml-auto flex items-center gap-4 text-xs font-mono text-muted">
          <span>
            <span className="text-foreground font-semibold">{stats?.total_agents ?? 0}</span> agents
          </span>
          <span>
            <span className="text-accent font-semibold">{stats?.online_agents ?? 0}</span> online
          </span>
          <div
            className={`px-2 py-1 rounded-lg border ${
              stats?.network_health === "healthy"
                ? "bg-green-500/10 text-green-400 border-green-500/20"
                : "bg-yellow-500/10 text-yellow-400 border-yellow-500/20"
            }`}
          >
            ● {stats?.network_health ?? "—"}
          </div>
        </div>
      </header>

      <main className="flex-1 p-6" style={{ height: "calc(100vh - 60px)" }}>
        <NetworkGraph />
      </main>
    </div>
  );
}
