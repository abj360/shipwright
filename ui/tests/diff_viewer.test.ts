/**
 * diff_viewer.test.ts --- unit tests for unified-diff parsing and stats
 */

import { diffStats, parseDiff } from "../src/DiffViewer";
import { describe, expect, it } from "vitest";

const PATCH = [
  "diff --git a/agent/cost_tracker.py b/agent/cost_tracker.py",
  "index 1111111..2222222 100644",
  "--- a/agent/cost_tracker.py",
  "+++ b/agent/cost_tracker.py",
  "@@ -25,7 +25,8 @@ PRICE_PER_MTOK = {",
  '     "claude-opus-4-1": (15.0, 75.0),',
  '-    "claude-sonnet-4-5": (3.5, 16.0),',
  '+    "claude-sonnet-4-5": (3.0, 15.0),',
  '+    "gpt-4o-mini": (0.15, 0.6),',
  '     "scripted": (0.0, 0.0),',
].join("\n");

describe("parseDiff", () => {
  it("groups lines under the file they belong to", () => {
    const files = parseDiff(PATCH);
    expect(files).toHaveLength(1);
    expect(files[0]?.path).toBe("agent/cost_tracker.py");
  });

  it("does not count the ---/+++ headers as changed lines", () => {
    const kinds = parseDiff(PATCH).flatMap((f) => f.lines.map((l) => l.kind));
    expect(kinds.filter((k) => k === "add")).toHaveLength(2);
    expect(kinds.filter((k) => k === "del")).toHaveLength(1);
  });

  it("keeps file metadata out of the rendered lines entirely", () => {
    const texts = parseDiff(PATCH).flatMap((f) => f.lines.map((l) => l.text));
    expect(texts.some((t) => t.startsWith("--- ") || t.startsWith("+++ "))).toBe(false);
    expect(texts.some((t) => t.startsWith("index "))).toBe(false);
  });

  it("numbers lines from the hunk header", () => {
    const lines = parseDiff(PATCH)[0]?.lines ?? [];
    const context = lines.find((l) => l.kind === "context");
    expect(context?.oldNo).toBe(25);
    expect(context?.newNo).toBe(25);
  });

  it("advances only the new-side counter across an addition", () => {
    const lines = parseDiff(PATCH)[0]?.lines ?? [];
    const adds = lines.filter((l) => l.kind === "add");
    expect(adds.map((l) => l.newNo)).toEqual([26, 27]);
    expect(adds.every((l) => l.oldNo === null)).toBe(true);
  });

  it("returns nothing for an empty patch", () => {
    expect(parseDiff("")).toEqual([]);
  });

  it("ignores content before the first file header", () => {
    expect(parseDiff("stray line\n+not a real add")).toEqual([]);
  });

  it("splits a multi-file patch per file", () => {
    const twoFiles = [
      "diff --git a/one.py b/one.py",
      "--- a/one.py",
      "+++ b/one.py",
      "@@ -1,1 +1,1 @@",
      "+first",
      "diff --git a/two.py b/two.py",
      "--- a/two.py",
      "+++ b/two.py",
      "@@ -1,1 +1,1 @@",
      "+second",
    ].join("\n");
    expect(parseDiff(twoFiles).map((f) => f.path)).toEqual(["one.py", "two.py"]);
  });
});

describe("diffStats", () => {
  it("counts additions and deletions without the headers", () => {
    expect(diffStats(parseDiff(PATCH))).toEqual({ added: 2, removed: 1 });
  });

  it("reports zeroes for an empty patch", () => {
    expect(diffStats(parseDiff(""))).toEqual({ added: 0, removed: 0 });
  });
});
