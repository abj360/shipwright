/**
 * TerminalViewer.tsx --- xterm.js live terminal streaming one run's sandbox output
 *
 * Contains:
 *   TerminalViewerProps: run and gateway to stream from
 *   TerminalViewer: streams sandbox output into xterm.js
 *   MAX_PENDING_CHUNKS: write-queue cap
 */

import { useSandboxSocket } from "./useSandboxSocket";
import { fonts, xtermTheme } from "./theme";
import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { useEffect, useRef, useState } from "react";

const MAX_PENDING_CHUNKS = 100;
const TERMINAL_SCROLLBACK = 5_000;
const TERMINAL_FONT_SIZE = 13;

export interface TerminalViewerProps {
  runId: string;
  gatewayUrl: string;
}

export function TerminalViewer({ runId, gatewayUrl }: TerminalViewerProps) {
  /**
   * Streams one run's sandbox output into a live xterm.js terminal.
   */
  const hostRef = useRef<HTMLDivElement>(null);

  const termRef = useRef<Terminal | null>(null);
  const pendingRef = useRef<string[]>([]);
  const pausedRef = useRef(false);
  const flushRef = useRef(false);
  const status = useSandboxSocket(gatewayUrl, runId, (data) => {
    if (pausedRef.current) {
      return;
    }
    if (pendingRef.current.length >= MAX_PENDING_CHUNKS) {
      return;
    }
    pendingRef.current.push(data);
    if (!flushRef.current) {
      flushRef.current = true;
      requestAnimationFrame(() => {
        const term = termRef.current;
        if (term !== null) {
          for (const chunk of pendingRef.current) {
            term.write(chunk);
          }
        }
        pendingRef.current = [];
        flushRef.current = false;
      });
    }
  });

  useEffect(() => {
    const term = new Terminal({
      convertEol: true,
      scrollback: TERMINAL_SCROLLBACK,
      theme: xtermTheme,
      fontFamily: fonts.mono,
    });
    termRef.current = term;
    term.options.linkHandler = {
      activate(_event: MouseEvent, text: string): void {
        window.open(text, "_blank", "noopener");
      },
    };
    term.options.fontSize = TERMINAL_FONT_SIZE;
    term.options.cursorBlink = true;
    const fit = new FitAddon();
    term.loadAddon(fit);
    let disposed = false;
    // fit() reads the renderer's cell size and throws while the container is
    // still zero-sized or the terminal has been disposed; proposeDimensions()
    // returns undefined in exactly those cases, so it is the guard.
    const refit = () => {
      if (disposed || fit.proposeDimensions() === undefined) {
        return;
      }
      fit.fit();
    };
    let observer: ResizeObserver | null = null;
    if (hostRef.current !== null) {
      term.open(hostRef.current);
      refit();
      observer = new ResizeObserver(refit);
      observer.observe(hostRef.current);
    }
    return () => {
      disposed = true;
      observer?.disconnect();
      termRef.current = null;
      term.dispose();
    };
  }, [runId, gatewayUrl]);

  const [paused, setPaused] = useState(false);
  pausedRef.current = paused;

  return (
    <div className="terminal-viewer">
      <div className="terminal-toolbar">
        <span className={`status-badge status-${status}`}>{status}</span>
        <button onClick={() => setPaused(!paused)}>{paused ? "resume" : "pause"}</button>
      </div>
      <div ref={hostRef} role="log" aria-label="sandbox output" />
    </div>
  );
}
