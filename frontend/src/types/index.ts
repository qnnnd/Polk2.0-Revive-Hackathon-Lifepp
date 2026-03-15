export type UUID = string;

export type MemoryType = "episodic" | "semantic" | "procedural" | "social" | "working";

export interface User {
  id: UUID;
  did: string;
  username: string;
  display_name: string | null;
  wallet_address: string | null;
  cog_balance: number;
  created_at: string;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
}

export interface Agent {
  id: UUID;
  owner_id: UUID;
  name: string;
  description: string | null;
  status: string;
  model: string;
  capabilities: string[];
  is_public: boolean;
  on_chain_id: string | null;
  created_at: string;
  last_active_at: string | null;
  reputation: Reputation | null;
}

export interface AgentCreate {
  name: string;
  description?: string;
  model?: string;
  system_prompt?: string;
  personality?: Record<string, unknown>;
  capabilities?: string[];
  is_public?: boolean;
}

export interface AgentUpdate {
  name?: string;
  description?: string;
  system_prompt?: string;
  personality?: Record<string, unknown>;
  capabilities?: string[];
  is_public?: boolean;
}

export interface AgentListResponse {
  agents: Agent[];
  total: number;
  page: number;
  page_size: number;
}

export interface ChatRequest {
  content: string;
  session_id?: UUID;
  stream?: boolean;
}

export interface ChatResponse {
  session_id: UUID;
  user_message: Message;
  agent_message: Message;
  memories_used: number;
}

export interface Message {
  id: UUID;
  agent_id: UUID;
  session_id: UUID;
  role: string;
  content: string;
  token_count: number | null;
  latency_ms: number | null;
  created_at: string;
}

export interface Memory {
  id: UUID;
  agent_id: UUID;
  memory_type: MemoryType;
  content: string;
  summary: string | null;
  importance: number;
  strength: number;
  access_count: number;
  tags: string[];
  is_shared: boolean;
  created_at: string;
  last_accessed_at: string;
  relevance_score?: number;
}

export interface MemoryCreate {
  content: string;
  memory_type?: string;
  importance?: number;
  tags?: string[];
  is_shared?: boolean;
}

export interface MemorySearchRequest {
  query: string;
  memory_type?: string;
  top_k?: number;
  min_strength?: number;
}

export interface MemorySearchResponse {
  memories: Memory[];
  query: string;
  total_found: number;
}

export interface Task {
  id: UUID;
  agent_id: UUID;
  title: string;
  description: string | null;
  status: string;
  priority: string;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown> | null;
  error_message: string | null;
  steps: Record<string, unknown>[];
  reward_cog: number;
  escrow_status: string;
  tx_hash: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface TaskCreate {
  title: string;
  description?: string;
  priority?: string;
  input_data?: Record<string, unknown>;
  deadline_at?: string;
  reward_cog?: number;
}

export interface TaskListResponse {
  tasks: Task[];
  total: number;
}

export interface TaskListingCreate {
  title: string;
  description: string;
  required_capabilities?: string[];
  reward_cog: number;
  deadline_at?: string;
}

export interface ChainTxParams {
  to: string;
  data: string;
  value: string;
  chain_id: number;
}

export interface TaskListing {
  id: UUID;
  poster_agent_id: UUID;
  title: string;
  description: string;
  required_capabilities: string[];
  reward_cog: number;
  status: string;
  winning_agent_id: string | null;
  chain_task_id: number | null;
  tx_hash: string | null;
  deadline_at: string | null;
  created_at: string;
  chain_tx_params?: ChainTxParams | null;
}

export interface Reputation {
  score: number;
  tasks_completed: number;
  tasks_failed: number;
  avg_quality_score: number;
  total_cog_earned: number;
  endorsements: number;
}

export interface NetworkNode {
  id: UUID;
  name: string;
  status: string;
  capabilities: string[];
  reputation_score: number;
  x: number | null;
  y: number | null;
}

export interface NetworkEdge {
  from_id: UUID;
  to_id: UUID;
  connection_type: string;
  strength: number;
}

export interface NetworkGraph {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  total_agents: number;
  online_agents: number;
}
