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
 */

import "node:crypto";

import { loadConfig } from "./config";
import { TaskQueue } from "./task_queue";
import express from "express";
import pino from "pino";
import { z } from "zod";

const logger = pino.default({ name: "gateway" });
const config = loadConfig();
const app = express.default();
app.use(express.json());

const queue = new TaskQueue({ concurrency: 2 });

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
  const perPage = Math.min(100, Math.max(1, Number(req.query.perPage ?? 20)));
  const all = Array.from(runs.values()).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  res.json({ runs: all.slice((page - 1) * perPage, page * perPage), total: all.length, page });
});
