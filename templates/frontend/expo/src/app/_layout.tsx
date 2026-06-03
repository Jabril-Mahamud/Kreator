import { useEffect, useState, useCallback } from "react";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { AuthContext, getStoredToken, storeToken, clearToken } from "@/lib/auth";
import { api } from "@/lib/api";

export default function RootLayout() {
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStoredToken().then((t) => {
      setToken(t);
      setLoading(false);
    });
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const data = await api.login(username, password);
    await storeToken(data.token);
    setToken(data.token);
  }, []);

  const register = useCallback(async (username: string, password: string) => {
    await api.register(username, password);
    const data = await api.login(username, password);
    await storeToken(data.token);
    setToken(data.token);
  }, []);

  const logout = useCallback(async () => {
    await clearToken();
    setToken(null);
  }, []);

  return (
    <AuthContext.Provider value={{ token, loading, login, register, logout }}>
      <Stack screenOptions={{ headerShown: false }} />
      <StatusBar style="auto" />
    </AuthContext.Provider>
  );
}
