"use client";

import { useState } from "react";
import { Topbar } from "@/components/ui/Topbar";
import { useNetworkGraph, useNetworkStats } from "@/hooks/useApi";
import type { NetworkNode, NetworkEdge } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  active: "#30d1a1",
  idle: "#f3b35e",
  sleeping: "#7183a2",
  online: "#30d1a1",
  busy: "#f3b35e",
  offline: "#7183a2",
  error: "#f87171",
  terminated: "#374151",
};

export default function NetworkPage() {
  const { data: graph, isLoading } = useNetworkGraph();
  const { data: stats } = useNetworkStats();
  const [selected, setSelected] = useState<NetworkNode | null>(null);

  const nodes = graph?.nodes ?? [];
  const edges = graph?.edges ?? [];

  // Backend places nodes in a circle with radius 200 (x,y in ~[-200,200]). Fit into viewBox 920×560.
  const normalizeNodes = (ns: NetworkNode[]) => {
    if (ns.length === 0) return [];
    const xs = ns.map((n) => n.x ?? 0);
    const ys = ns.map((n) => n.y ?? 0);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;
    const padding = 80;
    const width = 920 - 2 * padding;
    const height = 560 - 2 * padding;
    return ns.map((n) => ({
      ...n,
      cx: padding + ((n.x ?? 0) - minX) / rangeX * width,
      cy: padding + ((n.y ?? 0) - minY) / rangeY * height,
    }));
  };

  const positioned = normalizeNodes(nodes);
  const nodeMap = new Map(positioned.map((n) => [n.id, n]));

  return (
    <>
      <Topbar title="NetworkGraph" description="Agent network topology and connections" />
      <div className="page-content">
        <div className="network-layout">
          {/* Left: Graph */}
          <div className="card" style={{ padding: 20 }}>
            <h3>NetworkGraph</h3>
            <div className="graph-wrap">
              {isLoading ? (
                <div style={{ textAlign: "center", padding: 80, color: "var(--text-3)" }}>
                  Loading graph…
                </div>
              ) : (
                <svg viewBox="0 0 920 560" width="100%" height="100%" style={{ display: "block" }}>
                  <defs>
                    <pattern id="gridNet" width="40" height="40" patternUnits="userSpaceOnUse">
                      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(110,140,255,0.04)" strokeWidth="1" />
                    </pattern>
                  </defs>
                  <rect width="100%" height="100%" fill="url(#gridNet)" />

                  {/* Edges */}
                  {edges.map((edge: NetworkEdge) => {
                    const from = nodeMap.get(edge.from_id);
                    const to = nodeMap.get(edge.to_id);
                    if (!from || !to) return null;
                    return (
                      <line
                        key={`${edge.from_id}-${edge.to_id}`}
                        x1={from.cx}
                        y1={from.cy}
                        x2={to.cx}
                        y2={to.cy}
                        stroke="rgba(110,140,255,0.15)"
                        strokeWidth={1.5 * edge.strength}
                      />
                    );
                  })}

                  {/* Nodes */}
                  {positioned.map((node) => {
                    const color = STATUS_COLORS[node.status] ?? "#7183a2";
                    const isSelected = selected?.id === node.id;
                    const r = 18 + node.reputation_score * 3;

                    return (
                      <g
                        key={node.id}
                        transform={`translate(${node.cx}, ${node.cy})`}
                        style={{ cursor: "pointer" }}
                        onClick={() => setSelected(isSelected ? null : node)}
                      >
                        {isSelected && (
                          <circle
                            r={r + 10}
                            fill="none"
                            stroke="var(--brand)"
                            strokeWidth="1.5"
                            strokeDasharray="4 3"
                            opacity="0.8"
                          />
                        )}
                        {(node.status === "active" || node.status === "online") && (
                          <circle r={r + 5} fill={color} opacity="0.12">
                            <animate attributeName="opacity" values="0.05;0.2;0.05" dur="2s" repeatCount="indefinite" />
                          </circle>
                        )}
                        <circle
                          r={r}
                          fill={`${color}20`}
                          stroke={color}
                          strokeWidth={isSelected ? 2 : 1.5}
                        />
                        <text
                          textAnchor="middle"
                          dominantBaseline="central"
                          fill={color}
                          fontSize={13}
                          fontWeight="700"
                        >
                          {node.name[0]}
                        </text>
                        <text
                          y={r + 14}
                          textAnchor="middle"
                          fill="rgba(236,243,255,0.6)"
                          fontSize={10}
                        >
                          {node.name}
                        </text>
                      </g>
                    );
                  })}
                </svg>
              )}
            </div>
            <div className="graph-legend">
              <div className="legend-item">
                <div className="legend-dot" style={{ background: "#30d1a1" }} />
                online
              </div>
              <div className="legend-item">
                <div className="legend-dot" style={{ background: "#f3b35e" }} />
                busy
              </div>
              <div className="legend-item">
                <div className="legend-dot" style={{ background: "#7183a2" }} />
                offline
              </div>
              <div className="legend-item">
                <div className="legend-dot" style={{ background: "var(--brand)" }} />
                selected
              </div>
            </div>
          </div>

          {/* Right column */}
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {/* Network Stats */}
            <div className="card">
              <h3>Network Stats</h3>
              <div className="metric-grid">
                <div className="metric-item">
                  <div className="label">Nodes</div>
                  <div className="value">{stats?.total_agents ?? nodes.length}</div>
                </div>
                <div className="metric-item">
                  <div className="label">Edges</div>
                  <div className="value">{edges.length}</div>
                </div>
                <div className="metric-item">
                  <div className="label">Online</div>
                  <div className="value" style={{ color: "var(--green)" }}>
                    {stats?.online_agents ?? 0}
                  </div>
                </div>
                <div className="metric-item">
                  <div className="label">Busy</div>
                  <div className="value" style={{ color: "var(--amber)" }}>
                    {nodes.filter((n) => n.status === "busy" || n.status === "idle").length}
                  </div>
                </div>
              </div>
            </div>

            {/* Node Details */}
            <div className="card">
              <h3>Node Details</h3>
              {selected ? (
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
                    <div
                      style={{
                        width: 40, height: 40, borderRadius: 12,
                        background: `${STATUS_COLORS[selected.status] ?? "#7183a2"}25`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontWeight: 700, color: STATUS_COLORS[selected.status] ?? "#7183a2",
                      }}
                    >
                      {selected.name[0]}
                    </div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 15 }}>{selected.name}</div>
                      <div style={{ fontSize: 12, color: "var(--text-3)" }}>
                        {selected.capabilities?.join(", ") || "general"}
                      </div>
                    </div>
                  </div>
                  <div className="status-item">
                    <span className="label">Status</span>
                    <span className="value" style={{ color: STATUS_COLORS[selected.status] }}>
                      {selected.status}
                    </span>
                  </div>
                  <div className="status-item">
                    <span className="label">Reputation</span>
                    <span className="value">{selected.reputation_score.toFixed(1)}/5.0</span>
                  </div>
                  <p style={{ fontSize: 12, color: "var(--text-3)", marginTop: 12 }}>
                    This agent can collaborate with other nodes on the network for task execution and memory sharing.
                  </p>
                </div>
              ) : (
                <p style={{ color: "var(--text-3)", fontSize: 13 }}>
                  Click a node on the graph to see its details.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
