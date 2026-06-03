import { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  Pressable,
  FlatList,
  StyleSheet,
  Alert,
} from "react-native";
import { useAuth } from "@/lib/auth";
import { api, Todo } from "@/lib/api";
import { HealthDot } from "./HealthDot";

export default function TodoScreen() {
  const { token, logout } = useAuth();
  const [todos, setTodos] = useState<Todo[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const fetchTodos = useCallback(async () => {
    if (!token) return;
    try {
      const data = await api.getTodos(token);
      setTodos(data);
    } catch {
      await logout();
    }
  }, [token, logout]);

  useEffect(() => {
    fetchTodos();
  }, [fetchTodos]);

  async function addTodo() {
    if (!title.trim() || !token) return;
    try {
      await api.createTodo(token, title, description || null);
      setTitle("");
      setDescription("");
      fetchTodos();
    } catch (err: any) {
      Alert.alert("Error", err.message);
    }
  }

  async function toggleTodo(todo: Todo) {
    if (!token) return;
    await api.toggleTodo(token, todo.id, !todo.completed);
    fetchTodos();
  }

  async function deleteTodo(id: string) {
    if (!token) return;
    await api.deleteTodo(token, id);
    fetchTodos();
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Todos</Text>
        <HealthDot />
        <View style={{ flex: 1 }} />
        <Pressable onPress={logout}>
          <Text style={styles.logoutText}>Logout</Text>
        </Pressable>
      </View>

      <View style={styles.inputRow}>
        <TextInput
          style={[styles.input, { flex: 1 }]}
          placeholder="Title"
          value={title}
          onChangeText={setTitle}
        />
        <Pressable style={styles.addButton} onPress={addTodo}>
          <Text style={styles.addButtonText}>Add</Text>
        </Pressable>
      </View>

      <TextInput
        style={[styles.input, { marginBottom: 16 }]}
        placeholder="Description (optional)"
        value={description}
        onChangeText={setDescription}
      />

      <FlatList
        data={todos}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={styles.todoRow}>
            <Pressable onPress={() => toggleTodo(item)} style={styles.checkbox}>
              <Text>{item.completed ? "☑" : "☐"}</Text>
            </Pressable>
            <View style={{ flex: 1 }}>
              <Text style={[styles.todoTitle, item.completed && styles.completed]}>
                {item.title}
              </Text>
              {item.description ? (
                <Text style={styles.todoDesc}>{item.description}</Text>
              ) : null}
            </View>
            <Pressable onPress={() => deleteTodo(item.id)}>
              <Text style={styles.deleteText}>Delete</Text>
            </Pressable>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, paddingTop: 60, backgroundColor: "#fff" },
  header: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 16 },
  title: { fontSize: 28, fontWeight: "bold" },
  logoutText: { color: "#ef4444", fontSize: 14 },
  inputRow: { flexDirection: "row", gap: 8, marginBottom: 8 },
  input: {
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
  },
  addButton: {
    backgroundColor: "#111",
    borderRadius: 8,
    paddingHorizontal: 20,
    justifyContent: "center",
  },
  addButtonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  todoRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#eee",
    gap: 8,
  },
  checkbox: { padding: 4 },
  todoTitle: { fontSize: 16 },
  completed: { textDecorationLine: "line-through", color: "#999" },
  todoDesc: { fontSize: 13, color: "#888", marginTop: 2 },
  deleteText: { color: "#ef4444", fontSize: 14 },
});
