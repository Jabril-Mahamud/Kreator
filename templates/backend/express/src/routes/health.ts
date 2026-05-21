import { Router } from "express";
import { Pool } from "pg";
import client from "prom-client";

const register = new client.Registry();
client.collectDefaultMetrics({ register });

export function healthRouter(pool: Pool): Router {
  const router = Router();

  router.get("/healthz", (_req, res) => {
    res.json({ status: "ok" });
  });

  router.get("/readyz", async (_req, res) => {
    try {
      await pool.query("SELECT 1");
      res.json({ status: "ready" });
    } catch {
      res.status(503).json({ status: "not ready" });
    }
  });

  router.get("/metrics", async (_req, res) => {
    res.set("Content-Type", register.contentType);
    res.end(await register.metrics());
  });

  return router;
}
