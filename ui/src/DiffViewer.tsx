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
 *   DiffLineView: one diff line with line numbers
 *   diffStats(): counts added and removed lines
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
  const stats = useMemo(() => diffStats(files), [files]);
  const [copied, setCopied] = useState(false);
  const [wrap, setWrap] = useState(false);

  if (files.length === 0) {
    return <div className="diff-viewer diff-empty">no changes yet</div>;
  }

  return (
    <div className={`diff-viewer ${wrap ? "diff-wrap" : ""}`}>
      <label>
        <input type="checkbox" checked={wrap} onChange={() => setWrap(!wrap)} /> wrap
      </label>
      <span className="diff-stats">
        +{stats.added} / -{stats.removed}
      </span>
      <button
        onClick={() => {
          void navigator.clipboard.writeText(patch);
          setCopied(true);
        }}
      >
        {copied ? "copied" : "copy patch"}
      </button>
      <nav className="diff-tree">
        {files.map((file) => (
          <a key={file.path} href={`#diff-${file.path}`}>
            {file.path}
          </a>
        ))}
      </nav>
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
    <section id={`diff-${file.path}`}>
      <h3 onClick={() => setOpen(!open)}>
        {open ? "▾" : "▸"} {file.path}
      </h3>
      {open && (
        <pre>
          {file.lines.map((line, index) => (
            <DiffLineView key={index} line={line} />
          ))}
        </pre>
      )}
    </section>
  );
}

function DiffLineView({ line }: { line: DiffLine }) {
  /**
   * Renders one diff line with old and new line numbers.
   */
  return (
    <code className={`diff-line diff-${line.kind}`}>
      <span className="line-no">{line.oldNo ?? ""}</span>
      <span className="line-no">{line.newNo ?? ""}</span>
      {line.text}
    </code>
  );
}

export function diffStats(files: DiffFile[]): { added: number; removed: number } {
  /**
   * Counts added and removed lines across all files.
   *
   * @param files - Parsed diff files.
   * @returns stats - Added and removed line counts.
   */
  let added = 0;
  let removed = 0;
  for (const file of files) {
    for (const line of file.lines) {
      if (line.kind === "add") {
        added += 1;
      } else if (line.kind === "del") {
        removed += 1;
      }
    }
  }
  return { added, removed };
}
