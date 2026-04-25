const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Item = {
  id: string;
  name: string;
  description: string;
  created_at: string;
};

export async function listItems(): Promise<Item[]> {
  const res = await fetch(`${BASE_URL}/api/items`, { cache: "no-store" });
  if (!res.ok) throw new Error(`list failed: ${res.status}`);
  return res.json();
}

export async function createItem(name: string, description: string): Promise<Item> {
  const res = await fetch(`${BASE_URL}/api/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });
  if (!res.ok) throw new Error(`create failed: ${res.status}`);
  return res.json();
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/healthz`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}
