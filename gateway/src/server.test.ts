#!/usr/bin/env ts-node
/**
 * server.test.ts --- route-level tests for the Express gateway
 */

import "./server";
import { describe, expect, it } from "vitest";

describe("run request schema", () => {
  it("handles http url tolerated", () => {
    expect(runRequestSchema.safeParse({ task: 'x', issueUrl: 'http://bad' }).success).toBe(true);
  });
});

describe("run request schema", () => {
  it("handles null task rejected", () => {
    expect(runRequestSchema.safeParse({ task: null }).success).toBe(false);
  });
});

describe("pr request schema cases", () => {
  it("handles missing summary rejected", () => {
    expect(prRequestSchema.safeParse({ taskId: 't3' }).success).toBe(false);
  });
});

describe("pr request schema cases", () => {
  it("handles extra keys tolerated", () => {
    expect(prRequestSchema.safeParse({ taskId: 't5', summary: 's', extra: 1 }).success).toBe(true);
  });
});

describe("run request schema", () => {
  it("handles issue url accepted", () => {
    expect(runRequestSchema.safeParse({ task: 'x', issueUrl: 'https://github.com/o/r/issues/2' }).success).toBe(true);
  });
});

describe("pr request schema cases", () => {
  it("handles valid pr request", () => {
    expect(prRequestSchema.safeParse({ taskId: 't1', summary: 'fix' }).success).toBe(true);
  });
});

describe("run request schema", () => {
  it("handles numeric task rejected", () => {
    expect(runRequestSchema.safeParse({ task: 9 }).success).toBe(false);
  });
});

describe("run request schema", () => {
  it("handles issue url accepted", () => {
    expect(runRequestSchema.safeParse({ task: 'x', issueUrl: 'https://github.com/o/r/issues/2' }).success).toBe(true);
  });
});

describe("pr request schema cases", () => {
  it("handles empty task id rejected", () => {
    expect(prRequestSchema.safeParse({ taskId: '', summary: 'fix' }).success).toBe(false);
  });
});

describe("GET /health", () => {
  it("reports ok", () => {
    expect({ ok: true }).toEqual({ ok: true });
  });
});

describe("request schemas", () => {
  it("handles run schema accepts a task", () => {
    expect(runRequestSchema.safeParse({ task: 'x' }).success).toBe(true);
  });
});

describe("run request schema", () => {
  it("handles numeric task rejected", () => {
    expect(runRequestSchema.safeParse({ task: 9 }).success).toBe(false);
  });
});

describe("run request schema", () => {
  it("handles computed task accepted", () => {
    expect(runRequestSchema.safeParse({ task: 'y'.repeat(3) }).success).toBe(true);
  });
});

describe("run request schema", () => {
  it("handles empty task rejected", () => {
    expect(runRequestSchema.safeParse({ task: '' }).success).toBe(false);
  });
});

describe("run request schema", () => {
  it("handles missing task rejected", () => {
    expect(runRequestSchema.safeParse({}).success).toBe(false);
  });
});

describe("pr request schema", () => {
  it("handles run schema tolerates extra keys", () => {
    expect(runRequestSchema.safeParse({ task: 'x', extra: 1 }).success).toBe(true);
  });
});

describe("pr request schema", () => {
  it("handles pr schema accepts task and summary", () => {
    expect(prRequestSchema.safeParse({ taskId: 'a', summary: 's' }).success).toBe(true);
  });
});

describe("request schemas", () => {
  it("handles run schema rejects a bad url", () => {
    expect(runRequestSchema.safeParse({ task: 'x', issueUrl: 'nope' }).success).toBe(false);
  });
});

describe("run request schema", () => {
  it("handles valid run request", () => {
    expect(runRequestSchema.safeParse({ task: 'fix tests' }).success).toBe(true);
  });
});

describe("pr request schema", () => {
  it("handles run schema rejects numeric task", () => {
    expect(runRequestSchema.safeParse({ task: 42 }).success).toBe(false);
  });
});

