import { Router } from "express";
import { Pool } from "pg";
import bcrypt from "bcryptjs";
import { v4 as uuidv4 } from "uuid";
import { createToken } from "../middleware/auth.js";

export function authRouter(pool: Pool): Router {
  const router = Router();

  router.post("/register", async (req, res) => {
    const { username, password } = req.body;
    if (!username || !password) {
      res.status(400).json({ detail: "Username and password required" });
      return;
    }

    const hash = await bcrypt.hash(password, 10);
    const id = uuidv4();

    try {
      await pool.query(
        "INSERT INTO users (id, username, password_hash) VALUES ($1, $2, $3)",
        [id, username, hash],
      );
      res.status(201).json({ id, username });
    } catch {
      res.status(409).json({ detail: "Username taken" });
    }
  });

  router.post("/login", async (req, res) => {
    const { username, password } = req.body;
    if (!username || !password) {
      res.status(400).json({ detail: "Username and password required" });
      return;
    }

    const result = await pool.query(
      "SELECT id, password_hash FROM users WHERE username = $1",
      [username],
    );
    if (result.rows.length === 0) {
      res.status(401).json({ detail: "Invalid credentials" });
      return;
    }

    const user = result.rows[0];
    const valid = await bcrypt.compare(password, user.password_hash);
    if (!valid) {
      res.status(401).json({ detail: "Invalid credentials" });
      return;
    }

    const token = createToken(user.id);
    res.json({ token });
  });

  return router;
}
