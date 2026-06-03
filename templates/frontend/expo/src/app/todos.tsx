import { Redirect } from "expo-router";
import { useAuth } from "@/lib/auth";
import TodoScreen from "@/components/TodoScreen";

export default function Todos() {
  const { token, loading } = useAuth();

  if (loading) return null;
  if (!token) return <Redirect href="/" />;
  return <TodoScreen />;
}
