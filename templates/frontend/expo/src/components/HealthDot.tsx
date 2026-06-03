import { useState, useEffect } from "react";
import { View, StyleSheet } from "react-native";
import { api } from "@/lib/api";

export function HealthDot() {
  const [healthy, setHealthy] = useState(false);

  useEffect(() => {
    let active = true;

    async function check() {
      const ok = await api.healthz();
      if (active) setHealthy(ok);
    }

    check();
    const interval = setInterval(check, 10000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <View
      style={[
        styles.dot,
        { backgroundColor: healthy ? "#22c55e" : "#ef4444" },
      ]}
    />
  );
}

const styles = StyleSheet.create({
  dot: { width: 10, height: 10, borderRadius: 5 },
});
