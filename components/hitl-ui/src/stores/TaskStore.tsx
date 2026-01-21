import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ProtocolListItem } from '@/lib/api';
import { listProtocols } from '@/lib/api';

export type TaskType = 'extraction' | 'grounding';
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed';

export type Task = {
  /** Task identifier (we use protocol_id for now). */
  id: string;
  type: TaskType;
  protocolTitle: string;
  status: TaskStatus;
  progress: number | null; // 0-100, null means unknown
  message: string;
  updatedAt: number;
};

type TaskStoreValue = {
  tasks: Task[];
  upsertTask: (task: Task) => void;
  removeTask: (id: string) => void;
  clearCompleted: () => void;
};

const TaskStoreContext = createContext<TaskStoreValue | null>(null);

function toTaskStatus(processingStatus: string | undefined): TaskStatus {
  const s = (processingStatus ?? 'pending').toLowerCase();
  if (s === 'failed') return 'failed';
  if (s === 'completed') return 'completed';
  if (s === 'extracting' || s === 'grounding' || s === 'pending') return 'running';
  return 'running';
}

function toProgress(item: ProtocolListItem): number | null {
  const total = item.total_estimated ?? 0;
  const done = item.processed_count ?? 0;
  if (!total || total <= 0) return null;
  return Math.max(0, Math.min(100, (100 * done) / total));
}

function toMessage(item: ProtocolListItem): string {
  return (
    (item as unknown as { progress_message?: string | null }).progress_message ??
    item.processing_status ??
    'Working…'
  );
}

function inferType(item: ProtocolListItem): TaskType {
  const s = (item.processing_status ?? '').toLowerCase();
  if (s === 'grounding') return 'grounding';
  return 'extraction';
}

function isActive(item: ProtocolListItem): boolean {
  const s = (item.processing_status ?? '').toLowerCase();
  return s === 'pending' || s === 'extracting' || s === 'grounding';
}

export function TaskStoreProvider({ children }: { children: React.ReactNode }) {
  const [byId, setById] = useState<Record<string, Task>>({});
  const pollTimer = useRef<number | null>(null);

  const upsertTask = useCallback((task: Task) => {
    setById(prev => {
      const existing = prev[task.id];
      if (existing && existing.updatedAt > task.updatedAt) return prev;
      return { ...prev, [task.id]: task };
    });
  }, []);

  const removeTask = useCallback((id: string) => {
    setById(prev => {
      if (!prev[id]) return prev;
      const next = { ...prev };
      // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
      delete next[id];
      return next;
    });
  }, []);

  const clearCompleted = useCallback(() => {
    setById(prev => {
      const next: Record<string, Task> = {};
      for (const [id, task] of Object.entries(prev)) {
        if (task.status === 'running' || task.status === 'pending') next[id] = task;
      }
      return next;
    });
  }, []);

  // Poll the protocol list and keep tasks in sync.
  useEffect(() => {
    const poll = async () => {
      try {
        const resp = await listProtocols({ skip: 0, limit: 100 });
        const now = Date.now();
        const active = resp.protocols.filter(isActive);
        setById(prev => {
          const next = { ...prev };

          for (const p of active) {
            const id = p.protocol_id;
            next[id] = {
              id,
              type: inferType(p),
              protocolTitle: p.title,
              status: toTaskStatus(p.processing_status),
              progress: toProgress(p),
              message: toMessage(p),
              updatedAt: now,
            };
          }

          // Mark tasks completed/failed when they disappear from active set.
          for (const [id, t] of Object.entries(next)) {
            if (t.status !== 'running') continue;
            const stillActive = active.some(p => p.protocol_id === id);
            if (!stillActive) {
              // We don't know exact terminal state without fetching detail; keep as running unless
              // it was recently updated by list response.
              // Leave it alone.
            }
          }

          return next;
        });
      } catch {
        // Best-effort polling; UI should remain usable even if this fails.
      }
    };

    void poll();
    pollTimer.current = window.setInterval(() => void poll(), 2000);
    return () => {
      if (pollTimer.current) window.clearInterval(pollTimer.current);
      pollTimer.current = null;
    };
  }, []);

  const tasks = useMemo(() => Object.values(byId).sort((a, b) => b.updatedAt - a.updatedAt), [byId]);

  const value = useMemo<TaskStoreValue>(
    () => ({
      tasks,
      upsertTask,
      removeTask,
      clearCompleted,
    }),
    [tasks, upsertTask, removeTask, clearCompleted]
  );

  return <TaskStoreContext.Provider value={value}>{children}</TaskStoreContext.Provider>;
}

export function useTaskStore(): TaskStoreValue {
  const ctx = useContext(TaskStoreContext);
  if (!ctx) {
    throw new Error('useTaskStore must be used within TaskStoreProvider');
  }
  return ctx;
}

