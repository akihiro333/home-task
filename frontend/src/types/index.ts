export interface User {
  id: number;
  email: string;
  created_at: string;
}

export interface Organization {
  id: number;
  name: string;
  subdomain: string;
  created_at: string;
}

export interface Task {
  id: number;
  org_id: number;
  title: string;
  description?: string;
  status: 'todo' | 'doing' | 'done';
  assignee_id?: number;
  due_date?: string;
  created_at: string;
  updated_at: string;
}

export interface TasksResponse {
  tasks: Task[];
  has_more: boolean;
  next_cursor?: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginResponse {
  otp_required?: boolean;
  access_token?: string;
  refresh_token?: string;
  token_type?: string;
}

export interface WebSocketMessage {
  type: 'connected' | 'task_created' | 'task_updated' | 'task_deleted' | 'ping' | 'pong' | 'heartbeat';
  org_id?: number;
  user_id?: number;
  task?: Task;
}

export interface CreateTaskRequest {
  title: string;
  description?: string;
  status: 'todo' | 'doing' | 'done';
  assignee_id?: number;
  due_date?: string;
}

export interface UpdateTaskRequest {
  title?: string;
  description?: string;
  status?: 'todo' | 'doing' | 'done';
  assignee_id?: number;
  due_date?: string;
}