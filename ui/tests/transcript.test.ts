/**
 * transcript.test.ts --- unit tests for reading agent output into chat events
 */

import { parseTranscript, type ToolEvent } from "../src/transcript";
import { describe, expect, it } from "vitest";

const OUTPUT = [
  "[progress] step 0",
  "[step 0] read_file path=calc.py",
  "def add(a, b):",
  "    return a - b",
  "[progress] step 1",
  "[step 1] write_file path=calc.py; content=def add(a, b):…",
  "wrote 32 bytes to calc.py",
  "final: corrected add() to return a + b",
  "took 5.3s, cost $0.0042",
];

function tools(lines: string[]): ToolEvent[] {
  /**
   * Narrows a parsed transcript to just its tool events.
   *
   * @param lines - Raw output lines.
   * @returns events - The tool activity in order.
   */
  return parseTranscript(lines).filter((e): e is ToolEvent => e.kind === "tool");
}

describe("parseTranscript", () => {
  it("labels each tool in plain words", () => {
    expect(tools(OUTPUT).map((e) => e.label)).toEqual(["Read", "Wrote"]);
  });

  it("shows the path each step acted on", () => {
    expect(tools(OUTPUT).map((e) => e.target)).toEqual(["calc.py", "calc.py"]);
  });

  it("attaches each step's output to that step", () => {
    expect(tools(OUTPUT)[0]?.detail).toEqual(["def add(a, b):", "    return a - b"]);
    expect(tools(OUTPUT)[1]?.detail).toEqual(["wrote 32 bytes to calc.py"]);
  });

  it("drops the progress noise", () => {
    const text = JSON.stringify(parseTranscript(OUTPUT));
    expect(text).not.toContain("progress");
  });

  it("reads the final answer as prose", () => {
    const answers = parseTranscript(OUTPUT).filter((e) => e.kind === "answer");
    expect(answers).toEqual([{ kind: "answer", text: "corrected add() to return a + b" }]);
  });

  it("keeps the timing line as a note", () => {
    const notes = parseTranscript(OUTPUT).filter((e) => e.kind === "note");
    expect(notes).toEqual([{ kind: "note", text: "took 5.3s, cost $0.0042" }]);
  });

  it("marks a step that failed", () => {
    const failed = tools([
      "[step 0] apply_patch patch=nonsense",
      "error: patch rejected: corrupt patch at line 9",
    ]);
    expect(failed[0]?.failed).toBe(true);
  });

  it("does not mark a step that succeeded", () => {
    expect(tools(OUTPUT).every((e) => e.failed)).toBe(false);
  });

  it("shows the command for a shell step", () => {
    expect(tools(["[step 0] run_shell command=git diff --stat"])[0]?.target).toBe(
      "git diff --stat",
    );
  });

  it("falls back to the raw name for an unknown tool", () => {
    expect(tools(["[step 0] something_new path=x"])[0]?.label).toBe("something_new");
  });

  it("returns nothing for empty output", () => {
    expect(parseTranscript([])).toEqual([]);
  });

  it("ignores output that arrives before any step line", () => {
    expect(parseTranscript(["stray line"])).toEqual([]);
  });

  it("labels every tool the dispatcher offers", () => {
    const named = ["read_file", "write_file", "edit_file", "list_dir", "run_shell"];
    const labelled = tools(named.map((tool, i) => `[step ${i}] ${tool} path=x`));
    expect(labelled.map((e) => e.label)).toEqual(["Read", "Wrote", "Edited", "Listed", "Ran"]);
  });
});
