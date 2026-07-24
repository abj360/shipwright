#!/usr/bin/env ts-node
/**
 * TerminalViewer.tsx --- xterm.js live terminal streaming one run's sandbox output
 *
 * Contains:
 *   TerminalViewerProps: run and gateway to stream from
 *   TerminalViewer: streams sandbox output into xterm.js
 *   MAX_PENDING_CHUNKS: write-queue cap
 */

import { useSandboxSocket } from "./useSandboxSocket";
import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { useEffect, useRef } from "react";

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
  const flushRef = useRef(false);
  useSandboxSocket(gatewayUrl, runId, (data) => {
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
    const term = new Terminal({ convertEol: true, scrollback: 5_000 });
    termRef.current = term;
    const fit = new FitAddon();
    term.loadAddon(fit);
    if (hostRef.current !== null) {
      term.open(hostRef.current);
      fit.fit();
    }
    return () => {
      term.dispose();
    };
  }, [runId, gatewayUrl]);

  return <div className="terminal-viewer" ref={hostRef} />;
}

const MAX_PENDING_CHUNKS = 100;
