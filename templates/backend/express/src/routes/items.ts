import { Router } from "express";
import { pool } from "../db.js";

const router = Router();

router.get("/api/items", async (_req, res) => {
  const result = await pool.query("SELECT * FROM items ORDER BY name");
  res.json(result.rows);
});

router.post("/api/items", async (req, res) => {
  const { name, description } = req.body;
  if (!name) {
    res.status(400).json({ error: "name is required" });
    return;
  }
  const result = await pool.query(
    "INSERT INTO items (name, description) VALUES ($1, $2) RETURNING *",
    [name, description || null],
  );
  res.status(201).json(result.rows[0]);
});

router.get("/api/items/:id", async (req, res) => {
  const result = await pool.query("SELECT * FROM items WHERE id = $1", [
    req.params.id,
  ]);
  if (result.rows.length === 0) {
    res.status(404).json({ error: "Item not found" });
    return;
  }
  res.json(result.rows[0]);
});

router.patch("/api/items/:id", async (req, res) => {
  const { name, description } = req.body;
  const fields: string[] = [];
  const values: unknown[] = [];
  let idx = 1;

  if (name !== undefined) {
    fields.push(`name = $${idx++}`);
    values.push(name);
  }
  if (description !== undefined) {
    fields.push(`description = $${idx++}`);
    values.push(description);
  }

  if (fields.length === 0) {
    res.status(400).json({ error: "no fields to update" });
    return;
  }

  values.push(req.params.id);
  const result = await pool.query(
    `UPDATE items SET ${fields.join(", ")} WHERE id = $${idx} RETURNING *`,
    values,
  );
  if (result.rows.length === 0) {
    res.status(404).json({ error: "Item not found" });
    return;
  }
  res.json(result.rows[0]);
});

router.delete("/api/items/:id", async (req, res) => {
  const result = await pool.query("DELETE FROM items WHERE id = $1", [
    req.params.id,
  ]);
  if (result.rowCount === 0) {
    res.status(404).json({ error: "Item not found" });
    return;
  }
  res.status(204).send();
});

export default router;
