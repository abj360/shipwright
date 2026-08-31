/**
 * useRunPatch.ts --- polls one run's diff while it is still producing one
 *
 * Contains:
 *   PATCH_POLL_MS: how often an active run is re-read
 *   useRunPatch(): fetches and refreshes the run diff
 */

import { useEffect, useState } from "react";

const PATCH_POLL_MS = 2_000;

export function useRunPatch(gatewayUrl: string, runId: string, live: boolean): string {
  /**
   * Fetches the current diff for a run, refreshing only while it is active.
   *
   * @param gatewayUrl - Gateway base URL; empty means same-origin.
   * @param runId - Run to fetch the diff for.
   * @param live - Whether the run may still change the diff.
   * @returns patch - Unified diff text, empty while unavailable.
   */
  const [patch, setPatch] = useState("");

  useEffect(() => {
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
    void load();
    if (!live) {
      return;
    }
    const timer = setInterval(load, PATCH_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [gatewayUrl, runId, live]);

  return patch;
}
