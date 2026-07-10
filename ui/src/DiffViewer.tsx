#!/usr/bin/env ts-node
/**
 * DiffViewer.tsx --- renders the run's unified diff alongside the terminal output
 *
 * Contains:
 *   DiffLine: one classified diff line
 *   DiffFile: one file's classified lines
 *   parseDiff(): parses a unified diff into per-file lines
 *   DiffViewer: renders a unified diff with per-line styling
 */

import { useMemo } from "react";

export interface DiffLine {
  kind: "add" | "del" | "context" | "hunk";
  text: string;
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
  for (const line of patch.split("\n")) {
    if (line.startsWith("diff --git")) {
      const path = line.split(" b/").pop()?.trim() ?? "unknown";
      current = { path, lines: [] };
      files.push(current);
    } else if (current !== null) {
      if (line.startsWith("+")) {
        current.lines.push({ kind: "add", text: line });
      } else if (line.startsWith("-")) {
        current.lines.push({ kind: "del", text: line });
      } else if (line.startsWith("@@")) {
        current.lines.push({ kind: "hunk", text: line });
      } else {
        current.lines.push({ kind: "context", text: line });
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

  return (
    <div className="diff-viewer">
      {files.map((file) => (
        <section key={file.path}>
          <h3>{file.path}</h3>
          <pre>
            {file.lines.map((line, index) => (
              <code key={index} className={`diff-line diff-${line.kind}`}>
                {line.text}
              </code>
            ))}
          </pre>
        </section>
      ))}
    </div>
  );
}
