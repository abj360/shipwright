/**
 * App.tsx --- top-level layout for the live run view
 *
 * Contains:
 *   GATEWAY_URL: same-origin base the gateway is proxied under
 *   App: task box, live terminal, and diff for the current run
 *   useRunPatch(): fetches and refreshes the run diff
 */

import { DiffViewer } from "./DiffViewer";
import { startRun } from "./runs";
import { TerminalViewer } from "./TerminalViewer";
import { useEffect, useState } from "react";

// Same-origin: the vite dev proxy and the nginx image both forward /runs to the
// gateway, so the browser never makes a cross-origin request.
const GATEWAY_URL = "";
const PATCH_POLL_MS = 3_000;

export function App() {
  /**
   * Renders the task box and, once a run is queued, its output and diff.
   */
  const [runId, setRunId] = useState("");
  const [task, setTask] = useState("");
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const patch = useRunPatch(GATEWAY_URL, runId);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (starting) {
      return;
    }
    setStarting(true);
    setError("");
    try {
      const record = await startRun(GATEWAY_URL, task);
      setRunId(record.id);
      setTask("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "could not start the run");
    } finally {
      setStarting(false);
    }
  };

  return (
    <main className="app-shell">
      <header>
        <h1>shipwright</h1>
        <form className="task-form" onSubmit={submit}>
          <input
            value={task}
            onChange={(event) => setTask(event.target.value)}
            placeholder="what should the agent do?"
            aria-label="task"
            autoFocus
          />
          <button type="submit" disabled={starting}>
            {starting ? "starting…" : "run"}
          </button>
        </form>
        {runId !== "" && <code className="run-id">{runId}</code>}
      </header>
      {error !== "" && <p className="run-error">{error}</p>}
      {runId === "" ? (
        <p className="run-hint">Describe a task and press enter to start a run.</p>
      ) : (
        <>
          <TerminalViewer runId={runId} gatewayUrl={GATEWAY_URL} />
          <DiffViewer patch={patch} />
        </>
      )}
    </main>
  );
}

export function useRunPatch(gatewayUrl: string, runId: string): string {
  /**
   * Fetches the current diff for a run, refreshing while it is active.
   *
   * @param gatewayUrl - Gateway base URL.
   * @param runId - Run to fetch the diff for.
   * @returns patch - Unified diff text, empty while unavailable.
   */
  const [patch, setPatch] = useState("");

  useEffect(() => {
    setPatch("");
    if (runId === "") {
      return;
    }
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch(`${gatewayUrl}/runs/${runId}/diff`);
        if (response.ok && !cancelled) {
          setPatch(await response.text());
        }
      } catch {
        // A gateway that is down or still starting is expected; the next poll retries.
      }
    };
    const timer = setInterval(load, PATCH_POLL_MS);
    void load();
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [gatewayUrl, runId]);

  return patch;
}
