/**
 * Turn.tsx --- one request in the conversation, with its output and diff
 *
 * Contains:
 *   TurnProps: the run this turn follows
 *   Turn: renders the request, the agent's output, and the resulting diff
 *   useRunOutput(): collects a run's output lines as they stream in
 */

import { DiffViewer } from "./DiffViewer";
import { useRunPatch } from "./useRunPatch";
import { useSandboxSocket } from "./useSandboxSocket";
import { useCallback, useEffect, useRef, useState } from "react";

export interface TurnProps {
  runId: string;
  task: string;
  gatewayUrl: string;
  onEnded: (runId: string) => void;
}

export function Turn({ runId, task, gatewayUrl, onEnded }: TurnProps) {
  /**
   * Renders one request, whatever the agent has printed, and its diff.
   */
  const { lines, append } = useRunOutput();
  const status = useSandboxSocket(gatewayUrl, runId, append);
  const ended = status === "ended";
  const patch = useRunPatch(gatewayUrl, runId, !ended);

  useEffect(() => {
    if (ended) {
      onEnded(runId);
    }
  }, [ended, onEnded, runId]);

  return (
    <article className="turn">
      <p className="turn-request">{task}</p>
      {lines.length > 0 && <pre className="turn-output">{lines.join("\n")}</pre>}
      {!ended && lines.length === 0 && <p className="turn-waiting">working…</p>}
      {patch !== "" && <DiffViewer patch={patch} />}
    </article>
  );
}

export function useRunOutput(): { lines: string[]; append: (chunk: string) => void } {
  /**
   * Collects a run's output, splitting the stream back into whole lines.
   *
   * Chunks arrive on socket boundaries rather than line boundaries, so a
   * partial line is held back until the rest of it turns up.
   *
   * @returns output - The lines received so far and a chunk sink.
   */
  const [lines, setLines] = useState<string[]>([]);
  const partial = useRef("");

  const append = useCallback((chunk: string) => {
    const combined = partial.current + chunk;
    const parts = combined.split("\n");
    partial.current = parts.pop() ?? "";
    if (parts.length > 0) {
      setLines((current) => [...current, ...parts]);
    }
  }, []);

  return { lines, append };
}
