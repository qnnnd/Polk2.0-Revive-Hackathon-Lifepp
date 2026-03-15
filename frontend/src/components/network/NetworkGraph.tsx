"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useNetworkGraph, useNetworkStats } from "@/hooks/useApi";
import type { NetworkEdge, NetworkNode, UUID } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  active: "#34d399",
  idle: "#f59e0b",
  sleeping: "#6b7280",
  error: "#f87171",
  terminated: "#374151",
};

export function NetworkGraph() {
  const { data: graph, isLoading } = useNetworkGraph();
  const { data: stats } = useNetworkStats();
  const svgRef = useRef<SVGSVGElement>(null);
  const [selected, setSelected] = useState<NetworkNode | null>(null);
  const [dimensions, setDimensions] = useState({ w: 900, h: 540 });

  // Observe container size
  useEffect(() => {
    const el = svgRef.current?.parentElement;
    if (!el) return;
    const obs = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setDimensions({ w: Math.max(400, width), h: Math.max(300, height) });
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-muted text-sm">
        <span className="animate-pulse font-mono">Loading network graph…</span>
      </div>
    );
  }

  const nodes = graph?.nodes ?? [];
  const edges = graph?.edges ?? [];

  // Backend places nodes in a circle (x,y in ~[-200,200]). Fit into viewBox so all nodes are visible.
  const normalizeNodes = (ns: NetworkNode[], w: number, h: number) => {
    if (ns.length === 0) return [];
    const xs = ns.map((n) => n.x ?? 0);
    const ys = ns.map((n) => n.y ?? 0);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;
    const padding = 60;
    const width = w - 2 * padding;
    const height = h - 2 * padding;
    return ns.map((n) => ({
      ...n,
      cx: padding + ((n.x ?? 0) - minX) / rangeX * width,
      cy: padding + ((n.y ?? 0) - minY) / rangeY * height,
    }));
  };

  const positioned = normalizeNodes(nodes, dimensions.w, dimensions.h);
  const nodeMap = new Map(positioned.map((n) => [n.id, n]));

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Stats bar */}
      <div className="flex items-center gap-6 text-sm">
        <span className="font-mono text-muted">
          <span className="text-foreground font-semibold">{stats?.total_agents ?? 0}</span> agents
        </span>
        <span className="font-mono text-muted">
          <span className="text-accent font-semibold">{stats?.online_agents ?? 0}</span> online
        </span>
        <span className="font-mono text-muted">
          <span className="text-foreground font-semibold">{edges.length}</span> connections
        </span>
        <div className={`ml-auto text-xs px-2 py-1 rounded-lg font-mono ${
          stats?.network_health === "healthy"
            ? "bg-green-500/10 text-green-400 border border-green-500/20"
            : "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20"
        }`}>
          ● {stats?.network_health ?? "—"}
        </div>
      </div>

      <div className="flex gap-4 flex-1 min-h-0">
        {/* SVG Canvas */}
        <div className="flex-1 bg-surface2 rounded-2xl border border-border overflow-hidden relative">
          <svg
            ref={svgRef}
            width="100%"
            height="100%"
            viewBox={`0 0 ${dimensions.w} ${dimensions.h}`}
            preserveAspectRatio="xMidYMid meet"
          >
            {/* Background grid */}
            <defs>
              <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(99,130,255,0.04)" strokeWidth="1" />
              </pattern>
              <filter id="glow">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />

            {/* Edges */}
            {edges.map((edge) => {
              const from = nodeMap.get(edge.from_id);
              const to = nodeMap.get(edge.to_id);
              if (!from || !to) return null;
              return (
                <g key={`${edge.from_id}-${edge.to_id}`}>
                  <line
                    x1={from.cx} y1={from.cy}
                    x2={to.cx} y2={to.cy}
                    stroke="rgba(99,130,255,0.15)"
                    strokeWidth={1.5 * edge.strength}
                  />
                  {/* Animated data flow dot */}
                  <circle r="2" fill="#6382ff" opacity="0.7">
                    <animateMotion
                      dur={`${3 + Math.random() * 2}s`}
                      repeatCount="indefinite"
                      path={`M${from.cx},${from.cy} L${to.cx},${to.cy}`}
                    />
                  </circle>
                </g>
              );
            })}

            {/* Nodes */}
            {positioned.map((node) => {
              const color = STATUS_COLORS[node.status] ?? "#6b7280";
              const isSelected = selected?.id === node.id;
              const radius = 20 + node.reputation_score * 3;

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.cx}, ${node.cy})`}
                  className="cursor-pointer"
                  onClick={() => setSelected(isSelected ? null : node)}
                >
                  {/* Selection ring */}
                  {isSelected && (
                    <circle
                      r={radius + 10}
                      fill="none"
                      stroke="#6382ff"
                      strokeWidth="1.5"
                      strokeDasharray="4 3"
                      opacity="0.8"
                    >
                      <animateTransform
                        attributeName="transform"
                        type="rotate"
                        from="0"
                        to="360"
                        dur="8s"
                        repeatCount="indefinite"
                      />
                    </circle>
                  )}

                  {/* Status glow */}
                  {node.status === "active" && (
                    <circle r={radius + 6} fill={color} opacity="0.1">
                      <animate attributeName="opacity" values="0.05;0.2;0.05" dur="2s" repeatCount="indefinite" />
                    </circle>
                  )}

                  {/* Main circle */}
                  <circle
                    r={radius}
                    fill={`${color}20`}
                    stroke={color}
                    strokeWidth={isSelected ? 2 : 1.5}
                  />

                  {/* Avatar letter */}
                  <text
                    textAnchor="middle"
                    dominantBaseline="central"
                    fill={color}
                    fontSize={14}
                    fontWeight="700"
                    fontFamily="var(--font-syne)"
                  >
                    {node.name[0]}
                  </text>

                  {/* Status dot */}
                  <circle
                    cx={radius - 4}
                    cy={-(radius - 4)}
                    r={4}
                    fill={color}
                    stroke="var(--surface)"
                    strokeWidth="1.5"
                  />

                  {/* Name label */}
                  <text
                    y={radius + 14}
                    textAnchor="middle"
                    fill="rgba(226,232,240,0.7)"
                    fontSize={11}
                    fontFamily="var(--font-inter)"
                  >
                    {node.name}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* Detail panel */}
        <div className="w-56 shrink-0 space-y-3">
          {selected ? (
            <NodeDetailPanel node={selected} onClose={() => setSelected(null)} />
          ) : (
            <LegendPanel />
          )}
        </div>
      </div>
    </div>
  );
}

function NodeDetailPanel({ node, onClose }: { node: NetworkNode; onClose: () => void }) {
  const color = STATUS_COLORS[node.status] ?? "#6b7280";
  return (
    <div
      className="bg-surface2 rounded-2xl border p-4 space-y-3"
      style={{ borderColor: `${color}40` }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center text-sm font-bold font-syne"
            style={{ background: `${color}30`, color }}
          >
            {node.name[0]}
          </div>
          <span className="font-semibold text-sm">{node.name}</span>
        </div>
        <button onClick={onClose} className="text-muted hover:text-foreground text-lg leading-none">×</button>
      </div>

      <div className="space-y-2">
        {[
          { label: "Status", value: node.status },
          { label: "Reputation", value: `${node.reputation_score.toFixed(1)}/5.0` },
        ].map(({ label, value }) => (
          <div key={label} className="flex justify-between text-xs">
            <span className="text-muted">{label}</span>
            <span className="font-mono">{value}</span>
          </div>
        ))}
      </div>

      <div>
        <p className="text-xs text-muted mb-2">Capabilities</p>
        <div className="flex flex-wrap gap-1">
          {node.capabilities.map((cap) => (
            <span key={cap} className="text-[10px] px-2 py-0.5 rounded-md bg-surface3 border border-border font-mono text-muted">
              {cap}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function LegendPanel() {
  return (
    <div className="bg-surface2 rounded-2xl border border-border p-4 space-y-3">
      <p className="text-xs font-semibold text-muted uppercase tracking-wide">Legend</p>
      <div className="space-y-2">
        {Object.entries(STATUS_COLORS).map(([status, color]) => (
          <div key={status} className="flex items-center gap-2 text-xs">
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
            <span className="capitalize text-muted">{status}</span>
          </div>
        ))}
      </div>
      <div className="pt-2 border-t border-border">
        <p className="text-[10px] text-muted font-mono">Click a node to inspect</p>
        <p className="text-[10px] text-muted font-mono mt-1">Dot size ∝ reputation</p>
      </div>
    </div>
  );
}
