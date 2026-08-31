/**
 * run_executor.test.ts --- tests that the agent process is driven and captured
 */

import { execFile } from "node:child_process";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";

import { SpawnRunExecutor, diffSince, snapshotTree } from "../src/run_executor";
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

describe("diffSince", () => {
  it("reports an edit made after the snapshot", async () => {
    const dir = await gitRepo();
    const before = await snapshotTree(dir);
    await writeFile(join(dir, "calc.py"), "def add(a, b):\n    return a + b\n");
    const diff = await diffSince(dir, before);
    expect(diff).toContain("calc.py");
    expect(diff).toContain("+    return a + b");
  });

  it("reports a file created after the snapshot", async () => {
    const dir = await gitRepo();
    const before = await snapshotTree(dir);
    await writeFile(join(dir, "new_module.py"), "VALUE = 1\n");
    expect(await diffSince(dir, before)).toContain("new_module.py");
  });

  it("excludes changes that predate the snapshot", async () => {
    const dir = await gitRepo();
    await writeFile(join(dir, "earlier.py"), "EARLIER = 1\n");
    const before = await snapshotTree(dir);
    await writeFile(join(dir, "later.py"), "LATER = 1\n");
    const diff = await diffSince(dir, before);
    expect(diff).toContain("later.py");
    expect(diff).not.toContain("earlier.py");
  });

  it("is empty when the run changed nothing", async () => {
    const dir = await gitRepo();
    expect(await diffSince(dir, await snapshotTree(dir))).toBe("");
  });

  it("leaves the caller's staged changes alone", async () => {
    const dir = await gitRepo();
    await writeFile(join(dir, "staged.py"), "STAGED = 1\n");
    await execFileAsync("git", ["-C", dir, "add", "staged.py"]);
    await snapshotTree(dir);
    const { stdout } = await execFileAsync("git", ["-C", dir, "diff", "--cached", "--name-only"]);
    expect(stdout.trim()).toBe("staged.py");
  });

  it("is empty rather than throwing outside a checkout", async () => {
    const dir = await mkdtemp(join(tmpdir(), "shipwright-nogit-"));
    expect(await snapshotTree(dir)).toBeNull();
    expect(await diffSince(dir, null)).toBe("");
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
    const executor = new SpawnRunExecutor({
      python: "/nonexistent/interpreter",
      cwd: process.cwd(),
    });
    const outcome = await executor.execute({ runId: "r1", task: "t", repo }, () => {});
    // The interpreter never runs, so the run changes nothing of its own.
    expect(outcome.diff).toBe("");
  });
});
