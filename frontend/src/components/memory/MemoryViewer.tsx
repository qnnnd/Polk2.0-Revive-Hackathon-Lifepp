"use client";

import { useState } from "react";
import { toast } from "sonner";
import {
  useConsolidateMemories,
  useMemories,
  useSearchMemories,
  useStoreMemory,
} from "@/hooks/useApi";
import type { Memory, MemoryType, UUID } from "@/types";

const MEMORY_META: Record<MemoryType, { color: string; icon: string; description: string }> = {
  episodic:   { color: "#6382ff", icon: "◉", description: "Events & conversations" },
  semantic:   { color: "#34d399", icon: "◈", description: "Knowledge & facts" },
  procedural: { color: "#f59e0b", icon: "⬡", description: "Skills & workflows" },
  social:     { color: "#f472b6", icon: "◇", description: "Agent relationships" },
  working:    { color: "#a78bfa", icon: "◎", description: "Short-term context" },
};

interface MemoryViewerProps {
  agentId: UUID;
}

export function MemoryViewer({ agentId }: MemoryViewerProps) {
  const [filter, setFilter] = useState<MemoryType | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);

  const { data: memoriesData, isLoading } = useMemories(
    agentId,
    filter !== "all" ? { memory_type: filter } : undefined
  );

  const { data: searchResults } = useSearchMemories(
    agentId,
    { query: searchQuery, top_k: 10 },
  );

  const consolidateMutation = useConsolidateMemories(agentId);

  const displayMemories =
    isSearching && searchQuery.trim()
      ? searchResults?.memories ?? []
      : memoriesData?.memories ?? [];

  const handleConsolidate = async () => {
    try {
      const result = await consolidateMutation.mutateAsync();
      toast.success(`Consolidation complete: ${result.pruned} pruned, ${result.total - result.pruned} retained`);
    } catch {
      toast.error("Consolidation failed");
    }
  };

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Memory type tabs */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => setFilter("all")}
          className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-all border ${
            filter === "all"
              ? "bg-accent/20 border-accent/40 text-accent"
              : "bg-surface2 border-border text-muted hover:text-foreground"
          }`}
        >
          All ({memoriesData?.total ?? 0})
        </button>
        {(Object.keys(MEMORY_META) as MemoryType[]).map((type) => {
          const meta = MEMORY_META[type];
          return (
            <button
              key={type}
              onClick={() => setFilter(type)}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-all border capitalize ${
                filter === type
                  ? "border-opacity-40 text-opacity-100"
                  : "bg-surface2 border-border text-muted hover:text-foreground"
              }`}
              style={
                filter === type
                  ? { background: `${meta.color}20`, borderColor: `${meta.color}40`, color: meta.color }
                  : undefined
              }
            >
              {meta.icon} {type}
            </button>
          );
        })}

        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={handleConsolidate}
            disabled={consolidateMutation.isPending}
            className="text-xs px-3 py-1.5 rounded-lg border border-border bg-surface2 text-muted hover:text-foreground disabled:opacity-50 transition-all"
          >
            {consolidateMutation.isPending ? "Consolidating…" : "⟳ Consolidate"}
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <input
          value={searchQuery}
          onChange={(e) => {
            setSearchQuery(e.target.value);
            setIsSearching(true);
          }}
          placeholder="Semantic search across memories…"
          className="form-input w-full rounded-xl px-4 py-2.5 text-sm font-mono"
        />
        {isSearching && searchQuery && (
          <button
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-foreground text-lg"
            onClick={() => { setSearchQuery(""); setIsSearching(false); }}
          >
            ×
          </button>
        )}
      </div>

      {/* Memory list */}
      {isLoading ? (
        <div className="flex-1 flex items-center justify-center text-muted text-sm font-mono animate-pulse">
          Loading memories…
        </div>
      ) : displayMemories.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-2 text-muted">
          <span className="text-3xl">◎</span>
          <p className="text-sm">No memories found</p>
          {isSearching && <p className="text-xs font-mono">Try a different search query</p>}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-3 pr-1">
          {displayMemories.map((memory) => (
            <MemoryCard key={memory.id} memory={memory} />
          ))}
        </div>
      )}
    </div>
  );
}

function MemoryCard({ memory }: { memory: Memory }) {
  const [expanded, setExpanded] = useState(false);
  const meta = MEMORY_META[memory.memory_type] ?? MEMORY_META.episodic;

  return (
    <div
      className="bg-surface2 rounded-xl border p-4 space-y-3 cursor-pointer hover:border-opacity-60 transition-all"
      style={{ borderColor: `${meta.color}30` }}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-start gap-3">
        <div
          className="w-8 h-8 rounded-lg shrink-0 flex items-center justify-center text-base"
          style={{ background: `${meta.color}15`, color: meta.color }}
        >
          {meta.icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className="text-[10px] font-mono px-2 py-0.5 rounded-md capitalize"
              style={{ background: `${meta.color}15`, color: meta.color }}
            >
              {memory.memory_type}
            </span>
            {memory.is_shared && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-surface3 text-muted border border-border">
                shared
              </span>
            )}
            <span className="text-[10px] text-muted font-mono ml-auto">
              {new Date(memory.created_at).toLocaleDateString()}
            </span>
          </div>
          <p className={`text-sm leading-relaxed ${!expanded ? "line-clamp-2" : ""}`}>
            {memory.content}
          </p>
        </div>
      </div>

      {/* Strength bars */}
      <div className="flex gap-4">
        {[
          { label: "Importance", value: memory.importance, color: "#f59e0b" },
          { label: "Strength", value: memory.strength, color: meta.color },
          ...(memory.relevance_score !== undefined
            ? [{ label: "Relevance", value: memory.relevance_score, color: "#34d399" }]
            : []),
        ].map(({ label, value, color }) => (
          <div key={label} className="flex-1">
            <div className="flex justify-between text-[10px] text-muted font-mono mb-1">
              <span>{label}</span>
              <span>{(value * 100).toFixed(0)}%</span>
            </div>
            <div className="h-1 bg-surface3 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${value * 100}%`, background: color }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Tags */}
      {memory.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {memory.tags.map((tag) => (
            <span key={tag} className="text-[10px] px-2 py-0.5 rounded-md bg-surface3 text-muted font-mono">
              #{tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
