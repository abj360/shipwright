/**
 * server.ts --- Express API gateway fronting agent runs and PR creation
 *
 * Contains:
 *   runRequestSchema: validates POST /runs bodies
 *   prRequestSchema: validates POST /prs bodies
 *   app: the configured Express application
 *   GET /health: liveness probe
 *   POST /webhooks/github: HMAC-verified issue and comment triggers
 *   POST /runs: enqueues one agent run
 *   GET /runs/:id: fetches one run record
 *   GET /runs: lists run records
 *   error middleware: logs and returns 500
 *   GET /runs/:id/diff: returns the run's working-tree diff
 *   GET /runs/:id/logs: streams run status over SSE
 *   WS /runs/:id/stream: streams the run's output live
 *   attachStream(): serves the run output websocket
 *   404 handler: catches unmatched routes
 */

import { randomUUID } from "node:crypto";
import type { IncomingMessage } from "node:http";
import type { Duplex } from "node:stream";

import { loadConfig } from "./config";
import { createPrFromRun, type SidecarConfig } from "./github_sidecar";
import { SpawnRunExecutor, type RunExecutor } from "./run_executor";
import { RunStreams } from "./run_streams";
import { TaskQueue } from "./task_queue";
import { createWebhookRouter } from "./webhooks";
import express from "express";
import pino from "pino";
import { WebSocketServer, type WebSocket } from "ws";
import { z } from "zod";

const logger = pino({ name: "gateway" });
const config = loadConfig();
export const app = express();
app.use(express.json());
app.use((req, res, next) => {
  req.headers["x-request-id"] = req.headers["x-request-id"] ?? randomUUID();
  res.setHeader("x-request-id", String(req.headers["x-request-id"]));
  next();
});

const queue = new TaskQueue({ concurrency: 2 });

export const prRequestSchema = z.object({
  taskId: z.string().min(1),
  summary: z.string().min(1),
});

export const runRequestSchema = z.object({
  task: z.string().min(1),
  issueUrl: z.string().url().optional(),
  repo: z.string().min(1).optional(),
});

type RunStatus = "queued" | "running" | "done" | "failed";

interface RunRecord {
  id: string;
  task: string;
  repo: string;
  status: RunStatus;
  createdAt: string;
  diff: string;
}

const runs = new Map<string, RunRecord>();
const streams = new RunStreams();
const executor: RunExecutor = new SpawnRunExecutor({
  python: config.AGENT_PYTHON,
  cwd: config.AGENT_CWD,
});

const STREAM_PATH = /^\/runs\/([^/]+)\/stream$/;
// A normal closure tells the viewer the run ended, so it stops reconnecting
// and replaying the buffer it has already shown.
const STREAM_COMPLETE_CODE = 1000;

function isAuthorized(header: string | undefined): boolean {
  /**
   * Decides whether a request carries the gateway bearer token.
   *
   * @param header - Value of the Authorization header, when present.
   * @returns authorized - True when the token matches.
   */
  return header === `Bearer ${config.GATEWAY_TOKEN}`;
}

export function attachStream(server: import("node:http").Server): WebSocketServer {
  /**
   * Serves the run output websocket on the same port as the REST API.
   *
   * The upgrade is authenticated by hand: express middleware never sees an
   * upgrade request, so without this check the socket would bypass the bearer
   * token that guards every other run route.
   *
   * @param server - HTTP server to attach the websocket handler to.
   * @returns wss - The websocket server, so callers can close it on shutdown.
   */
  const wss = new WebSocketServer({ noServer: true });

  server.on("upgrade", (request: IncomingMessage, socket: Duplex, head: Buffer) => {
    const match = STREAM_PATH.exec(request.url ?? "");
    if (match === null) {
      socket.destroy();
      return;
    }
    if (!isAuthorized(request.headers.authorization)) {
      socket.write("HTTP/1.1 401 Unauthorized\r\n\r\n");
      socket.destroy();
      return;
    }
    const runId = match[1];
    if (runId === undefined || !runs.has(runId)) {
      socket.write("HTTP/1.1 404 Not Found\r\n\r\n");
      socket.destroy();
      return;
    }
    wss.handleUpgrade(request, socket, head, (ws) => {
      wss.emit("connection", ws, request);
      followRun(ws, runId);
    });
  });

  return wss;
}

function followRun(ws: WebSocket, runId: string): void {
  /**
   * Replays a run's buffered output to one socket, then keeps it live.
   *
   * @param ws - Socket to write output lines to.
   * @param runId - Run to follow.
   */
  const unsubscribe = streams.subscribe(runId, (line) => {
    if (ws.readyState === ws.OPEN) {
      ws.send(`${line}\n`);
    }
  });
  const finish = () => ws.close(STREAM_COMPLETE_CODE, "run complete");
  const cancelOnEnd = streams.onEnd(runId, finish);
  const detach = () => {
    unsubscribe();
    cancelOnEnd();
  };
  if (streams.hasEnded(runId)) {
    finish();
  }
  ws.on("close", detach);
  ws.on("error", detach);
}

const sidecarConfig: SidecarConfig = {
  repoUrl: config.REPO_URL,
  workDir: config.WORK_DIR,
  githubToken: config.GITHUB_TOKEN,
  baseBranch: config.BASE_BRANCH,
};

app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

app.use(createWebhookRouter(config.WEBHOOK_SECRET, queue));

app.use((req, res, next) => {
  if (req.path === "/health" || req.path.startsWith("/webhooks")) {
    next();
    return;
  }
  if (!isAuthorized(req.header("authorization"))) {
    res.status(401).json({ error: "unauthorized" });
    return;
  }
  next();
});

app.post("/runs", (req, res) => {
  const parsed = runRequestSchema.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.issues });
    return;
  }
  const id = randomUUID();
  const runRecord: RunRecord = {
    id,
    task: parsed.data.task,
    repo: parsed.data.repo ?? config.AGENT_REPO,
    status: "queued",
    createdAt: new Date().toISOString(),
    diff: "",
  };
  runs.set(id, runRecord);
  queue.enqueue(id, async () => {
    runRecord.status = "running";
    logger.info({ runId: id, repo: runRecord.repo }, "run started");
    try {
      const outcome = await executor.execute(
        { runId: id, task: runRecord.task, repo: runRecord.repo },
        (line) => streams.append(id, line),
      );
      runRecord.diff = outcome.diff;
      runRecord.status = outcome.exitCode === 0 ? "done" : "failed";
    } finally {
      streams.end(id);
      logger.info({ runId: id, status: runRecord.status }, "run finished");
    }
  });
  res.status(202).json(runRecord);
});

app.get("/runs/:id", (req, res) => {
  const record = runs.get(req.params.id);
  if (record === undefined) {
    res.status(404).json({ error: "run not found" });
    return;
  }
  res.json(record);
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

app.get("/runs/:id/diff", (req, res) => {
  const record = runs.get(req.params.id);
  if (record === undefined) {
    res.status(404).json({ error: "run not found" });
    return;
  }
  res.type("text/plain").send(record.diff);
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

app.use((err: Error, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  logger.error({ err }, "unhandled route error");
  res.status(500).json({ error: "internal error" });
});

app.use((_req, res) => {
  res.status(404).json({ error: "not found" });
});

if (require.main === module) {
  const port = config.PORT;
  const server = app.listen(port, () => {
    logger.info({ port }, "gateway listening");
  });
  const wss = attachStream(server);
  for (const signal of ["SIGINT", "SIGTERM"] as const) {
    process.on(signal, () => {
      logger.info({ signal }, "shutting down");
      wss.close();
      server.close(() => process.exit(0));
    });
  }
}
