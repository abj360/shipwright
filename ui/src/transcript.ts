/**
 * transcript.ts --- reads the agent's stdout into events the chat can render
 *
 * Contains:
 *   ToolEvent / AnswerEvent / NoteEvent: what a run reports
 *   TranscriptEvent: any one of them
 *   TOOL_LABELS: human wording for each tool name
 *   parseTranscript(): groups raw output lines into events
 */

export interface ToolEvent {
  kind: "tool";
  label: string;
  target: string;
  detail: string[];
  failed: boolean;
}

export interface AnswerEvent {
  kind: "answer";
  text: string;
}

export interface NoteEvent {
  kind: "note";
  text: string;
}

export type TranscriptEvent = ToolEvent | AnswerEvent | NoteEvent;

export const TOOL_LABELS: Record<string, string> = {
  read_file: "Read",
  write_file: "Wrote",
  edit_file: "Edited",
  list_dir: "Listed",
  run_shell: "Ran",
  run_tests: "Tested",
  git_diff: "Diffed",
  apply_patch: "Patched",
};

const STEP_LINE = /^\[step \d+\] (\S+)(?: (.*))?$/;
const PROGRESS_LINE = /^\[progress\] /;
const ANSWER_LINE = /^final: ?/;
const NOTE_LINE = /^took /;
const PATH_ARG = /(?:^|; )(?:path|command|selector)=([^;]*)/;

export function parseTranscript(lines: string[]): TranscriptEvent[] {
  /**
   * Groups the agent's output lines into the events the chat renders.
   *
   * The stream is a flat log: a step line, then that step's observation, then
   * the next step. This reassembles each step with the output it produced so
   * the chat can show an activity row instead of raw log lines.
   *
   * @param lines - Output lines exactly as the agent printed them.
   * @returns events - Tool activity, the final answer, and the run note.
   */
  const events: TranscriptEvent[] = [];
  let current: ToolEvent | null = null;

  for (const line of lines) {
    if (PROGRESS_LINE.test(line)) {
      continue;
    }
    const step = STEP_LINE.exec(line);
    if (step !== null) {
      const tool = step[1] ?? "";
      if (tool === "final") {
        current = null;
        continue;
      }
      current = {
        kind: "tool",
        label: TOOL_LABELS[tool] ?? tool,
        target: targetOf(step[2] ?? ""),
        detail: [],
        failed: false,
      };
      events.push(current);
      continue;
    }
    if (ANSWER_LINE.test(line)) {
      current = null;
      events.push({ kind: "answer", text: line.replace(ANSWER_LINE, "") });
      continue;
    }
    if (NOTE_LINE.test(line)) {
      current = null;
      events.push({ kind: "note", text: line });
      continue;
    }
    if (current !== null) {
      current.detail.push(line);
      if (line.startsWith("error:")) {
        current.failed = true;
      }
    }
  }
  return events;
}

function targetOf(args: string): string {
  /**
   * Picks the argument worth showing beside the tool name.
   *
   * @param args - Rendered argument string from the step line.
   * @returns target - The path or command the step acted on, else empty.
   */
  const match = PATH_ARG.exec(args);
  return match?.[1]?.trim() ?? "";
}
