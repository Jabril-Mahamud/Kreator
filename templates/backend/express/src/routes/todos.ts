import { Router, Response } from "express";
import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";
import { authenticate, AuthRequest } from "../middleware/auth.js";

export function todosRouter(pool: Pool): Router {
  const router = Router();
  router.use(authenticate);

  router.get("/", async (req: AuthRequest, res: Response) => {
    const result = await pool.query(
      "SELECT id, title, description, completed, created_at FROM todos WHERE user_id = $1 ORDER BY created_at DESC",
      [req.userId],
    );
    res.json(result.rows);
  });

  router.post("/", async (req: AuthRequest, res: Response) => {
    const { title, description } = req.body;
    if (!title) {
      res.status(400).json({ detail: "Title required" });
      return;
    }

    const id = uuidv4();
    const result = await pool.query(
      "INSERT INTO todos (id, user_id, title, description) VALUES ($1, $2, $3, $4) RETURNING id, title, description, completed, created_at",
      [id, req.userId, title, description || null],
    );
    res.status(201).json(result.rows[0]);
  });

  router.get("/:id", async (req: AuthRequest, res: Response) => {
    const result = await pool.query(
      "SELECT id, title, description, completed, created_at FROM todos WHERE id = $1 AND user_id = $2",
      [req.params.id, req.userId],
    );
    if (result.rows.length === 0) {
      res.status(404).json({ detail: "Todo not found" });
      return;
    }
    res.json(result.rows[0]);
  });

  router.patch("/:id", async (req: AuthRequest, res: Response) => {
    const existing = await pool.query(
      "SELECT id, title, description, completed FROM todos WHERE id = $1 AND user_id = $2",
      [req.params.id, req.userId],
    );
    if (existing.rows.length === 0) {
      res.status(404).json({ detail: "Todo not found" });
      return;
    }

    const current = existing.rows[0];
    const title = req.body.title ?? current.title;
    const description = req.body.description ?? current.description;
    const completed = req.body.completed ?? current.completed;

    const result = await pool.query(
      "UPDATE todos SET title = $1, description = $2, completed = $3 WHERE id = $4 AND user_id = $5 RETURNING id, title, description, completed, created_at",
      [title, description, completed, req.params.id, req.userId],
    );
    res.json(result.rows[0]);
  });

  router.delete("/:id", async (req: AuthRequest, res: Response) => {
    const result = await pool.query(
      "DELETE FROM todos WHERE id = $1 AND user_id = $2",
      [req.params.id, req.userId],
    );
    if (result.rowCount === 0) {
      res.status(404).json({ detail: "Todo not found" });
      return;
    }
    res.status(204).send();
  });

  return router;
}
