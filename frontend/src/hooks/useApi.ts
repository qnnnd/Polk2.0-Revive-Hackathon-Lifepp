import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import {
  agentsApi,
  chainApi,
  marketplaceApi,
  memoriesApi,
  networkApi,
  tasksApi,
} from "@/lib/api";
import type { ApiError } from "@/lib/api";
import type {
  Agent,
  AgentCreate,
  AgentUpdate,
  ChatRequest,
  ChatResponse,
  Memory,
  MemoryCreate,
  MemorySearchRequest,
  Task,
  TaskCreate,
  TaskListing,
  TaskListingCreate,
} from "@/types";

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
  marketplace: {
    all: ["marketplace"] as const,
    list: (params?: object) => ["marketplace", "list", params] as const,
  },
  network: {
    graph: ["network", "graph"] as const,
    stats: ["network", "stats"] as const,
  },
  chain: {
    config: ["chain", "config"] as const,
    stats: ["chain", "stats"] as const,
  },
} as const;

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
      qc.invalidateQueries({ queryKey: queryKeys.agents.detail(agentId) });
    },
  });
}

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

export function useTasks(agentId: string, params?: { status?: string; page?: number }) {
  return useQuery({
    queryKey: queryKeys.tasks.list(agentId, params),
    queryFn: () => tasksApi.list(agentId, params),
    enabled: Boolean(agentId),
    refetchInterval: (query) => {
      const data = query.state.data as { tasks: Task[] } | undefined;
      const tasks = data?.tasks ?? [];
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

export function useMarketplaceTasks(params?: { status?: string; page?: number }) {
  return useQuery({
    queryKey: queryKeys.marketplace.list(params),
    queryFn: () => marketplaceApi.list(params),
    staleTime: 15_000,
  });
}

export function usePublishTask() {
  const qc = useQueryClient();
  return useMutation<TaskListing, ApiError, TaskListingCreate>({
    mutationFn: (data) => marketplaceApi.publish(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.marketplace.all });
    },
  });
}

export function useAcceptTask() {
  const qc = useQueryClient();
  return useMutation<TaskListing, ApiError, { listingId: string; agentId: string }>({
    mutationFn: ({ listingId, agentId }) => marketplaceApi.accept(listingId, agentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.marketplace.all });
    },
  });
}

export function useCompleteTask() {
  const qc = useQueryClient();
  return useMutation<TaskListing, ApiError, string>({
    mutationFn: (listingId) => marketplaceApi.complete(listingId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.marketplace.all });
    },
  });
}

export function useCancelListing() {
  const qc = useQueryClient();
  return useMutation<TaskListing, ApiError, string>({
    mutationFn: (listingId) => marketplaceApi.cancel(listingId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.marketplace.all });
    },
  });
}

export function useNetworkGraph() {
  return useQuery({
    queryKey: queryKeys.network.graph,
    queryFn: networkApi.graph,
    staleTime: 60_000,
    refetchInterval: 30_000,
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

export function useChainConfig() {
  return useQuery({
    queryKey: queryKeys.chain.config,
    queryFn: chainApi.config,
    staleTime: 60_000,
    retry: false,
  });
}

export function useChainStats() {
  return useQuery({
    queryKey: queryKeys.chain.stats,
    queryFn: chainApi.stats,
    staleTime: 15_000,
    refetchInterval: 20_000,
    retry: false,
  });
}
