/**
 * Turn.tsx --- one request in the conversation, with its activity and diff
 *
 * Contains:
 *   TurnProps: the run this turn follows
 *   Turn: renders the request and what the agent did
 *   ToolRow: one tool activity line with its output and the diff it made
 *   useRunOutput(): collects a run's output lines as they stream in
 */

import { DiffViewer } from "./DiffViewer";
import { parseTranscript, type ToolEvent } from "./transcript";
import { useSandboxSocket } from "./useSandboxSocket";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export interface TurnProps {
  runId: string;
  task: string;
  gatewayUrl: string;
  onEnded: (runId: string) => void;
}

export function Turn({ runId, task, gatewayUrl, onEnded }: TurnProps) {
  /**
   * Renders one request and the steps the agent took, each write showing the
   * diff it made at the point it made it.
   */
  const { lines, append } = useRunOutput();
  const status = useSandboxSocket(gatewayUrl, runId, append);
  const ended = status === "ended";
  const events = useMemo(() => parseTranscript(lines), [lines]);

  useEffect(() => {
    if (ended) {
      onEnded(runId);
    }
  }, [ended, onEnded, runId]);

  return (
    <article className="turn">
      <p className="turn-request">{task}</p>
      <div className="turn-reply">
        {events.map((event, index) => {
          if (event.kind === "tool") {
            return <ToolRow key={index} event={event} />;
          }
          if (event.kind === "answer") {
            return (
              <p key={index} className="turn-answer">
                {event.text}
              </p>
            );
          }
          return (
            <p key={index} className="turn-note">
              {event.text}
            </p>
          );
        })}
        {!ended && <p className="turn-waiting">working…</p>}
      </div>
    </article>
  );
}

export function ToolRow({ event }: { event: ToolEvent }) {
  /**
   * Renders one tool call as an activity line that opens to show its output,
   * followed by the diff that call produced.
   */
  const [open, setOpen] = useState(false);
  const summary =
    event.detail.length === 1
      ? event.detail[0]
      : `${event.detail.length} lines`;

  return (
    <div className={`tool-row ${event.failed ? "tool-failed" : ""}`}>
      <button
        type="button"
        className="tool-head"
        onClick={() => setOpen(!open)}
      >
        <span className="tool-bullet" aria-hidden="true">
          {event.detail.length > 0 ? (open ? "▾" : "▸") : "·"}
        </span>
        <span className="tool-label">{event.label}</span>
        {event.target !== "" && (
          <span className="tool-target">{event.target}</span>
        )}
        {event.detail.length > 0 && !open && (
          <span className="tool-summary">{summary}</span>
        )}
      </button>
      {open && event.detail.length > 0 && (
        <pre className="tool-detail">{event.detail.join("\n")}</pre>
      )}
      {event.diff !== "" && <DiffViewer patch={event.diff} />}
    </div>
  );
}

export function useRunOutput(): {
  lines: string[];
  append: (chunk: string) => void;
} {
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
