"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Topbar } from "@/components/ui/Topbar";
import {
  useAgents,
  useChainConfig,
  useMarketplaceTasks,
  usePublishTask,
  useCancelListing,
  useAcceptTask,
  useCompleteTask,
  queryKeys,
} from "@/hooks/useApi";
import { useQueryClient } from "@tanstack/react-query";
import { getAccessToken, setAccessToken, authApi, marketplaceApi } from "@/lib/api";
import type { ChainTxParams, TaskListing } from "@/types";

declare global {
  interface Window {
    ethereum?: {
      request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
    };
  }
}

const FILTER_OPTIONS = ["all", "open", "escrowed", "running", "done"] as const;

export default function MarketplacePage() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [username, setUsername] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (getAccessToken()) setIsLoggedIn(true);
  }, []);

  // When already logged in (e.g. page load with token), ensure cache matches current user.
  useEffect(() => {
    if (isLoggedIn) invalidateUserData();
  }, [isLoggedIn]);

  const invalidateUserData = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.agents.all });
    queryClient.invalidateQueries({ queryKey: queryKeys.marketplace.all });
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
    queryClient.invalidateQueries({ queryKey: ["memories"] });
  };

  const handleLogin = async () => {
    if (!username.trim()) return;
    setLoginLoading(true);
    try {
      const did = `did:key:${crypto.randomUUID()}`;
      await authApi.register({ did, username: username.trim(), display_name: username.trim() });
      const tokenRes = await authApi.login(username.trim());
      setAccessToken(tokenRes.access_token);
      invalidateUserData();
      setIsLoggedIn(true);
      toast.success("Welcome to Life++!");
    } catch (err: any) {
      if (err.status === 409) {
        try {
          const tokenRes = await authApi.login(username.trim());
          setAccessToken(tokenRes.access_token);
          invalidateUserData();
          setIsLoggedIn(true);
          toast.success(`Welcome back, ${username}!`);
        } catch {
          toast.error("Login failed");
        }
      } else {
        toast.error(err.message ?? "Registration failed");
      }
    } finally {
      setLoginLoading(false);
    }
  };

  if (!isLoggedIn) {
    return (
      <>
        <Topbar title="Marketplace" description="Task marketplace and settlement" />
        <div className="page-content">
          <div className="login-card">
            <h2>Life++</h2>
            <p>Sign in to access the Marketplace</p>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
              placeholder="Choose a username"
            />
            <button onClick={handleLogin} disabled={loginLoading || !username.trim()}>
              {loginLoading ? "Connecting..." : "Enter Life++"}
            </button>
          </div>
        </div>
      </>
    );
  }

  return <MarketplaceContent />;
}

