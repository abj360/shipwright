#!/usr/bin/env ts-node
/**
 * useSandboxSocket.ts --- WebSocket hooks for streaming sandbox output to the viewer
 *
 * Contains:
 *   SocketStatus: connection state of the streaming socket
 *   useSandboxSocket(): maintains the streaming WebSocket
 */

import { useEffect, useRef, useState } from "react";

export type SocketStatus = "connecting" | "open" | "closed";

const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_BASE_MS = 1_000;

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
   * @param onChunk - Called with each output chunk; read through a ref so a
   *   new closure each render does not tear the socket down.
   * @returns status - Current socket status.
   */
  const [status, setStatus] = useState<SocketStatus>("connecting");
  const onChunkRef = useRef(onChunk);
  onChunkRef.current = onChunk;

  useEffect(() => {
    let attempt = 0;
    let cancelled = false;
    let socket: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    const connect = () => {
      setStatus("connecting");
      socket = new WebSocket(`${gatewayUrl}/runs/${runId}/stream`);
      socket.onopen = () => {
        attempt = 0;
        setStatus("open");
      };
      socket.onclose = () => {
        setStatus("closed");
        if (!cancelled && attempt < MAX_RECONNECT_ATTEMPTS) {
          attempt += 1;
          retry = setTimeout(connect, RECONNECT_BASE_MS * attempt);
        }
      };
      socket.onmessage = (event) => onChunkRef.current(String(event.data));
    };
    connect();
    return () => {
      cancelled = true;
      if (retry !== null) {
        clearTimeout(retry);
      }
      socket?.close();
    };
  }, [gatewayUrl, runId]);

  return status;
}
