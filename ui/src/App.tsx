/**
 * App.tsx --- the conversation view: requests, agent output, and diffs
 *
 * Contains:
 *   GATEWAY_URL: same-origin base the gateway is proxied under
 *   App: title, conversation, and the composer that queues runs
 *   SendIcon: arrow while idle, square while a run is in flight
 */

import { startRun } from "./runs";
import { Turn } from "./Turn";
import { useCallback, useEffect, useRef, useState } from "react";

// Same-origin: the vite dev proxy and the nginx image both forward /runs to the
// gateway, so the browser never makes a cross-origin request.
const GATEWAY_URL = "";

interface ConversationTurn {
  runId: string;
  task: string;
}

export function App() {
  /**
   * Renders the conversation and the composer that adds to it.
   */
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [task, setTask] = useState("");
  const [runningId, setRunningId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const foot = useRef<HTMLDivElement>(null);

  useEffect(() => {
    foot.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, runningId]);

  const handleEnded = useCallback((runId: string) => {
    setRunningId((current) => (current === runId ? null : current));
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (runningId !== null) {
      return;
    }
    setError("");
    try {
      const record = await startRun(GATEWAY_URL, task);
      setTurns((current) => [...current, { runId: record.id, task: record.task }]);
      setRunningId(record.id);
      setTask("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "could not start the run");
    }
  };

  return (
    <main className="app-shell">
      <header>
        <h1>shipwright</h1>
      </header>

      <section className="conversation" aria-label="conversation">
        {turns.map((turn) => (
          <Turn
            key={turn.runId}
            runId={turn.runId}
            task={turn.task}
            gatewayUrl={GATEWAY_URL}
            onEnded={handleEnded}
          />
        ))}
        <div ref={foot} />
      </section>

      {error !== "" && <p className="run-error">{error}</p>}

      <form className="composer" onSubmit={submit}>
        <input
          value={task}
          onChange={(event) => setTask(event.target.value)}
          aria-label="task"
          autoFocus
        />
        <button
          type="submit"
          disabled={runningId !== null}
          aria-label={runningId !== null ? "run in progress" : "send"}
          title={runningId !== null ? "run in progress" : "send"}
        >
          <SendIcon running={runningId !== null} />
        </button>
      </form>
    </main>
  );
}

export function SendIcon({ running }: { running: boolean }) {
  /**
   * Draws the composer's icon: an arrow to send, a square while a run is live.
   */
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
      {running ? (
        <rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" />
      ) : (
        <path
          d="M12 19V5M12 5l-6 6M12 5l6 6"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}
    </svg>
  );
}
