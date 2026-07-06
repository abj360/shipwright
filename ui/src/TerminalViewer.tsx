#!/usr/bin/env ts-node
/**
 * TerminalViewer.tsx --- xterm.js live terminal streaming one run's sandbox output
 *
 * Contains:
 *   TerminalViewerProps: run and gateway to stream from
 *   TerminalViewer: streams sandbox output into xterm.js
 */

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

  useEffect(() => {
    const term = new Terminal({ convertEol: true, scrollback: 5_000 });
    const fit = new FitAddon();
    term.loadAddon(fit);
    if (hostRef.current !== null) {
      term.open(hostRef.current);
      fit.fit();
    }
    const socket = new WebSocket(`${gatewayUrl}/runs/${runId}/stream`);
    socket.onmessage = (event) => {
      term.write(String(event.data));
    };
    return () => {
      socket.close();
      term.dispose();
    };
  }, [runId, gatewayUrl]);

  return <div className="terminal-viewer" ref={hostRef} />;
}
