"use client";

import { FormEvent, useEffect, useState } from "react";
import { Item, checkHealth, createItem, listItems } from "@/lib/api";

export default function Home() {
  const [items, setItems] = useState<Item[]>([]);
  const [healthy, setHealthy] = useState<boolean | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const hostname = process.env.NEXT_PUBLIC_HOSTNAME ?? "";

  async function refresh() {
    try {
      setItems(await listItems());
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    refresh();
    checkHealth().then(setHealthy);
    const id = setInterval(() => checkHealth().then(setHealthy), 5000);
    return () => clearInterval(id);
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    await createItem(name, description);
    setName("");
    setDescription("");
    await refresh();
  }

  return (
    <main style={{ maxWidth: 720, margin: "0 auto" }}>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h1>Kreator</h1>
        <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
          <span
            title={healthy ? "backend healthy" : "backend unreachable"}
            style={{
              display: "inline-block",
              width: 12,
              height: 12,
              borderRadius: "50%",
              background: healthy === null ? "#888" : healthy ? "#3fb950" : "#f85149",
            }}
          />
          {hostname && <code style={{ fontSize: 12, opacity: 0.7 }}>{hostname}</code>}
        </div>
      </header>

      <form onSubmit={onSubmit} style={{ display: "grid", gap: "0.5rem", margin: "1.5rem 0" }}>
        <input
          placeholder="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={{ padding: "0.5rem", background: "#161b22", color: "#e6e6e6", border: "1px solid #30363d" }}
        />
        <input
          placeholder="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          style={{ padding: "0.5rem", background: "#161b22", color: "#e6e6e6", border: "1px solid #30363d" }}
        />
        <button type="submit" style={{ padding: "0.5rem", cursor: "pointer" }}>
          Add item
        </button>
      </form>

      {error && <p style={{ color: "#f85149" }}>{error}</p>}

      <ul style={{ listStyle: "none", padding: 0 }}>
        {items.map((item) => (
          <li
            key={item.id}
            style={{ padding: "0.75rem 1rem", border: "1px solid #30363d", marginBottom: "0.5rem", borderRadius: 6 }}
          >
            <strong>{item.name}</strong>
            {item.description && <div style={{ opacity: 0.8 }}>{item.description}</div>}
            <small style={{ opacity: 0.5 }}>{new Date(item.created_at).toLocaleString()}</small>
          </li>
        ))}
      </ul>
    </main>
  );
}
