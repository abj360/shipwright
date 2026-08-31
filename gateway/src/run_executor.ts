/**
 * run_executor.ts --- drives the agent CLI for one run and captures its output
 *
 * Contains:
 *   RunRequest: what one run needs to execute
 *   RunOutcome: exit status and working-tree diff of a finished run
 *   RunExecutor: executes one run, streaming output line by line
 *   SpawnRunExecutor: runs the agent CLI as a child process
 *   diffFor(): reads the working-tree diff of a checkout
 */

import { execFile, spawn } from "node:child_process";
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
    const exitCode = await this.stream(args, onLine);
    return { exitCode, diff: await diffFor(request.repo) };
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

export async function diffFor(repo: string): Promise<string> {
  /**
   * Reads the working-tree diff of a checkout, including untracked files.
   *
   * A repo that is not a git checkout is not an error here: the run still
   * happened, there is just nothing to show, so the diff comes back empty.
   *
   * @param repo - Checkout the agent worked in.
   * @returns diff - Unified diff text, empty when there is nothing to show.
   */
  try {
    await execFileAsync("git", ["-C", repo, "add", "--intent-to-add", "--all"]);
    const { stdout } = await execFileAsync("git", ["-C", repo, "diff"], {
      maxBuffer: DIFF_MAX_BUFFER_BYTES,
    });
    return stdout;
  } catch (error) {
    logger.warn({ err: error, repo }, "could not read the working-tree diff");
    return "";
  }
}
