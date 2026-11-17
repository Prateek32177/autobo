"use client";

import { useEffect, useRef, useState } from "react";

import { getWsUrl } from "@/lib/api";
import type { TelemetrySnapshot } from "@/lib/types";

type LiveEvent = {
  type: string;
  device_id?: string;
  [key: string]: unknown;
};

export function useLiveTelemetry(deviceId: string | null) {
  const [telemetry, setTelemetry] = useState<TelemetrySnapshot | null>(null);
  const [lastHeartbeatAt, setLastHeartbeatAt] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [eventCount, setEventCount] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    setTelemetry(null);
    setLastHeartbeatAt(null);
    setEventCount(0);
    setConnected(false);

    if (!deviceId) return;

    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      if (cancelled) return;
      const ws = new WebSocket(getWsUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        if (!cancelled) setConnected(true);
      };

      ws.onclose = () => {
        if (cancelled) return;
        setConnected(false);
        retryTimer = setTimeout(connect, 1500);
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as LiveEvent;
          if (payload.device_id && payload.device_id !== deviceId) return;
          setEventCount((n) => n + 1);
          if (payload.type === "telemetry") {
            setTelemetry(payload as unknown as TelemetrySnapshot);
          }
          if (payload.type === "heartbeat") {
            setLastHeartbeatAt(
              (payload.received_at as string) || new Date().toISOString(),
            );
          }
        } catch {
          // ignore malformed frames
        }
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, [deviceId]);

  return { telemetry, lastHeartbeatAt, connected, eventCount };
}
