"use client";

import { useState, useEffect } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

export function HealthDot() {
  const [healthy, setHealthy] = useState(false);

  useEffect(() => {
    let active = true;

    async function check() {
      try {
        const res = await fetch(`${API_URL}/healthz`);
        if (active) setHealthy(res.ok);
      } catch {
        if (active) setHealthy(false);
      }
    }

    check();
    const interval = setInterval(check, 10000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <span
      title={healthy ? "Backend connected" : "Backend unreachable"}
      style={{
        display: "inline-block",
        width: 10,
        height: 10,
        borderRadius: "50%",
        backgroundColor: healthy ? "#22c55e" : "#ef4444",
      }}
    />
  );
}
