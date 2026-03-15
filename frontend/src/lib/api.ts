import type {
  Agent,
  AgentCreate,
  AgentListResponse,
  AgentUpdate,
  AuthTokenResponse,
  ChatRequest,
  ChatResponse,
  Memory,
  MemoryCreate,
  MemorySearchRequest,
  MemorySearchResponse,
  NetworkGraph,
  Task,
  TaskCreate,
  TaskListResponse,
  TaskListing,
  TaskListingCreate,
  User,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8002";
const API_V1 = `${API_BASE}/api/v1`;

let _accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  _accessToken = token;
  if (typeof window !== "undefined") {
    if (token) localStorage.setItem("lpp_token", token);
    else localStorage.removeItem("lpp_token");
  }
}

export function getAccessToken(): string | null {
  if (_accessToken) return _accessToken;
  if (typeof window !== "undefined") {
    return localStorage.getItem("lpp_token");
  }
  return null;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface FetchOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
  auth?: boolean;
}

async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { params, auth = true, ...fetchOpts } = options;

  let url = `${API_V1}${path}`;
  if (params) {
    const qs = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => [k, String(v)])
    ).toString();
    if (qs) url += `?${qs}`;
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchOpts.headers as Record<string, string>),
  };

  if (auth) {
    const token = getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, { ...fetchOpts, headers });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const err = await response.json();
      detail = err.detail ?? detail;
    } catch {
      /* empty */
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const authApi = {
  register: (data: { did: string; username: string; display_name?: string }) =>
    apiFetch<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
      auth: false,
    }),

  login: (username: string) =>
    apiFetch<AuthTokenResponse>(`/auth/token`, {
      method: "POST",
      params: { username },
      auth: false,
    }),

  getMe: () => apiFetch<User>("/auth/me"),

  updateWallet: (wallet_address: string | null) =>
    apiFetch<User>("/auth/me", {
      method: "PATCH",
      body: JSON.stringify({ wallet_address }),
    }),
};

export const agentsApi = {
  create: (data: AgentCreate) =>
    apiFetch<Agent>("/agents", { method: "POST", body: JSON.stringify(data) }),

  list: (params?: { page?: number; page_size?: number }) =>
    apiFetch<AgentListResponse>("/agents", { params }),

  discover: (params?: { capability?: string; page?: number; page_size?: number }) =>
    apiFetch<AgentListResponse>("/agents/discover", { params, auth: false }),

  get: (id: string) =>
    apiFetch<Agent>(`/agents/${id}`),

  update: (id: string, data: AgentUpdate) =>
    apiFetch<Agent>(`/agents/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

  delete: (id: string) =>
    apiFetch<void>(`/agents/${id}`, { method: "DELETE" }),

  chat: (id: string, data: ChatRequest) =>
    apiFetch<ChatResponse>(`/agents/${id}/chat`, { method: "POST", body: JSON.stringify(data) }),

  chatStream: (id: string, content: string, sessionId?: string) => {
    const token = getAccessToken();
    return fetch(`${API_V1}/agents/${id}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ content, session_id: sessionId, stream: true }),
    });
  },
};

export const memoriesApi = {
  store: (agentId: string, data: MemoryCreate) =>
    apiFetch<Memory>(`/agents/${agentId}/memories`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  list: (agentId: string, params?: { memory_type?: string; page?: number; page_size?: number }) =>
    apiFetch<{ memories: Memory[]; total: number }>(`/agents/${agentId}/memories`, { params }),

  search: (agentId: string, data: MemorySearchRequest) =>
    apiFetch<MemorySearchResponse>(`/agents/${agentId}/memories/search`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  consolidate: (agentId: string) =>
    apiFetch<{ pruned: number; strengthened: number; total: number }>(
      `/agents/${agentId}/memories/consolidate`,
      { method: "POST" }
    ),
};

export const tasksApi = {
  create: (agentId: string, data: TaskCreate) =>
    apiFetch<Task>(`/agents/${agentId}/tasks`, { method: "POST", body: JSON.stringify(data) }),

  list: (agentId: string, params?: { status?: string; page?: number }) =>
    apiFetch<TaskListResponse>(`/agents/${agentId}/tasks`, { params }),

  get: (agentId: string, taskId: string) =>
    apiFetch<Task>(`/agents/${agentId}/tasks/${taskId}`),

  cancel: (agentId: string, taskId: string) =>
    apiFetch<Task>(`/agents/${agentId}/tasks/${taskId}/cancel`, { method: "POST" }),
};

export const marketplaceApi = {
  publish: (data: TaskListingCreate) =>
    apiFetch<TaskListing>("/tasks", { method: "POST", body: JSON.stringify(data) }),

  confirmChainCreated: (listingId: string, txHash: string) =>
    apiFetch<TaskListing>(`/tasks/${listingId}/chain_created`, {
      method: "PATCH",
      body: JSON.stringify({ tx_hash: txHash }),
    }),

  list: (params?: { status?: string; page?: number; page_size?: number }) =>
    apiFetch<TaskListing[]>("/tasks", { params }),

  accept: (listingId: string, agentId: string) =>
    apiFetch<TaskListing>(`/tasks/${listingId}/accept`, {
      method: "POST",
      params: { agent_id: agentId },
    }),

  complete: (listingId: string) =>
    apiFetch<TaskListing>(`/tasks/${listingId}/complete`, { method: "POST" }),

  cancel: (listingId: string) =>
    apiFetch<TaskListing>(`/tasks/${listingId}/cancel`, { method: "POST" }),
};

export const networkApi = {
  graph: () =>
    apiFetch<NetworkGraph>("/network/graph", { auth: false }),

  stats: () =>
    apiFetch<{ total_agents: number; online_agents: number; network_health: string }>(
      "/network/stats",
      { auth: false }
    ),
};

export interface ChainConfig {
  revive_rpc_url: string;
  chain_id: number | null;
  task_market_address: string;
  agent_registry_address: string;
  reputation_address: string;
  configured: boolean;
}

export interface ChainStats {
  connected: boolean;
  block_number: number | null;
  total_agents_on_chain: number | null;
  configured: boolean;
}

export const chainApi = {
  config: () =>
    apiFetch<ChainConfig>("/chain/config", { auth: false }),

  stats: () =>
    apiFetch<ChainStats>("/chain/stats", { auth: false }),
};
