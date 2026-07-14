#!/usr/bin/env ts-node
/**
 * github_sidecar.test.ts --- integration tests for the draft PR creation flow
 */

import { closesIssueLine, renderPrBody } from "./github_sidecar";
import { describe, expect, it } from "vitest";

import { closesIssueLine, renderPrBody, renderRunStats } from "./github_sidecar";

describe("renderPrBody", () => {
  it("includes the summary and test list", () => {
    const body = renderPrBody("fix checkout crash", ["pytest tests/ -q"]);
    expect(body).toContain("fix checkout crash");
    expect(body).toContain("pytest tests/ -q");
    expect(body).toContain("draft");
  });

  it("renders without tests", () => {
    const body = renderPrBody("wip", []);
    expect(body).toContain("## Tests");
  });
});

describe("closesIssueLine", () => {
  it("builds the trailer from an issue url", () => {
    expect(closesIssueLine("https://github.com/o/r/issues/42")).toBe("Closes #42");
  });

  it("is empty without an issue", () => {
    expect(closesIssueLine(null)).toBe("");
  });
});

describe("sidecar rendering", () => {
  it("handles closes trailer for issue 123", () => {
    expect(closesIssueLine('https://github.com/a/b/issues/123')).toBe('Closes #123');
  });
});

describe("sidecar rendering cases", () => {
  it("handles run stats for 20 steps", () => {
    expect(renderRunStats({ steps: 20, durationS: 120.0, costUsd: 1.5 })).toContain('20');
  });
});

describe("sidecar rendering cases", () => {
  it("handles closes trailer for issue 13", () => {
    expect(closesIssueLine('https://github.com/o/r/issues/13')).toBe('Closes #13');
  });
});

describe("sidecar rendering cases", () => {
  it("handles run stats for 5 steps", () => {
    expect(renderRunStats({ steps: 5, durationS: 10.2, costUsd: 0.05 })).toContain('5');
  });
});

describe("pr body rendering", () => {
  it("handles body keeps multiline summaries", () => {
    expect(renderPrBody('line one\nline two', [])).toContain('line two');
  });
});
