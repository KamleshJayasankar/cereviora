/**
 * CEREVIORA — Shared TypeScript Types
 *
 * These interfaces describe every data shape the frontend uses.
 * They mirror the Pydantic schemas in the backend, keeping the
 * two halves of the application synchronized.
 */

// ──────────────────────────────────────────────────────────────────────────────
// Task status — must match the enum in the backend
// ──────────────────────────────────────────────────────────────────────────────
export type TaskStatus =
  | 'PENDING'
  | 'AWAITING_APPROVAL'
  | 'RUNNING'
  | 'SUCCEEDED'
  | 'FAILED';

// ──────────────────────────────────────────────────────────────────────────────
// Step status — a single step within a task
// ──────────────────────────────────────────────────────────────────────────────
export type StepStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'SKIPPED';

// ──────────────────────────────────────────────────────────────────────────────
// Core domain models
// ──────────────────────────────────────────────────────────────────────────────

export interface TaskStep {
  id: string;
  task_id: string;
  step_number: number;
  title: string;
  description: string;
  step_type: string;
  status: StepStatus;
  result_summary: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  steps: TaskStep[];
}

export interface ExecutionRecord {
  id: string;
  task_id: string;
  step_id: string | null;
  attempt: number;
  event_type: string;
  status: string;
  input_summary: string | null;
  output_summary: string | null;
  error_details: string | null;
  verified: boolean;
  verification_result: string | null;
  created_at: string;
  completed_at: string | null;
}

// ──────────────────────────────────────────────────────────────────────────────
// API request / response shapes
// ──────────────────────────────────────────────────────────────────────────────

export interface CreateTaskRequest {
  title: string;
  description: string;
}

export interface UpdateTaskRequest {
  title?: string;
  description?: string;
}

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  timestamp: string;
}

export interface ApiError {
  detail: string;
}

export interface TaskListResponse {
  tasks: Task[];
  total: number;
  has_more: boolean;
}

export interface TaskCounts {
  PENDING: number;
  AWAITING_APPROVAL: number;
  RUNNING: number;
  SUCCEEDED: number;
  FAILED: number;
  total: number;
}

export type WorkflowNodeId = 'interpret' | 'plan' | 'approve' | 'execute' | 'verify' | 'store';
export type WorkflowNodeStatus = 'idle' | 'awaiting' | 'running' | 'success' | 'failed';

export interface WorkflowNode {
  id: WorkflowNodeId;
  label: string;
  icon: string;
  description: string;
  color: string;
  status: WorkflowNodeStatus;
  statusLabel: string;
  value: string;
  detail: string;
}
