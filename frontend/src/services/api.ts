/**
 * CEREVIORA — API Service Layer
 *
 * This module is the single place in the frontend that talks to the backend.
 * Every component calls these functions instead of writing raw fetch() calls.
 *
 * Benefits:
 * - Change the base URL once and everything updates.
 * - Consistent error handling across all requests.
 * - TypeScript keeps response shapes accurate.
 *
 * The base URL points to /api which Vite's dev proxy rewrites to
 * http://localhost:8000 (see vite.config.ts).  In production, you'd set
 * VITE_API_BASE_URL to the real API server address.
 */

import type {
  Task,
  TaskListResponse,
  CreateTaskRequest,
  UpdateTaskRequest,
  HealthResponse,
  ExecutionRecord,
} from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';

// ──────────────────────────────────────────────────────────────────────────────
// Utility: unwrap a Response, throw on non-2xx
// ──────────────────────────────────────────────────────────────────────────────
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });

  if (!response.ok) {
    // FastAPI returns { detail: "..." } for error responses
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail ?? 'Unknown API error');
  }

  return response.json() as Promise<T>;
}

// ──────────────────────────────────────────────────────────────────────────────
// Health
// ──────────────────────────────────────────────────────────────────────────────
export const getHealth = (): Promise<HealthResponse> =>
  request<HealthResponse>('/health');

// ──────────────────────────────────────────────────────────────────────────────
// Tasks
// ──────────────────────────────────────────────────────────────────────────────
export const getTasks = (): Promise<TaskListResponse> =>
  request<TaskListResponse>('/tasks');

export const getTask = (id: string): Promise<Task> =>
  request<Task>(`/tasks/${id}`);

export const createTask = (data: CreateTaskRequest): Promise<Task> =>
  request<Task>('/tasks', { method: 'POST', body: JSON.stringify(data) });

export const updateTask = (id: string, data: UpdateTaskRequest): Promise<Task> =>
  request<Task>(`/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(data) });

export const deleteTask = (id: string): Promise<{ message: string }> =>
  request<{ message: string }>(`/tasks/${id}`, { method: 'DELETE' });

// ──────────────────────────────────────────────────────────────────────────────
// Planning & Execution
// ──────────────────────────────────────────────────────────────────────────────
export const planTask = (id: string): Promise<Task> =>
  request<Task>(`/tasks/${id}/plan`, { method: 'POST' });

export const approveTask = (id: string): Promise<Task> =>
  request<Task>(`/tasks/${id}/approve`, { method: 'POST' });

export const executeTask = (id: string): Promise<Task> =>
  request<Task>(`/tasks/${id}/execute`, { method: 'POST' });

// ──────────────────────────────────────────────────────────────────────────────
// Execution History
// ──────────────────────────────────────────────────────────────────────────────
export const getTaskHistory = (id: string): Promise<ExecutionRecord[]> =>
  request<ExecutionRecord[]>(`/tasks/${id}/history`);
