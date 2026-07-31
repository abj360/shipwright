#!/usr/bin/env ts-node
/**
 * DiffViewer.tsx --- renders the run's unified diff alongside the terminal output
 *
 * Contains:
 *   DiffLine: one classified diff line
 *   DiffFile: one file's classified lines
 *   parseDiff(): parses a unified diff into per-file lines
 *   DiffViewer: renders a unified diff with per-line styling
 *   FileSection: collapsible per-file diff section
 */

import { useMemo, useState } from "react";

export interface DiffLine {
  kind: "add" | "del" | "context" | "hunk";
  text: string;
  oldNo: number | null;
  newNo: number | null;
}

export interface DiffFile {
  path: string;
  lines: DiffLine[];
}

export function parseDiff(patch: string): DiffFile[] {
  /**
   * Parses a unified diff into per-file line lists.
   *
   * @param patch - Unified diff text.
   * @returns files - Parsed files with classified lines.
   */
  const files: DiffFile[] = [];
  let current: DiffFile | null = null;
  let counters = { old: 1, new: 1 };
  for (const line of patch.split("\n")) {
    if (line.startsWith("diff --git")) {
      const path = line.split(" b/").pop()?.trim() ?? "unknown";
      current = { path, lines: [] };
      files.push(current);
    } else if (current !== null) {
      if (line.startsWith("+")) {
        current.lines.push({ kind: "add", text: line, oldNo: null, newNo: counters.new });
        counters.new += 1;
      } else if (line.startsWith("-")) {
        current.lines.push({ kind: "del", text: line, oldNo: counters.old, newNo: null });
        counters.old += 1;
      } else if (line.startsWith("@@")) {
        current.lines.push({ kind: "hunk", text: line, oldNo: null, newNo: null });
        const match = line.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
        if (match !== null) {
          counters = { old: Number(match[1]), new: Number(match[2]) };
        }
      } else {
        current.lines.push({ kind: "context", text: line, oldNo: counters.old, newNo: counters.new });
        counters.old += 1;
        counters.new += 1;
      }
    }
  }
  return files;
}

export function DiffViewer({ patch }: { patch: string }) {
  /**
   * Renders a unified diff with per-line styling.
   */
  const files = useMemo(() => parseDiff(patch), [patch]);
  const [copied, setCopied] = useState(false);

  if (files.length === 0) {
    return <div className="diff-viewer diff-empty">no changes yet</div>;
  }

  return (
    <div className="diff-viewer">
      <button
        onClick={() => {
          void navigator.clipboard.writeText(patch);
          setCopied(true);
        }}
      >
        {copied ? "copied" : "copy patch"}
      </button>
      {files.map((file) => (
        <FileSection key={file.path} file={file} />
      ))}

    </div>
  );
}

function FileSection({ file }: { file: DiffFile }) {
  /**
   * Renders one file's diff as a collapsible section.
   */
  const [open, setOpen] = useState(true);

  return (
    <section>
      <h3 onClick={() => setOpen(!open)}>
        {open ? "▾" : "▸"} {file.path}
      </h3>
      {open && (
        <pre>
          {file.lines.map((line, index) => (
            <code key={index} className={`diff-line diff-${line.kind}`}>
              {line.text}
            </code>
          ))}
        </pre>
      )}
    </section>
  );
}
