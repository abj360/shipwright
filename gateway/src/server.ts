#!/usr/bin/env ts-node
/**
 * server.ts --- Express API gateway fronting agent runs and PR creation
 *
 * Contains:
 *   runRequestSchema: validates POST /runs bodies
 *   GET /health: liveness probe
 *   POST /runs: enqueues one agent run
 *   GET /runs/:id: fetches one run record
 *   GET /runs: lists run records
 *   error middleware: logs and returns 500
 *   GET /runs/:id/logs: streams run status over SSE
 */

import "node:crypto";

import { loadConfig } from "./config";
import { createPrFromRun } from "./github_sidecar";
import { TaskQueue } from "./task_queue";
import express from "express";
import pino from "pino";
import { z } from "zod";

const logger = pino.default({ name: "gateway" });
const config = loadConfig();
const app = express.default();
app.use(express.json());
app.use((req, res, next) => {
  req.headers["x-request-id"] = req.headers["x-request-id"] ?? crypto.randomUUID();
  res.setHeader("x-request-id", String(req.headers["x-request-id"]));
  next();
});

const queue = new TaskQueue({ concurrency: 2 });

const prRequestSchema = z.object({
  taskId: z.string().min(1),
  summary: z.string().min(1),
});

const runRequestSchema = z.object({
  task: z.string().min(1),
  issueUrl: z.string().url().optional(),
});

type RunStatus = "queued" | "running" | "done" | "failed";

interface RunRecord {
  id: string;
  task: string;
  status: RunStatus;
  createdAt: string;
}

const runs = new Map<string, RunRecord>();

app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

app.use((req, res, next) => {
  if (req.path === "/health" || req.path.startsWith("/webhooks")) {
    next();
    return;
  }
  const token = req.header("authorization") ?? "";
  if (token !== `Bearer ${config.GATEWAY_TOKEN}`) {
    res.status(401).json({ error: "unauthorized" });
    return;
  }
  next();
});

app.post("/runs", async (req, res) => {
  const parsed = runRequestSchema.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.issues });
    return;
  }
  const id = crypto.randomUUID();
  const runRecord: RunRecord = {
    id,
    task: parsed.data.task,
    status: "queued",
    createdAt: new Date().toISOString(),
  };
  runs.set(id, record);
  await queue.enqueue(id, async () => {
    record.status = "running";
    logger.info({ runId: id }, "run started");
    record.status = "done";
  });
  res.status(202).json(record);
});

app.get("/runs/:id", (req, res) => {
  const record = runs.get(req.params.id);
  if (record === undefined) {
    res.status(404).json({ error: "run not found" });
    return;
  }
  res.json(record);
});

const port = config.PORT;
app.listen(port, () => {
  logger.info({ port }, "gateway listening");
});

app.get("/runs", (req, res) => {
  const page = Math.max(1, Number(req.query.page ?? 1));
  const perPage = Math.min(200, Math.max(1, Number(req.query.perPage ?? 20)));
  const all = Array.from(runs.values()).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  res.json({ runs: all.slice((page - 1) * perPage, page * perPage), total: all.length, page });
});

app.post("/prs", async (req, res) => {
  const parsed = prRequestSchema.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.issues });
    return;
  }
  try {
    const result = await createPrFromRun(sidecarConfig, parsed.data.taskId, parsed.data.summary);
    res.status(result.prUrl === null ? 502 : 201).json(result);
  } catch (error) {
    logger.error({ err: error }, "PR creation failed after retries");
    res.status(502).json({ error: "github api unavailable; try again later" });
  }
});

app.use((err: Error, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  logger.error({ err }, "unhandled route error");
  res.status(500).json({ error: "internal error" });
});

app.get("/runs/:id/logs", (req, res) => {
  const record = runs.get(req.params.id);
  if (record === undefined) {
    res.status(404).json({ error: "run not found" });
    return;
  }
  res.setHeader("content-type", "text/event-stream");
  res.write(`event: status\ndata: ${JSON.stringify(record)}\n\n`);
  const timer = setInterval(() => {
    res.write(`event: ping\ndata: {}\n\n`);
  }, 5_000);
  req.on("close", () => clearInterval(timer));
});
