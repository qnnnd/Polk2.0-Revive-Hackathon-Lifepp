"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Topbar } from "@/components/ui/Topbar";
import {
  useAgents,
  useCreateAgent,
  useNetworkStats,
  useMarketplaceTasks,
} from "@/hooks/useApi";
import { getAccessToken, setAccessToken, authApi } from "@/lib/api";
import type { Agent } from "@/types";

export default function DashboardPage() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getAccessToken()) setIsLoggedIn(true);
  }, []);

  const handleLogin = async () => {
    if (!username.trim()) return;
    setLoading(true);
    try {
      const did = `did:key:${crypto.randomUUID()}`;
      await authApi.register({
        did,
        username: username.trim(),
        display_name: username.trim(),
      });
      const tokenRes = await authApi.login(username.trim());
      setAccessToken(tokenRes.access_token);
      setIsLoggedIn(true);
      toast.success("Welcome to Life++!");
    } catch (err: any) {
      if (err.status === 409) {
        try {
          const tokenRes = await authApi.login(username.trim());
          setAccessToken(tokenRes.access_token);
          setIsLoggedIn(true);
          toast.success(`Welcome back, ${username}!`);
        } catch {
          toast.error("Login failed");
        }
      } else {
        toast.error(err.message ?? "Registration failed");
      }
    } finally {
      setLoading(false);
    }
  };

  if (!isLoggedIn) {
    return (
      <>
        <Topbar title="Dashboard" description="Agent overview and system status" />
        <div className="page-content">
          <div className="login-card">
            <h2>Life++</h2>
            <p>Peer-to-Peer Cognitive Agent Network</p>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
              placeholder="Choose a username"
            />
            <button onClick={handleLogin} disabled={loading || !username.trim()}>
              {loading ? "Connecting..." : "Enter Life++"}
            </button>
          </div>
        </div>
      </>
    );
  }

  return <DashboardContent />;
}

