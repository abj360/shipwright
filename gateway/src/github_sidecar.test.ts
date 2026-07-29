#!/usr/bin/env ts-node
/**
 * github_sidecar.test.ts --- integration tests for the draft PR creation flow
 */

import { closesIssueLine, mapWithLimit, renderPrBody } from "./github_sidecar";
import { describe, expect, it, vi } from "vitest";

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

describe("sidecar rendering", () => {
  it("handles pr body for 'wip' includes 'draft'", () => {
    expect(renderPrBody('wip', [])).toContain('draft');
  });
});

describe("sidecar rendering cases", () => {
  it("handles pr body for 'fix bug'", () => {
    expect(renderPrBody('fix bug', ['pytest -q'])).toContain('fix bug');
  });
});

describe("sidecar rendering cases", () => {
  it("handles closes trailer for issue 8", () => {
    expect(closesIssueLine('https://github.com/o/r/issues/8')).toBe('Closes #8');
  });
});

describe("sidecar rendering", () => {
  it("handles pr body for 'fix login' includes 'fix login'", () => {
    expect(renderPrBody('fix login', ['pytest -q'])).toContain('fix login');
  });
});

describe("sidecar rendering cases", () => {
  it("handles run stats for 1 steps", () => {
    expect(renderRunStats({ steps: 1, durationS: 0.5, costUsd: 0.001 })).toContain('1');
  });
});

vi.mock("@octokit/rest", () => ({
  Octokit: vi.fn().mockImplementation(() => ({
    pulls: {
      list: vi.fn().mockResolvedValue({ data: [{ html_url: "https://x/pr/1" }] }),
    },
  })),
}));

describe("findOpenPr", () => {
  it("returns the url of an open PR", async () => {
    const { findOpenPr } = await import("./github_sidecar");
    const url = await findOpenPr(
      { repoUrl: "https://github.com/o/r", workDir: "/tmp", githubToken: "t", baseBranch: "main" },
      "shipwright/x",
    );
    expect(url).toBe("https://x/pr/1");
  });
});

describe("sidecar rendering cases", () => {
  it("handles run stats for 8 steps", () => {
    expect(renderRunStats({ steps: 8, durationS: 30.0, costUsd: 0.25 })).toContain('8');
  });
});

describe("sidecar rendering", () => {
  it("handles pr body for 'fix login' includes 'fix login'", () => {
    expect(renderPrBody('fix login', ['pytest -q'])).toContain('fix login');
  });
});

describe("sidecar rendering cases", () => {
  it("handles closes trailer for issue 512", () => {
    expect(closesIssueLine('https://github.com/o/r/issues/512')).toBe('Closes #512');
  });
});

describe("sidecar rendering", () => {
  it("handles pr body for 'bump deps' includes 'bump deps'", () => {
    expect(renderPrBody('bump deps', ['make check'])).toContain('bump deps');
  });
});

describe("sidecar rendering cases", () => {
  it("handles run stats for 5 steps", () => {
    expect(renderRunStats({ steps: 5, durationS: 10.2, costUsd: 0.05 })).toContain('5');
  });
});

describe("sidecar rendering cases", () => {
  it("handles closes trailer for issue 21", () => {
    expect(closesIssueLine('https://github.com/o/r/issues/21')).toBe('Closes #21');
  });
});

describe("sidecar rendering cases", () => {
  it("handles closes trailer for issue 100", () => {
    expect(closesIssueLine('https://github.com/o/r/issues/100')).toBe('Closes #100');
  });
});

describe("sidecar rendering", () => {
  it("handles pr body for 'refactor' includes '## Tests'", () => {
    expect(renderPrBody('refactor', ['pytest tests/ -q'])).toContain('## Tests');
  });
});

describe("sidecar rendering cases", () => {
  it("handles closes trailer for issue 42", () => {
    expect(closesIssueLine('https://github.com/o/r/issues/42')).toBe('Closes #42');
  });
});

describe("sidecar rendering cases", () => {
  it("handles pr body for 'add feature'", () => {
    expect(renderPrBody('add feature', ['pytest -q'])).toContain('add feature');
  });
});

