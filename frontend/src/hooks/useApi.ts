/**
 * Life++ — React Query Hooks
 * Typed data-fetching hooks with caching, optimistic updates, and pagination.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { agentsApi, memoriesApi, networkApi, tasksApi, type ApiError } from "@/lib/api";
import type {
  Agent,
  AgentCreate,
  AgentListResponse,
  AgentUpdate,
  ChatRequest,
  ChatResponse,
  Memory,
  MemoryCreate,
  MemorySearchRequest,
  NetworkGraph,
  Task,
  TaskCreate,
} from "@/types";

// ── Query Keys ────────────────────────────────────────────────────────────

export const queryKeys = {
  agents: {
    all: ["agents"] as const,
    list: (params?: object) => ["agents", "list", params] as const,
    detail: (id: string) => ["agents", id] as const,
    discover: (params?: object) => ["agents", "discover", params] as const,
  },
  memories: {
    list: (agentId: string, params?: object) => ["memories", agentId, params] as const,
    search: (agentId: string, query: string) => ["memories", agentId, "search", query] as const,
  },
  tasks: {
    list: (agentId: string, params?: object) => ["tasks", agentId, params] as const,
    detail: (agentId: string, taskId: string) => ["tasks", agentId, taskId] as const,
  },
  network: {
    graph: ["network", "graph"] as const,
    stats: ["network", "stats"] as const,
  },
} as const;

// ── Agent Hooks ───────────────────────────────────────────────────────────

export function useAgents(params?: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: queryKeys.agents.list(params),
    queryFn: () => agentsApi.list(params),
    staleTime: 30_000,
  });
}

export function useDiscoverAgents(capability?: string) {
  return useQuery({
    queryKey: queryKeys.agents.discover({ capability }),
    queryFn: () => agentsApi.discover({ capability }),
    staleTime: 60_000,
  });
}

export function useAgent(id: string, options?: Partial<UseQueryOptions<Agent>>) {
  return useQuery({
    queryKey: queryKeys.agents.detail(id),
    queryFn: () => agentsApi.get(id),
    enabled: Boolean(id),
    staleTime: 30_000,
    ...options,
  });
}

export function useCreateAgent() {
  const qc = useQueryClient();
  return useMutation<Agent, ApiError, AgentCreate>({
    mutationFn: agentsApi.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.agents.all });
    },
  });
}

export function useUpdateAgent(id: string) {
  const qc = useQueryClient();
  return useMutation<Agent, ApiError, AgentUpdate>({
    mutationFn: (data) => agentsApi.update(id, data),
    onSuccess: (updated) => {
      qc.setQueryData(queryKeys.agents.detail(id), updated);
      qc.invalidateQueries({ queryKey: queryKeys.agents.all });
    },
  });
}

export function useDeleteAgent() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: agentsApi.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.agents.all });
    },
  });
}

export function useChatWithAgent(agentId: string) {
  const qc = useQueryClient();
  return useMutation<ChatResponse, ApiError, ChatRequest>({
    mutationFn: (data) => agentsApi.chat(agentId, data),
    onSuccess: () => {
      // Refetch agent to get updated last_active_at
      qc.invalidateQueries({ queryKey: queryKeys.agents.detail(agentId) });
    },
  });
}

// ── Memory Hooks ──────────────────────────────────────────────────────────

export function useMemories(
  agentId: string,
  params?: { memory_type?: string; page?: number; page_size?: number },
) {
  return useQuery({
    queryKey: queryKeys.memories.list(agentId, params),
    queryFn: () => memoriesApi.list(agentId, params),
    enabled: Boolean(agentId),
    staleTime: 30_000,
  });
}

export function useSearchMemories(agentId: string, request: MemorySearchRequest) {
  return useQuery({
    queryKey: queryKeys.memories.search(agentId, request.query),
    queryFn: () => memoriesApi.search(agentId, request),
    enabled: Boolean(agentId) && Boolean(request.query?.trim()),
    staleTime: 10_000,
  });
}

export function useStoreMemory(agentId: string) {
  const qc = useQueryClient();
  return useMutation<Memory, ApiError, MemoryCreate>({
    mutationFn: (data) => memoriesApi.store(agentId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.memories.list(agentId) });
    },
  });
}

export function useConsolidateMemories(agentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => memoriesApi.consolidate(agentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.memories.list(agentId) });
    },
  });
}

// ── Task Hooks ────────────────────────────────────────────────────────────

export function useTasks(agentId: string, params?: { status?: string; page?: number }) {
  return useQuery({
    queryKey: queryKeys.tasks.list(agentId, params),
    queryFn: () => tasksApi.list(agentId, params),
    enabled: Boolean(agentId),
    refetchInterval: (query) => {
      // Poll while any task is pending/running
      const tasks = (query.state.data as any)?.tasks ?? [];
      const hasActive = tasks.some((t: Task) => ["pending", "running"].includes(t.status));
      return hasActive ? 2_000 : false;
    },
  });
}

export function useCreateTask(agentId: string) {
  const qc = useQueryClient();
  return useMutation<Task, ApiError, TaskCreate>({
    mutationFn: (data) => tasksApi.create(agentId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.tasks.list(agentId) });
    },
  });
}

export function useCancelTask(agentId: string) {
  const qc = useQueryClient();
  return useMutation<Task, ApiError, string>({
    mutationFn: (taskId) => tasksApi.cancel(agentId, taskId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.tasks.list(agentId) });
    },
  });
}

// ── Network Hooks ─────────────────────────────────────────────────────────

export function useNetworkGraph() {
  return useQuery({
    queryKey: queryKeys.network.graph,
    queryFn: networkApi.graph,
    staleTime: 60_000,
    refetchInterval: 30_000,   // Live refresh every 30s
  });
}

export function useNetworkStats() {
  return useQuery({
    queryKey: queryKeys.network.stats,
    queryFn: networkApi.stats,
    staleTime: 30_000,
    refetchInterval: 15_000,
  });
}
