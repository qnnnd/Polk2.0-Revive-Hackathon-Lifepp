"use client";

import { useState } from "react";
import { toast } from "sonner";
import { useTasks, useCreateTask, useCancelTask } from "@/hooks/useApi";
import type { Task, UUID } from "@/types";

const PRIORITY_OPTIONS = ["low", "normal", "high", "critical"] as const;

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  running: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  completed: "bg-green-500/10 text-green-400 border-green-500/20",
  failed: "bg-red-500/10 text-red-400 border-red-500/20",
  cancelled: "bg-gray-500/10 text-gray-400 border-gray-500/20",
};

interface MarketplaceProps {
  agentId: UUID;
}

export function Marketplace({ agentId }: MarketplaceProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<string>("normal");
  const [reward, setReward] = useState("");

  const { data: tasksData, isLoading } = useTasks(agentId);
  const createTask = useCreateTask(agentId);
  const cancelTask = useCancelTask(agentId);

  const tasks: Task[] = tasksData?.tasks ?? [];

  const handleCreateTask = async () => {
    if (!title.trim()) {
      toast.error("Task title is required");
      return;
    }
    try {
      await createTask.mutateAsync({
        title: title.trim(),
        description: description.trim() || undefined,
        priority,
        reward_cog: reward ? parseFloat(reward) : 0,
      });
      toast.success("Task created successfully!");
      setTitle("");
      setDescription("");
      setPriority("normal");
      setReward("");
    } catch (err: any) {
      toast.error(err.message ?? "Failed to create task");
    }
  };

  const handleCancel = async (taskId: string) => {
    try {
      await cancelTask.mutateAsync(taskId);
      toast.success("Task cancelled");
    } catch (err: any) {
      toast.error(err.message ?? "Failed to cancel task");
    }
  };

  return (
    <div className="space-y-6">
      {/* Create task form */}
      <div className="bg-surface2 rounded-2xl border border-border p-6 space-y-4">
        <h2 className="text-sm font-semibold font-syne">Create Task</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Task title"
            className="bg-surface3 border border-border rounded-xl px-4 py-2.5 text-sm placeholder:text-muted outline-none focus:border-accent/50 transition-colors"
          />
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
            className="bg-surface3 border border-border rounded-xl px-4 py-2.5 text-sm outline-none focus:border-accent/50 transition-colors"
          >
            {PRIORITY_OPTIONS.map((p) => (
              <option key={p} value={p}>
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </option>
            ))}
          </select>
        </div>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Task description (optional)"
          rows={3}
          className="w-full bg-surface3 border border-border rounded-xl px-4 py-2.5 text-sm placeholder:text-muted outline-none focus:border-accent/50 transition-colors resize-none"
        />
        <div className="flex items-center gap-4">
          <input
            value={reward}
            onChange={(e) => setReward(e.target.value)}
            placeholder="Reward (IVE)"
            type="number"
            min="0"
            step="0.1"
            className="bg-surface3 border border-border rounded-xl px-4 py-2.5 text-sm placeholder:text-muted outline-none focus:border-accent/50 transition-colors w-40"
          />
          <button
            onClick={handleCreateTask}
            disabled={createTask.isPending || !title.trim()}
            className="bg-accent hover:bg-accent/80 disabled:opacity-50 text-white rounded-xl px-6 py-2.5 text-sm font-semibold transition-all"
          >
            {createTask.isPending ? "Creating…" : "Create Task"}
          </button>
        </div>
      </div>

      {/* Task list */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold font-syne">Tasks ({tasks.length})</h2>
        {isLoading ? (
          <div className="bg-surface2 rounded-2xl border border-border p-8 text-center">
            <p className="text-muted text-sm font-mono animate-pulse">Loading tasks…</p>
          </div>
        ) : tasks.length === 0 ? (
          <div className="bg-surface2 rounded-2xl border border-border p-8 text-center">
            <p className="text-muted text-sm">No tasks yet. Create one above.</p>
          </div>
        ) : (
          tasks.map((task) => (
            <div
              key={task.id}
              className="bg-surface2 rounded-xl border border-border p-4 flex items-center gap-4"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="text-sm font-semibold truncate">{task.title}</h3>
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded-md border capitalize ${
                      STATUS_STYLES[task.status] ?? STATUS_STYLES.pending
                    }`}
                  >
                    {task.status}
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-surface3 border border-border text-muted capitalize">
                    {task.priority}
                  </span>
                </div>
                {task.description && (
                  <p className="text-xs text-muted truncate">{task.description}</p>
                )}
                <div className="flex items-center gap-4 mt-1">
                  <span className="text-[10px] text-muted font-mono">
                    {task.reward_cog > 0 ? `${task.reward_cog} IVE` : "No reward"}
                  </span>
                  <span className="text-[10px] text-muted font-mono">
                    {new Date(task.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              {(task.status === "pending" || task.status === "running") && (
                <button
                  onClick={() => handleCancel(task.id)}
                  disabled={cancelTask.isPending}
                  className="text-xs text-red-400 hover:text-red-300 px-3 py-1.5 rounded-lg border border-red-500/20 hover:bg-red-500/10 transition-all disabled:opacity-50"
                >
                  Cancel
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
