/**
 * runs.test.ts --- unit tests for queueing a run from the browser
 */

import { defaultWorkspace, startRun } from "../src/runs";
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
    await expect(startRun("", "fix add()", "", fetchImpl)).resolves.toMatchObject({ id: "run-1" });
  });

  it("posts the trimmed task to the gateway", async () => {
    const fetchImpl = respond(202, { id: "run-1", task: "t", status: "queued" });
    await startRun("", "  fix add()  ", "", fetchImpl);
    const [url, init] = vi.mocked(fetchImpl).mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/runs");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ task: "fix add()" });
  });

  it("sends no credential, because the proxy attaches it", async () => {
    const fetchImpl = respond(202, { id: "run-1", task: "t", status: "queued" });
    await startRun("", "fix add()", "", fetchImpl);
    const [, init] = vi.mocked(fetchImpl).mock.calls[0] as [string, RequestInit];
    expect(JSON.stringify(init.headers)).not.toContain("uthorization");
  });

  it("refuses an empty task without calling the gateway", async () => {
    const fetchImpl = respond(202, { id: "run-1", task: "t", status: "queued" });
    await expect(startRun("", "   ", "", fetchImpl)).rejects.toThrow(/describe what the agent/);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("surfaces the gateway's own reason for a rejection", async () => {
    const fetchImpl = respond(401, { error: "unauthorized" });
    await expect(startRun("", "fix add()", "", fetchImpl)).rejects.toThrow(/unauthorized/);
  });

  it("falls back to the status when the gateway gives no reason", async () => {
    const fetchImpl = respond(502, {});
    await expect(startRun("", "fix add()", "", fetchImpl)).rejects.toThrow(/502/);
  });

  it("rejects a response with no run id", async () => {
    const fetchImpl = respond(202, { task: "fix add()" });
    await expect(startRun("", "fix add()", "", fetchImpl)).rejects.toThrow(/without an id/);
  });

  it("honours an explicit gateway base", async () => {
    const fetchImpl = respond(202, { id: "run-1", task: "t", status: "queued" });
    await startRun("http://gateway:4000", "fix add()", "", fetchImpl);
    const [url] = vi.mocked(fetchImpl).mock.calls[0] as [string];
    expect(url).toBe("http://gateway:4000/runs");
  });

  it("sends the folder when one is chosen", async () => {
    const fetchImpl = respond(202, { id: "run-1", task: "t", status: "queued", repo: "/srv/app" });
    await startRun("", "fix add()", "/srv/app", fetchImpl);
    const [, init] = vi.mocked(fetchImpl).mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({ task: "fix add()", repo: "/srv/app" });
  });

  it("omits the folder so the gateway picks its default", async () => {
    const fetchImpl = respond(202, { id: "run-1", task: "t", status: "queued", repo: "/d" });
    await startRun("", "fix add()", "", fetchImpl);
    const [, init] = vi.mocked(fetchImpl).mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({ task: "fix add()" });
  });

  it("surfaces the gateway's reason for refusing", async () => {
    const fetchImpl = respond(400, { error: "not a directory on the agent host: /nope" });
    await expect(startRun("", "fix add()", "/nope", fetchImpl)).rejects.toThrow(/not a directory/);
  });
});

describe("defaultWorkspace", () => {
  it("reads the folder the gateway reports", async () => {
    const fetchImpl = respond(200, { repo: "/tmp/sw-demo-repo" });
    await expect(defaultWorkspace("", fetchImpl)).resolves.toBe("/tmp/sw-demo-repo");
  });

  it("is empty when the gateway will not say", async () => {
    const fetchImpl = respond(500, {});
    await expect(defaultWorkspace("", fetchImpl)).resolves.toBe("");
  });

  it("is empty rather than throwing when the gateway is down", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error("offline");
    }) as unknown as typeof fetch;
    await expect(defaultWorkspace("", fetchImpl)).resolves.toBe("");
  });
});
