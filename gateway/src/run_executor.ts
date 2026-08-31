/**
 * run_executor.ts --- drives the agent CLI for one run and captures its output
 *
 * Contains:
 *   RunRequest: what one run needs to execute
 *   RunOutcome: exit status and working-tree diff of a finished run
 *   RunExecutor: executes one run, streaming output line by line
 *   SpawnRunExecutor: runs the agent CLI as a child process
 *   snapshotTree(): records the checkout state as a git tree
 *   diffSince(): diffs the checkout against a pre-run snapshot
 */

import { execFile, spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";

import pino from "pino";

const execFileAsync = promisify(execFile);
const logger = pino({ name: "run-executor" });

const AGENT_MODULE = "agent.cli";
const DIFF_MAX_BUFFER_BYTES = 16 * 1024 * 1024;

export interface RunRequest {
  runId: string;
  task: string;
  repo: string;
}

export interface RunOutcome {
  exitCode: number;
  diff: string;
}

export interface RunExecutor {
  execute(request: RunRequest, onLine: (line: string) => void): Promise<RunOutcome>;
}

export interface SpawnRunExecutorOptions {
  python: string;
  cwd: string;
  env?: NodeJS.ProcessEnv;
}

export class SpawnRunExecutor implements RunExecutor {
  /**
   * Runs the agent CLI as a child process and streams its output.
   *
   * Attributes:
   *   python: Interpreter used to launch the agent module.
   *   cwd: Directory the agent module is importable from.
   */

  private readonly python: string;
  private readonly cwd: string;
  private readonly env: NodeJS.ProcessEnv;

  constructor(options: SpawnRunExecutorOptions) {
    this.python = options.python;
    this.cwd = options.cwd;
    this.env = options.env ?? process.env;
  }

  async execute(request: RunRequest, onLine: (line: string) => void): Promise<RunOutcome> {
    /**
     * Runs one agent task, forwarding each output line as it arrives.
     *
     * @param request - Run id, task text, and checkout to work in.
     * @param onLine - Called once per line of agent output.
     * @returns outcome - Exit status and the resulting working-tree diff.
     */
    const args = ["-m", AGENT_MODULE, "--task", request.task, "--repo", request.repo, "--headless"];
    const before = await snapshotTree(request.repo);
    const exitCode = await this.stream(args, onLine);
    return { exitCode, diff: await diffSince(request.repo, before) };
  }

  private stream(args: string[], onLine: (line: string) => void): Promise<number> {
    return new Promise((resolve) => {
      const child = spawn(this.python, args, { cwd: this.cwd, env: this.env });
      const emit = lineSplitter(onLine);
      child.stdout.on("data", (chunk: Buffer) => emit(chunk.toString()));
      child.stderr.on("data", (chunk: Buffer) => emit(chunk.toString()));
      child.on("error", (error) => {
        logger.error({ err: error }, "agent process failed to start");
        onLine(`gateway: could not start the agent process: ${error.message}`);
        resolve(1);
      });
      child.on("close", (code) => {
        emit(null);
        resolve(code ?? 1);
      });
    });
  }
}

function lineSplitter(onLine: (line: string) => void): (chunk: string | null) => void {
  /**
   * Buffers partial chunks so subscribers only ever see whole lines.
   *
   * @param onLine - Called once per complete line.
   * @returns emit - Accepts a chunk, or null to flush the remainder.
   */
  let pending = "";
  return (chunk: string | null) => {
    if (chunk === null) {
      if (pending !== "") {
        onLine(pending);
        pending = "";
      }
      return;
    }
    pending += chunk;
    const lines = pending.split("\n");
    pending = lines.pop() ?? "";
    for (const line of lines) {
      onLine(line);
    }
  };
}

export async function snapshotTree(repo: string): Promise<string | null> {
  /**
   * Records the current state of a checkout as a git tree object.
   *
   * Written through a throwaway index so the caller's staged changes are left
   * exactly as they were; only loose objects are added to the database.
   *
   * @param repo - Checkout to snapshot.
   * @returns tree - Tree object id, or null when the path is not a checkout.
   */
  const indexFile = join(tmpdir(), `shipwright-index-${randomUUID()}`);
  const env = { ...process.env, GIT_INDEX_FILE: indexFile };
  try {
    await execFileAsync("git", ["-C", repo, "add", "-A"], { env });
    const { stdout } = await execFileAsync("git", ["-C", repo, "write-tree"], { env });
    return stdout.trim();
  } catch (error) {
    logger.warn({ err: error, repo }, "could not snapshot the checkout");
    return null;
  } finally {
    await rm(indexFile, { force: true });
  }
}

export async function diffSince(repo: string, before: string | null): Promise<string> {
  /**
   * Diffs a checkout against a snapshot taken before the run started.
   *
   * Diffing the working tree instead would fold in every earlier run's edits,
   * so a second request appeared to have changed what the first one did.
   *
   * @param repo - Checkout the agent worked in.
   * @param before - Tree recorded before the run, or null when unavailable.
   * @returns diff - Unified diff of just this run's changes.
   */
  const after = await snapshotTree(repo);
  if (before === null || after === null || before === after) {
    return "";
  }
  try {
    const { stdout } = await execFileAsync("git", ["-C", repo, "diff", before, after], {
      maxBuffer: DIFF_MAX_BUFFER_BYTES,
    });
    return stdout;
  } catch (error) {
    logger.warn({ err: error, repo }, "could not diff against the pre-run snapshot");
    return "";
  }
}
