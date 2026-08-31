/**
 * App.tsx --- top-level layout for the live run view
 *
 * Contains:
 *   GATEWAY_URL: same-origin base the gateway is proxied under
 *   App: top-level layout for the live run view
 *   useRunPatch(): fetches and refreshes the run diff
 */

import { DiffViewer } from "./DiffViewer";
import { TerminalViewer } from "./TerminalViewer";
import { useEffect, useState } from "react";

// Same-origin: the vite dev proxy and the nginx image both forward /runs to the
// gateway, so the browser never makes a cross-origin request.
const GATEWAY_URL = "";
const PATCH_POLL_MS = 3_000;

export function App() {
  /**
   * Renders the run selector and the live terminal for the selected run.
   */
  const [runId, setRunId] = useState("demo-run");
  const patch = useRunPatch(GATEWAY_URL, runId);

  return (
    <main className="app-shell">
      <header>
        <h1>shipwright</h1>
        <input value={runId} onChange={(event) => setRunId(event.target.value)} />
      </header>
      <TerminalViewer runId={runId} gatewayUrl={GATEWAY_URL} />
      <DiffViewer patch={patch} />
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
