/**
 * run_executor.test.ts --- tests that the agent process is driven and captured
 */

import { execFile } from "node:child_process";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";

import { SpawnRunExecutor, diffFor } from "../src/run_executor";
import { beforeAll, describe, expect, it } from "vitest";

const execFileAsync = promisify(execFile);

async function gitRepo(): Promise<string> {
  /**
   * Builds a throwaway git checkout with one committed file.
   *
   * @returns dir - Path of the new checkout.
   */
  const dir = await mkdtemp(join(tmpdir(), "shipwright-exec-"));
  await execFileAsync("git", ["-C", dir, "init", "-q"]);
  await execFileAsync("git", ["-C", dir, "config", "user.email", "t@example.com"]);
  await execFileAsync("git", ["-C", dir, "config", "user.name", "t"]);
  await writeFile(join(dir, "calc.py"), "def add(a, b):\n    return a - b\n");
  await execFileAsync("git", ["-C", dir, "add", "-A"]);
  await execFileAsync("git", ["-C", dir, "commit", "-qm", "init"]);
  return dir;
}

describe("diffFor", () => {
  it("reports an edit to a tracked file", async () => {
    const dir = await gitRepo();
    await writeFile(join(dir, "calc.py"), "def add(a, b):\n    return a + b\n");
    const diff = await diffFor(dir);
    expect(diff).toContain("calc.py");
    expect(diff).toContain("+    return a + b");
  });

  it("reports a file the agent created", async () => {
    const dir = await gitRepo();
    await writeFile(join(dir, "new_module.py"), "VALUE = 1\n");
    expect(await diffFor(dir)).toContain("new_module.py");
  });

  it("is empty for an untouched checkout", async () => {
    expect(await diffFor(await gitRepo())).toBe("");
  });

  it("is empty rather than throwing outside a checkout", async () => {
    const dir = await mkdtemp(join(tmpdir(), "shipwright-nogit-"));
    expect(await diffFor(dir)).toBe("");
  });
});

describe("SpawnRunExecutor", () => {
  let repo: string;

  beforeAll(async () => {
    repo = await gitRepo();
  });

  it("streams the agent's output line by line", async () => {
    const lines: string[] = [];
    const executor = new SpawnRunExecutor({
      // Stand in for the interpreter so the test never needs a model credential.
      python: process.execPath,
      cwd: process.cwd(),
      env: { ...process.env, NODE_OPTIONS: "" },
    });
    const outcome = await executor.execute({ runId: "r1", task: "t", repo }, (line) =>
      lines.push(line),
    );
    // node rejects "-m agent.cli"; what matters is that stderr was captured.
    expect(outcome.exitCode).not.toBe(0);
    expect(lines.length).toBeGreaterThan(0);
  });

  it("reports a failure instead of throwing when the process cannot start", async () => {
    const lines: string[] = [];
    const executor = new SpawnRunExecutor({
      python: "/nonexistent/interpreter",
      cwd: process.cwd(),
    });
    const outcome = await executor.execute({ runId: "r1", task: "t", repo }, (line) =>
      lines.push(line),
    );
    expect(outcome.exitCode).toBe(1);
    expect(lines.join("\n")).toContain("could not start the agent process");
  });

  it("returns the diff the run left behind", async () => {
    await writeFile(join(repo, "calc.py"), "def add(a, b):\n    return a + b\n");
    const executor = new SpawnRunExecutor({ python: "/nonexistent/interpreter", cwd: process.cwd() });
    const outcome = await executor.execute({ runId: "r1", task: "t", repo }, () => {});
    expect(outcome.diff).toContain("+    return a + b");
  });
});