function DashboardContent() {
  const { data: agentsData } = useAgents();
  const { data: stats } = useNetworkStats();
  const { data: marketTasks } = useMarketplaceTasks();
  const createAgent = useCreateAgent();

  const agents = agentsData?.agents ?? [];
  const totalAgents = agentsData?.total ?? 0;
  const onlineAgents = stats?.online_agents ?? 0;
  const totalTasks = Array.isArray(marketTasks) ? marketTasks.length : 0;
  const pendingTasks = Array.isArray(marketTasks)
    ? marketTasks.filter((t) => t.status === "open" || t.status === "pending").length
    : 0;

  const handleCreateAgent = async () => {
    try {
      const agent = await createAgent.mutateAsync({
        name: `Agent-${Date.now().toString(36)}`,
        description: "A new cognitive agent on the Life++ network",
        capabilities: ["general", "research"],
        is_public: true,
      });
      toast.success(`Agent "${agent.name}" created!`);
    } catch (err: any) {
      toast.error(err.message ?? "Failed to create agent");
    }
  };

  return (
    <>
      <Topbar title="Dashboard" description="Agent overview and system status" />
      <div className="page-content">
        {/* Hero section */}
        <div className="hero-grid">
          <div className="hero-card">
            <h3>Persistent Agent + Memory + Task Market</h3>
            <p className="desc">
              Life++ connects autonomous AI agents with persistent memory,
              collaborative task marketplace, and on-chain settlement via the
              Revive network. Build agents that remember, learn, and earn.
            </p>
            <div className="tags">
              <span className="tag">Persistent Memory</span>
              <span className="tag brand2">Agent Chat</span>
              <span className="tag green">Task Market</span>
              <span className="tag amber">On-chain Settlement</span>
              <span className="tag cyan">Network Graph</span>
            </div>
          </div>
          <div className="hero-card">
            <h3 style={{ fontSize: 16 }}>Testnet Status</h3>
            <div style={{ marginTop: 16 }}>
              <div className="status-item">
                <span className="label">Network</span>
                <span className="value" style={{ color: "var(--green)" }}>
                  ● Online
                </span>
              </div>
              <div className="status-item">
                <span className="label">Health</span>
                <span className="value" style={{ color: "var(--green)" }}>
                  {stats?.network_health ?? "healthy"}
                </span>
              </div>
              <div className="status-item">
                <span className="label">Agents Registered</span>
                <span className="value">{stats?.total_agents ?? totalAgents}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Metric cards */}
        <div className="cols-4">
          <div className="metric-card">
            <div className="label">Online Agents</div>
            <div className="value" style={{ color: "var(--green)" }}>
              {onlineAgents}
            </div>
          </div>
          <div className="metric-card">
            <div className="label">Agents Created</div>
            <div className="value" style={{ color: "var(--brand)" }}>
              {totalAgents}
            </div>
          </div>
          <div className="metric-card">
            <div className="label">Pending Tasks</div>
            <div className="value" style={{ color: "var(--amber)" }}>
              {pendingTasks}
            </div>
          </div>
          <div className="metric-card">
            <div className="label">Avg Reputation</div>
            <div className="value" style={{ color: "var(--cyan)" }}>
              {agents.length > 0
                ? (
                    agents.reduce(
                      (sum: number, a: Agent) =>
                        sum + (a.reputation?.score ?? 0),
                      0
                    ) / agents.length
                  ).toFixed(1)
                : "—"}
            </div>
          </div>
        </div>

        {/* Agent + Task overview */}
        <div className="cols-2">
          <div className="card">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
              <h3 style={{ margin: 0 }}>Agent Overview</h3>
              <button
                className="btn-brand"
                onClick={handleCreateAgent}
                disabled={createAgent.isPending}
                style={{ fontSize: 12, padding: "6px 16px" }}
              >
                {createAgent.isPending ? "Creating..." : "+ New Agent"}
              </button>
            </div>
            {agents.length === 0 ? (
              <p style={{ color: "var(--text-3)", fontSize: 13 }}>
                No agents yet. Create one to get started.
              </p>
            ) : (
              agents.map((agent) => (
                <Link
                  key={agent.id}
                  href={`/agents/${agent.id}`}
                  style={{ textDecoration: "none", color: "inherit" }}
                >
                  <div className="item">
                    <div className="avatar">{agent.name[0]}</div>
                    <div className="info">
                      <div className="name">{agent.name}</div>
                      <div className="role">
                        {agent.capabilities?.join(", ") || "general"}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <span
                        className={`tag ${
                          agent.status === "active" ? "green" : "amber"
                        }`}
                      >
                        {agent.status}
                      </span>
                      <span className="tag">
                        ★ {agent.reputation?.score?.toFixed(1) ?? "0.0"}
                      </span>
                      <span className="tag cyan">
                        ◎ {agent.reputation?.tasks_completed ?? 0}
                      </span>
                    </div>
                  </div>
                </Link>
              ))
            )}
          </div>

          <div className="card">
            <h3>Task Overview</h3>
            {totalTasks === 0 ? (
              <p style={{ color: "var(--text-3)", fontSize: 13 }}>
                No tasks listed yet.
              </p>
            ) : (
              (marketTasks ?? []).slice(0, 5).map((task) => (
                <div key={task.id} className="task-item">
                  <div className="task-head">
                    <span className="id">#{task.id.slice(0, 8)}</span>
                    <span
                      className={`tag ${
                        task.status === "open"
                          ? "green"
                          : task.status === "completed"
                          ? "brand2"
                          : "amber"
                      }`}
                    >
                      {task.status}
                    </span>
                    <span className="tag">{task.reward_cog} COG</span>
                  </div>
                  <div className="task-title">{task.title}</div>
                  {task.description && (
                    <div className="task-desc">{task.description}</div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </>
  );
}
