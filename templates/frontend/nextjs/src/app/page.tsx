"use client";

import { useState } from "react";
import { AuthProvider, useAuth } from "../components/AuthContext";
import { LoginForm } from "../components/LoginForm";
import { TodoList } from "../components/TodoList";
import { HealthDot } from "../components/HealthDot";

function AppContent() {
  const { token, logout } = useAuth();

  if (!token) {
    return <LoginForm />;
  }

  return (
    <div style={{ maxWidth: 600, margin: "0 auto", padding: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Todos</h1>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <HealthDot />
          <button onClick={logout}>Logout</button>
        </div>
      </div>
      <TodoList />
    </div>
  );
}

export default function Home() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
