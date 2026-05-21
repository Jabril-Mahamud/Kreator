import express from "express";
import cors from "cors";
import { Pool } from "pg";
import { authRouter } from "./routes/auth.js";
import { todosRouter } from "./routes/todos.js";
import { healthRouter } from "./routes/health.js";
import { migrate } from "./database.js";

const app = express();
const port = parseInt(process.env.PORT || "8000", 10);

const pool = new Pool({
  connectionString:
    process.env.DATABASE_URL ||
    "postgres://postgres:postgres@localhost:5432/postgres",
});

app.use(cors());
app.use(express.json());

app.use(healthRouter(pool));
app.use("/api/auth", authRouter(pool));
app.use("/api/todos", todosRouter(pool));

async function main(): Promise<void> {
  await migrate(pool);
  app.listen(port, () => {
    console.log(JSON.stringify({ level: "info", msg: "server starting", port }));
  });
}

main().catch((err) => {
  console.error(JSON.stringify({ level: "error", msg: "startup failed", error: String(err) }));
  process.exit(1);
});
