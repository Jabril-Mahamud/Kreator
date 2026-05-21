import { useState } from "react";
import { LoginForm } from "./components/LoginForm";
import { TodoList } from "./components/TodoList";
import { HealthDot } from "./components/HealthDot";

export function App() {
  const [token, setToken] = useState<string | null>(null);

  if (!token) {
    return <LoginForm onLogin={setToken} />;
  }

  return (
    <div style={{ maxWidth: 600, margin: "0 auto", padding: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Todos</h1>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <HealthDot />
          <button onClick={() => setToken(null)}>Logout</button>
        </div>
      </div>
      <TodoList token={token} onUnauth={() => setToken(null)} />
    </div>
  );
}
