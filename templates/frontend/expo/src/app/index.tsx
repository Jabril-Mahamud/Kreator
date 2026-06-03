import { Redirect } from "expo-router";
import { useAuth } from "@/lib/auth";
import LoginScreen from "@/components/LoginScreen";

export default function Index() {
  const { token, loading } = useAuth();

  if (loading) return null;
  if (token) return <Redirect href="/todos" />;
  return <LoginScreen />;
}