function MarketplaceContent() {
  const [filter, setFilter] = useState<string>("all");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [reward, setReward] = useState("");
  const [acceptAgentByListingId, setAcceptAgentByListingId] = useState<Record<string, string>>({});
  const [completingId, setCompletingId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  // Ensure user-scoped data is fresh when viewing marketplace (e.g. after token change or new tab).
  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: queryKeys.agents.all });
    queryClient.invalidateQueries({ queryKey: queryKeys.marketplace.all });
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
    queryClient.invalidateQueries({ queryKey: ["memories"] });
  }, [queryClient]);

  const { data: agentsData } = useAgents();
  const { data: chainConfig } = useChainConfig();
  const { data: tasks } = useMarketplaceTasks(
    filter !== "all" ? { status: filter } : undefined
  );
  const publishTask = usePublishTask();
  const cancelListing = useCancelListing();
  const acceptTask = useAcceptTask();
  const completeTask = useCompleteTask();

  const agents = agentsData?.agents ?? [];
  const myAgentIds = new Set(agents.map((a) => a.id));
  const allTasks: TaskListing[] = Array.isArray(tasks) ? tasks : [];
  const canCancel = (task: TaskListing) =>
    task.status === "open" && myAgentIds.has(task.poster_agent_id);
  const canAccept = (task: TaskListing) =>
    task.status === "open" && !myAgentIds.has(task.poster_agent_id) && agents.length > 0;
  const couldAcceptButNoAgent = (task: TaskListing) =>
    task.status === "open" && !myAgentIds.has(task.poster_agent_id) && agents.length === 0;
  const canComplete = (task: TaskListing) =>
    task.status === "accepted" && myAgentIds.has(task.poster_agent_id);
  const isAcceptedWaitingForPublisher = (task: TaskListing) =>
    task.status === "accepted" && !myAgentIds.has(task.poster_agent_id);

  const handlePublish = async () => {
    if (!title.trim()) {
      toast.error("Title is required");
      return;
    }
    const rewardNum = reward ? parseFloat(reward) : 0;
    const hasReward = !Number.isNaN(rewardNum) && rewardNum > 0;
    if (hasReward && (typeof window === "undefined" || !window.ethereum)) {
      toast.error("Connect MetaMask (or another wallet) to publish a task with IVE reward.");
      return;
    }
    try {
      const listing = await publishTask.mutateAsync({
        title: title.trim(),
        description: description.trim() || "No description",
        reward_cog: rewardNum || 0,
      });
      const params = listing?.chain_tx_params as ChainTxParams | undefined | null;
      if (params && params.to && params.data) {
        toast.info("Please confirm the transaction in your wallet to lock the IVE reward.", {
          duration: 8000,
        });
        const accounts = (await window.ethereum!.request({ method: "eth_requestAccounts" })) as string[];
        if (!accounts?.[0]) {
          toast.error("No wallet account selected. Unlock MetaMask and try again.");
          return;
        }
        const txResult = await window.ethereum!.request({
          method: "eth_sendTransaction",
          params: [
            {
              from: accounts[0],
              to: params.to,
              data: params.data,
              value: params.value,
              chainId: "0x" + Number(params.chain_id).toString(16),
            },
          ],
        });
        const txHash = Array.isArray(txResult)
          ? (txResult[0] as string)
          : (txResult as string);
        if (!txHash) {
          toast.error("Transaction was not sent. Check your wallet.");
          return;
        }
        toast.info("Transaction submitted. Confirming on chain...");
        await marketplaceApi.confirmChainCreated(listing.id, txHash);
        queryClient.invalidateQueries({ queryKey: queryKeys.marketplace.all });
        toast.success("Task published! IVE reward locked from your wallet.");
      } else {
        if (hasReward) {
          toast.warning(
            "Task saved, but IVE was not locked. Check backend (REVIVE_RPC_URL, TASK_MARKET_ADDRESS) or try again."
          );
        } else {
          toast.success("Task published!");
        }
      }
      setTitle("");
      setDescription("");
      setReward("");
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to publish task");
    }
  };

  const statusColor = (status: string) => {
    switch (status) {
      case "open": return "green";
      case "escrowed": return "amber";
      case "running": return "cyan";
      case "completed": case "done": return "brand2";
      case "cancelled": return "red";
      default: return "";
    }
  };

  const progress = (status: string) => {
    switch (status) {
      case "open": return 20;
      case "escrowed": return 40;
      case "running": return 65;
      case "completed": case "done": return 100;
      case "cancelled": return 0;
      default: return 10;
    }
  };

  return (
    <>
      <Topbar title="Marketplace" description="Task marketplace and settlement" />
      <div className="page-content">
        <div className="market-layout">
          {/* Left: Task list */}
          <div className="card">
            <h3>Marketplace</h3>

            {/* Create form */}
            <div style={{ marginBottom: 20, padding: 16, background: "var(--panel-2)", borderRadius: 14, border: "1px solid var(--line)" }}>
              <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
                <input
                  className="form-input"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Task title"
                />
                <input
                  className="form-input"
                  style={{ width: 120, flexShrink: 0 }}
                  value={reward}
                  onChange={(e) => setReward(e.target.value)}
                  placeholder="IVE reward"
                  type="number"
                  min="0"
                />
              </div>
              <textarea
                className="form-input"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Task description"
                rows={2}
                style={{ resize: "none", marginBottom: 10 }}
              />
              <button
                className="btn-brand"
                onClick={handlePublish}
                disabled={publishTask.isPending || !title.trim()}
              >
                {publishTask.isPending ? "Publishing..." : "Publish Task"}
              </button>
            </div>

            {/* Task items */}
            {allTasks.length === 0 ? (
              <p style={{ color: "var(--text-3)", fontSize: 13 }}>No tasks listed yet.</p>
            ) : (
              allTasks.map((task) => (
                <div key={task.id} className="task-item">
                  <div className="task-head">
                    <span className="id">#{task.id.slice(0, 8)}</span>
                    <span className={`tag ${statusColor(task.status)}`}>{task.status}</span>
                    <span className="tag">{task.reward_cog} IVE</span>
                    {task.winning_agent_id && (
                      <span className="tag cyan">Agent: {task.winning_agent_id.slice(0, 8)}</span>
                    )}
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: "auto" }}>
                    {couldAcceptButNoAgent(task) && (
                      <a
                        href="/dashboard?tab=agents"
                        style={{
                          fontSize: 11,
                          color: "var(--text-3)",
                          textDecoration: "underline",
                        }}
                        title="Create an agent on Dashboard first, then you can accept tasks"
                      >
                        Need an agent to accept →
                      </a>
                    )}
                    {canAccept(task) && (
                      <>
                        <select
                          className="form-input"
                          value={acceptAgentByListingId[task.id] ?? ""}
                          onChange={(e) =>
                            setAcceptAgentByListingId((prev) => ({
                              ...prev,
                              [task.id]: e.target.value,
                            }))
                          }
                          style={{
                            fontSize: 11,
                            padding: "4px 8px",
                            minWidth: 100,
                            borderRadius: 6,
                            border: "1px solid var(--border)",
                            background: "var(--panel-2)",
                            color: "var(--text-1)",
                          }}
                        >
                          <option value="">Select agent</option>
                          {agents.map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.name}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          onClick={() => {
                            const agentId = acceptAgentByListingId[task.id];
                            if (!agentId) {
                              toast.error("Please select an agent");
                              return;
                            }
                            acceptTask.mutate(
                              { listingId: task.id, agentId },
                              {
                                onSuccess: () => {
                                  toast.success("Task accepted");
                                  setAcceptAgentByListingId((prev) => {
                                    const next = { ...prev };
                                    delete next[task.id];
                                    return next;
                                  });
                                },
                                onError: (err: any) =>
                                  toast.error(err?.message ?? "Failed to accept task"),
                              }
                            );
                          }}
                          disabled={acceptTask.isPending}
                          style={{
                            fontSize: 11,
                            padding: "4px 10px",
                            border: "1px solid var(--green)",
                            color: "var(--green)",
                            background: "transparent",
                            borderRadius: 8,
                            cursor: "pointer",
                          }}
                        >
                          {acceptTask.isPending ? "..." : "Accept"}
                        </button>
                      </>
                    )}
                    {isAcceptedWaitingForPublisher(task) && (
                      <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--text-3)" }}>
                        Waiting for publisher to complete
                      </span>
                    )}
                    {canComplete(task) && (
                      <button
                        type="button"
                        onClick={() => {
                          setCompletingId(task.id);
                          completeTask.mutate(task.id, {
                            onSuccess: () => {
                              toast.success("Task completed");
                              setCompletingId(null);
                            },
                            onError: (err: any) => {
                              toast.error(err?.message ?? "Failed to complete task");
                              setCompletingId(null);
                            },
                          });
                        }}
                        disabled={completingId === task.id}
                        style={{
                          marginLeft: "auto",
                          fontSize: 11,
                          padding: "4px 10px",
                          border: "1px solid var(--cyan)",
                          color: "var(--cyan)",
                          background: "transparent",
                          borderRadius: 8,
                          cursor: "pointer",
                        }}
                      >
                        {completingId === task.id ? "..." : "Complete"}
                      </button>
                    )}
                    {canCancel(task) && (
                      <button
                        type="button"
                        onClick={() => {
                          cancelListing.mutate(task.id, {
                            onSuccess: () => toast.success("Task cancelled"),
                            onError: (err: any) => toast.error(err?.message ?? "Failed to cancel"),
                          });
                        }}
                        disabled={cancelListing.isPending}
                        style={{
                          fontSize: 11,
                          padding: "4px 10px",
                          border: "1px solid var(--red)",
                          color: "var(--red)",
                          background: "transparent",
                          borderRadius: 8,
                          cursor: "pointer",
                        }}
                      >
                        Cancel
                      </button>
                    )}
                    </div>
                  </div>
                  <div className="task-title">{task.title}</div>
                  {task.description && <div className="task-desc">{task.description}</div>}
                  <div className="progress-bar">
                    <div className="fill" style={{ width: `${progress(task.status)}%` }} />
                  </div>
                  {task.tx_hash && (
                    <div className="tx-hash">TX: {task.tx_hash}</div>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Right column */}
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {/* Settlement Status — from Revive API (13.4: no fake chain data) */}
            <div className="card">
              <h3>Settlement Status</h3>
              <div className="status-item">
                <span className="label">Contract</span>
                <span className="value" style={{ fontSize: 12, fontFamily: "monospace" }}>
                  {chainConfig?.task_market_address
                    ? `${chainConfig.task_market_address.slice(0, 6)}…${chainConfig.task_market_address.slice(-6)}`
                    : "—"}
                </span>
              </div>
              <div className="status-item">
                <span className="label">Recent TX</span>
                <span className="value" style={{ fontSize: 12 }}>
                  {(() => {
                    const recentTx = allTasks.find((t) => t.tx_hash)?.tx_hash;
                    return recentTx ? `${recentTx.slice(0, 10)}…` : "—";
                  })()}
                </span>
              </div>
              <div className="status-item">
                <span className="label">Constraint</span>
                <span className="value" style={{ fontSize: 12, color: "var(--amber)" }}>
                  Testnet Only
                </span>
              </div>
            </div>

            {/* Task Filters */}
            <div className="card">
              <h3>Task Filters</h3>
              <div className="filter-chips">
                {FILTER_OPTIONS.map((f) => (
                  <button
                    key={f}
                    className={`chip ${filter === f ? "active" : ""}`}
                    onClick={() => setFilter(f)}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
