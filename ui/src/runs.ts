/**
 * runs.ts --- starting runs through the gateway from the browser
 *
 * Contains:
 *   RunRecord: one run as the gateway reports it
 *   defaultWorkspace(): reads the folder runs default to
 *   startRun(): asks the gateway to queue a run and returns its record
 */

export interface RunRecord {
  id: string;
  task: string;
  status: string;
  repo: string;
}

export async function defaultWorkspace(
  gatewayUrl: string,
  fetchImpl: typeof fetch = fetch,
): Promise<string> {
  /**
   * Asks the gateway which folder runs work in unless told otherwise.
   *
   * @param gatewayUrl - Gateway base URL; empty means same-origin.
   * @param fetchImpl - Injected for tests.
   * @returns repo - The default folder, empty when the gateway will not say.
   */
  try {
    const response = await fetchImpl(`${gatewayUrl}/workspace`);
    if (!response.ok) {
      return "";
    }
    const body: unknown = await response.json();
    const repo = typeof body === "object" && body !== null ? Reflect.get(body, "repo") : "";
    return typeof repo === "string" ? repo : "";
  } catch {
    return "";
  }
}

export async function startRun(
  gatewayUrl: string,
  task: string,
  repo: string,
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
   * @param repo - Folder to work in; empty uses the gateway's default.
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
    body: JSON.stringify(repo === "" ? { task: trimmed } : { task: trimmed, repo }),
  });
  if (!response.ok) {
    const detail: unknown = await response.json().catch(() => null);
    const reason = typeof detail === "object" && detail !== null ? Reflect.get(detail, "error") : "";
    throw new Error(
      typeof reason === "string" && reason !== ""
        ? reason
        : `gateway rejected the run (${response.status})`,
    );
  }
  const record: unknown = await response.json();
  if (typeof record !== "object" || record === null || typeof Reflect.get(record, "id") !== "string") {
    throw new Error("gateway returned a run without an id");
  }
  return record as RunRecord;
}
