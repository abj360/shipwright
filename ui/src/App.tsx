#!/usr/bin/env ts-node
/**
 * App.tsx --- top-level layout for the live run view
 *
 * Contains:
 *   App: top-level layout for the live run view
 *   useRunPatch(): fetches and refreshes the run diff
 */

import { DiffViewer } from "./DiffViewer";
import { TerminalViewer } from "./TerminalViewer";
import { useEffect, useState } from "react";

export function App() {
  /**
   * Renders the run selector and the live terminal for the selected run.
   */
  const [runId, setRunId] = useState("demo-run");
  const patch = useRunPatch("http://localhost:4000", runId);

  return (
    <main className="app-shell">
      <header>
        <h1>shipwright</h1>
        <input value={runId} onChange={(event) => setRunId(event.target.value)} />
      </header>
      <TerminalViewer runId={runId} gatewayUrl="http://localhost:4000" />
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
      const response = await fetch(`${gatewayUrl}/runs/${runId}/diff`);
      if (response.ok && !cancelled) {
        setPatch(await response.text());
      }
    };
    const timer = setInterval(load, 3_000);
    void load();
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [gatewayUrl, runId]);

  return patch;
}
