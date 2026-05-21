"use client";

import { useState } from "react";
import { useAuth } from "./AuthContext";

export function LoginForm() {
  const { login, register } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isRegister, setIsRegister] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      if (isRegister) {
        await register(username, password);
        await login(username, password);
      } else {
        await login(username, password);
      }
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <div style={{ maxWidth: 400, margin: "100px auto", padding: 20 }}>
      <h1>{isRegister ? "Register" : "Login"}</h1>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 12 }}>
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            style={{ width: "100%", padding: 8, boxSizing: "border-box" }}
          />
        </div>
        <div style={{ marginBottom: 12 }}>
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ width: "100%", padding: 8, boxSizing: "border-box" }}
          />
        </div>
        {error && <p style={{ color: "red" }}>{error}</p>}
        <button type="submit" style={{ width: "100%", padding: 10, marginBottom: 8 }}>
          {isRegister ? "Register" : "Login"}
        </button>
        <button
          type="button"
          onClick={() => setIsRegister(!isRegister)}
          style={{ width: "100%", padding: 10, background: "none", border: "1px solid #ccc" }}
        >
          {isRegister ? "Already have an account? Login" : "Need an account? Register"}
        </button>
      </form>
    </div>
  );
}
