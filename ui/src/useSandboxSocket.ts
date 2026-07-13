#!/usr/bin/env ts-node
/**
 * useSandboxSocket.ts --- WebSocket hooks for streaming sandbox output to the viewer
 *
 * Contains:
 *   useSandboxSocket(): maintains the streaming WebSocket
 */

import { useEffect, useRef, useState } from "react";

export type SocketStatus = "connecting" | "open" | "closed";

export function useSandboxSocket(
  gatewayUrl: string,
  runId: string,
  onChunk: (data: string) => void,
): SocketStatus {
  /**
   * Maintains the run's streaming WebSocket and reports its status.
   *
   * @param gatewayUrl - Gateway base URL.
   * @param runId - Run to stream.
   * @param onChunk - Called with each output chunk.
   * @returns status - Current socket status.
   */
  const [status, setStatus] = useState<SocketStatus>("connecting");

  useEffect(() => {
    setStatus("connecting");
    const socket = new WebSocket(`${gatewayUrl}/runs/${runId}/stream`);
    socket.onopen = () => setStatus("open");
    socket.onclose = () => setStatus("closed");
    socket.onmessage = (event) => onChunk(String(event.data));
    return () => socket.close();
  }, [gatewayUrl, runId]);

  return status;
}
