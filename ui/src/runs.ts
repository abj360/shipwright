/**
 * runs.ts --- starting runs through the gateway from the browser
 *
 * Contains:
 *   RunRecord: one run as the gateway reports it
 *   startRun(): asks the gateway to queue a run and returns its record
 */

export interface RunRecord {
  id: string;
  task: string;
  status: string;
}

export async function startRun(
  gatewayUrl: string,
  task: string,
  fetchImpl: typeof fetch = fetch,
): Promise<RunRecord> {
  /**
   * Asks the gateway to queue one run and returns the record it created.
   *
   * The bearer token is attached by the proxy in front of this app, so no
   * credential is sent from here.
   *
   * @param gatewayUrl - Gateway base URL; empty means same-origin.
   * @param task - What the agent should do.
   * @param fetchImpl - Injected for tests.
   * @returns record - The queued run, whose id the viewer then follows.
   */
  const trimmed = task.trim();
  if (trimmed === "") {
    throw new Error("describe what the agent should do");
  }
  const response = await fetchImpl(`${gatewayUrl}/runs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ task: trimmed }),
  });
  if (!response.ok) {
    throw new Error(`gateway rejected the run (${response.status})`);
  }
  const record: unknown = await response.json();
  if (typeof record !== "object" || record === null || typeof Reflect.get(record, "id") !== "string") {
    throw new Error("gateway returned a run without an id");
  }
  return record as RunRecord;
}