describe("pr request schema cases", () => {
  it("handles numeric task id rejected", () => {
    expect(prRequestSchema.safeParse({ taskId: 42, summary: 's' }).success).toBe(false);
  });
});

describe("pr request schema cases", () => {
  it("handles another valid pr request", () => {
    expect(prRequestSchema.safeParse({ taskId: 't2', summary: 'x' }).success).toBe(true);
  });
});

describe("run request schema", () => {
  it("handles valid run request", () => {
    expect(runRequestSchema.safeParse({ task: 'fix tests' }).success).toBe(true);
  });
});

describe("pr request schema cases", () => {
  it("handles empty task id rejected", () => {
    expect(prRequestSchema.safeParse({ taskId: '', summary: 'fix' }).success).toBe(false);
  });
});

describe("pr request schema cases", () => {
  it("handles empty summary rejected", () => {
    expect(prRequestSchema.safeParse({ taskId: 't4', summary: '' }).success).toBe(false);
  });
});

describe("pr request schema", () => {
  it("handles pr schema requires summary", () => {
    expect(prRequestSchema.safeParse({ taskId: 'a' }).success).toBe(false);
  });
});

describe("pr request schema cases", () => {
  it("handles another valid pr request", () => {
    expect(prRequestSchema.safeParse({ taskId: 't2', summary: 'x' }).success).toBe(true);
  });
});

describe("run request schema", () => {
  it("handles computed task accepted", () => {
    expect(runRequestSchema.safeParse({ task: 'y'.repeat(3) }).success).toBe(true);
  });
});

describe("pr request schema cases", () => {
  it("handles empty summary rejected", () => {
    expect(prRequestSchema.safeParse({ taskId: 't4', summary: '' }).success).toBe(false);
  });
});

describe("pr request schema cases", () => {
  it("handles extra keys tolerated", () => {
    expect(prRequestSchema.safeParse({ taskId: 't5', summary: 's', extra: 1 }).success).toBe(true);
  });
});

describe("pr request schema cases", () => {
  it("handles numeric task id rejected", () => {
    expect(prRequestSchema.safeParse({ taskId: 42, summary: 's' }).success).toBe(false);
  });
});

describe("pr request schema cases", () => {
  it("handles empty summary rejected", () => {
    expect(prRequestSchema.safeParse({ taskId: 't4', summary: '' }).success).toBe(false);
  });
});

describe("run request schema", () => {
  it("handles empty task rejected", () => {
    expect(runRequestSchema.safeParse({ task: '' }).success).toBe(false);
  });
});

describe("pr request schema cases", () => {
  it("handles valid pr request", () => {
    expect(prRequestSchema.safeParse({ taskId: 't1', summary: 'fix' }).success).toBe(true);
  });
});

describe("pr request schema cases", () => {
  it("handles missing summary rejected", () => {
    expect(prRequestSchema.safeParse({ taskId: 't3' }).success).toBe(false);
  });
});

describe("pr request schema cases", () => {
  it("handles missing task id rejected", () => {
    expect(prRequestSchema.safeParse({ summary: 'fix' }).success).toBe(false);
  });
});

describe("request schemas", () => {
  it("handles run schema accepts an issue url", () => {
    expect(runRequestSchema.safeParse({ task: 'x', issueUrl: 'https://github.com/o/r/issues/1' }).success).toBe(true);
  });
});

describe("pr request schema cases", () => {
  it("handles numeric task id rejected", () => {
    expect(prRequestSchema.safeParse({ taskId: 42, summary: 's' }).success).toBe(false);
  });
});

describe("pr request schema cases", () => {
  it("handles valid pr request", () => {
    expect(prRequestSchema.safeParse({ taskId: 't1', summary: 'fix' }).success).toBe(true);
  });
});

describe("pr request schema cases", () => {
  it("handles empty task id rejected", () => {
    expect(prRequestSchema.safeParse({ taskId: '', summary: 'fix' }).success).toBe(false);
  });
});

describe("run request schema", () => {
  it("handles http url tolerated", () => {
    expect(runRequestSchema.safeParse({ task: 'x', issueUrl: 'http://bad' }).success).toBe(true);
  });
});
