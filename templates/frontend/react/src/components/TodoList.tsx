import { useState, useEffect, useCallback } from "react";

const API_URL = import.meta.env.VITE_API_URL || "";

interface Todo {
  id: string;
  title: string;
  description: string | null;
  completed: boolean;
  created_at: string;
}

export function TodoList({
  token,
  onUnauth,
}: {
  token: string;
  onUnauth: () => void;
}) {
  const [todos, setTodos] = useState<Todo[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  const fetchTodos = useCallback(async () => {
    const res = await fetch(`${API_URL}/api/todos`, { headers });
    if (res.status === 401) {
      onUnauth();
      return;
    }
    setTodos(await res.json());
  }, [token]);

  useEffect(() => {
    fetchTodos();
  }, [fetchTodos]);

  async function addTodo(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    await fetch(`${API_URL}/api/todos`, {
      method: "POST",
      headers,
      body: JSON.stringify({ title, description: description || null }),
    });
    setTitle("");
    setDescription("");
    fetchTodos();
  }

  async function toggleTodo(todo: Todo) {
    await fetch(`${API_URL}/api/todos/${todo.id}`, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ completed: !todo.completed }),
    });
    fetchTodos();
  }

  async function deleteTodo(id: string) {
    await fetch(`${API_URL}/api/todos/${id}`, {
      method: "DELETE",
      headers,
    });
    fetchTodos();
  }

  return (
    <div>
      <form onSubmit={addTodo} style={{ marginBottom: 20 }}>
        <input
          type="text"
          placeholder="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          style={{ width: "70%", padding: 8, marginRight: 8 }}
        />
        <button type="submit" style={{ padding: 8 }}>Add</button>
        <input
          type="text"
          placeholder="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          style={{ width: "100%", padding: 8, marginTop: 8 }}
        />
      </form>

      <ul style={{ listStyle: "none", padding: 0 }}>
        {todos.map((todo) => (
          <li
            key={todo.id}
            style={{
              display: "flex",
              alignItems: "center",
              padding: "8px 0",
              borderBottom: "1px solid #eee",
              gap: 8,
            }}
          >
            <input
              type="checkbox"
              checked={todo.completed}
              onChange={() => toggleTodo(todo)}
            />
            <span
              style={{
                flex: 1,
                textDecoration: todo.completed ? "line-through" : "none",
              }}
            >
              {todo.title}
              {todo.description && (
                <span style={{ color: "#888", marginLeft: 8 }}>
                  {todo.description}
                </span>
              )}
            </span>
            <button onClick={() => deleteTodo(todo.id)}>Delete</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