describe("sidecar rendering cases", () => {
  it("handles closes trailer for issue 77", () => {
    expect(closesIssueLine('https://github.com/o/r/issues/77')).toBe('Closes #77');
  });
});

describe("sidecar rendering cases", () => {
  it("handles closes trailer for issue 1", () => {
    expect(closesIssueLine('https://github.com/o/r/issues/1')).toBe('Closes #1');
  });
});

describe("sidecar rendering cases", () => {
  it("handles closes trailer for issue 5", () => {
    expect(closesIssueLine('https://github.com/o/r/issues/5')).toBe('Closes #5');
  });
});

describe("sidecar rendering", () => {
  it("handles closes trailer for issue 1", () => {
    expect(closesIssueLine('https://github.com/o/r/issues/1')).toBe('Closes #1');
  });
});

describe("mapWithLimit", () => {
  it("preserves order while bounding concurrency", async () => {
    let inFlight = 0;
    let peak = 0;
    const results = await mapWithLimit([1, 2, 3, 4, 5], 2, async (n) => {
      inFlight += 1;
      peak = Math.max(peak, inFlight);
      await new Promise((resolve) => setTimeout(resolve, 5));
      inFlight -= 1;
      return n * 10;
    });
    expect(results).toEqual([10, 20, 30, 40, 50]);
    expect(peak).toBeLessThanOrEqual(2);
  });
});

describe("sidecar rendering cases", () => {
  it("handles pr body for 'improve logging'", () => {
    expect(renderPrBody('improve logging', ['pytest -q'])).toContain('improve logging');
  });
});

describe("sidecar rendering cases", () => {
  it("handles run stats for 3 steps", () => {
    expect(renderRunStats({ steps: 3, durationS: 2.0, costUsd: 0.01 })).toContain('3');
  });
});

describe("sidecar rendering cases", () => {
  it("handles closes trailer for issue 1", () => {
    expect(closesIssueLine('https://github.com/o/r/issues/1')).toBe('Closes #1');
  });
});

describe("sidecar rendering", () => {
  it("handles pr body for 'add cache' includes 'add cache'", () => {
    expect(renderPrBody('add cache', ['npm test'])).toContain('add cache');
  });
});

describe("sidecar rendering", () => {
  it("handles pr body for 'bump deps' includes 'bump deps'", () => {
    expect(renderPrBody('bump deps', ['make check'])).toContain('bump deps');
  });
});

describe("sidecar rendering cases", () => {
  it("handles pr body for 'add feature'", () => {
    expect(renderPrBody('add feature', ['pytest -q'])).toContain('add feature');
  });
});

describe("sidecar rendering", () => {
  it("handles closes trailer for issue 99", () => {
    expect(closesIssueLine('https://github.com/o/r/issues/99')).toBe('Closes #99');
  });
});

describe("sidecar rendering cases", () => {
  it("handles pr body for 'fix bug'", () => {
    expect(renderPrBody('fix bug', ['pytest -q'])).toContain('fix bug');
  });
});

describe("sidecar rendering", () => {
  it("handles closes trailer for issue 123", () => {
    expect(closesIssueLine('https://github.com/a/b/issues/123')).toBe('Closes #123');
  });
});

describe("sidecar rendering cases", () => {
  it("handles pr body for 'improve logging'", () => {
    expect(renderPrBody('improve logging', ['pytest -q'])).toContain('improve logging');
  });
});

describe("sidecar rendering", () => {
  it("handles pr body for 'refactor' includes '## Tests'", () => {
    expect(renderPrBody('refactor', ['pytest tests/ -q'])).toContain('## Tests');
  });
});

describe("sidecar rendering cases", () => {
  it("handles closes trailer for issue 2", () => {
    expect(closesIssueLine('https://github.com/o/r/issues/2')).toBe('Closes #2');
  });
});

describe("pr body rendering", () => {
  it("handles stats render step count", () => {
    expect(renderRunStats({ steps: 3, durationS: 1.5, costUsd: 0.01 })).toContain('3');
  });
});

describe("sidecar rendering cases", () => {
  it("handles pr body for 'tighten types'", () => {
    expect(renderPrBody('tighten types', ['pytest -q'])).toContain('tighten types');
  });
});
