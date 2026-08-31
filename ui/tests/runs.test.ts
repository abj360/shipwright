/**
 * runs.test.ts --- unit tests for queueing a run from the browser
 */

import { startRun } from "../src/runs";
import { describe, expect, it, vi } from "vitest";

function respond(status: number, body: unknown): typeof fetch {
  /**
   * Builds a fetch stub that answers once with the given status and body.
   *
   * @param status - HTTP status to answer with.
   * @param body - JSON body to answer with.
   * @returns fetchImpl - Stub suitable for injection.
   */
  return vi.fn(async () =>
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  ) as unknown as typeof fetch;
}

describe("startRun", () => {
  it("returns the queued run record", async () => {
    const fetchImpl = respond(202, { id: "run-1", task: "fix add()", status: "queued" });
    await expect(startRun("", "fix add()", fetchImpl)).resolves.toMatchObject({ id: "run-1" });
  });

  it("posts the trimmed task to the gateway", async () => {
    const fetchImpl = respond(202, { id: "run-1", task: "t", status: "queued" });
    await startRun("", "  fix add()  ", fetchImpl);
    const [url, init] = vi.mocked(fetchImpl).mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/runs");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ task: "fix add()" });
  });

  it("sends no credential, because the proxy attaches it", async () => {
    const fetchImpl = respond(202, { id: "run-1", task: "t", status: "queued" });
    await startRun("", "fix add()", fetchImpl);
    const [, init] = vi.mocked(fetchImpl).mock.calls[0] as [string, RequestInit];
    expect(JSON.stringify(init.headers)).not.toContain("uthorization");
  });

  it("refuses an empty task without calling the gateway", async () => {
    const fetchImpl = respond(202, { id: "run-1", task: "t", status: "queued" });
    await expect(startRun("", "   ", fetchImpl)).rejects.toThrow(/describe what the agent/);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("surfaces a rejection from the gateway", async () => {
    const fetchImpl = respond(401, { error: "unauthorized" });
    await expect(startRun("", "fix add()", fetchImpl)).rejects.toThrow(/401/);
  });

  it("rejects a response with no run id", async () => {
    const fetchImpl = respond(202, { task: "fix add()" });
    await expect(startRun("", "fix add()", fetchImpl)).rejects.toThrow(/without an id/);
  });

  it("honours an explicit gateway base", async () => {
    const fetchImpl = respond(202, { id: "run-1", task: "t", status: "queued" });
    await startRun("http://gateway:4000", "fix add()", fetchImpl);
    const [url] = vi.mocked(fetchImpl).mock.calls[0] as [string];
    expect(url).toBe("http://gateway:4000/runs");
  });
});
