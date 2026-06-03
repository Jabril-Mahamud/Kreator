import Constants from "expo-constants";

const API_URL = Constants.expoConfig?.extra?.apiUrl || "http://localhost:8000";

type RequestOptions = {
  method?: string;
  headers?: Record<string, string>;
  body?: unknown;
};

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: opts.method || "GET",
    headers: {
      "Content-Type": "application/json",
      ...opts.headers,
    },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

export const api = {
  healthz: () => fetch(`${API_URL}/healthz`).then((r) => r.ok).catch(() => false),

  login: (username: string, password: string) =>
    request<{ token: string }>("/api/auth/login", {
      method: "POST",
      body: { username, password },
    }),

  register: (username: string, password: string) =>
    request<void>("/api/auth/register", {
      method: "POST",
      body: { username, password },
    }),

  getTodos: (token: string) =>
    request<Todo[]>("/api/todos", { headers: authHeaders(token) }),

  createTodo: (token: string, title: string, description: string | null) =>
    request<Todo>("/api/todos", {
      method: "POST",
      headers: authHeaders(token),
      body: { title, description },
    }),

  toggleTodo: (token: string, id: string, completed: boolean) =>
    request<Todo>(`/api/todos/${id}`, {
      method: "PATCH",
      headers: authHeaders(token),
      body: { completed },
    }),

  deleteTodo: (token: string, id: string) =>
    request<void>(`/api/todos/${id}`, {
      method: "DELETE",
      headers: authHeaders(token),
    }),
};

export interface Todo {
  id: string;
  title: string;
  description: string | null;
  completed: boolean;
  created_at: string;
}
