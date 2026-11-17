"use client";

import { useCallback, useEffect, useState } from "react";

import { ComponentTable } from "@/components/ComponentTable";
import { MetricCard } from "@/components/MetricCard";
import { ModeBanner } from "@/components/ModeBanner";
import { StatusBadge } from "@/components/StatusBadge";
import { useLiveTelemetry } from "@/hooks/useLiveTelemetry";
import { api } from "@/lib/api";
import { formatMetric, relativeTime } from "@/lib/format";
import type { DeviceHealth, DeviceSummary, RuntimeMeta } from "@/lib/types";

export default function OverviewPage() {
  const [devices, setDevices] = useState<DeviceSummary[]>([]);
  const [health, setHealth] = useState<DeviceHealth | null>(null);
  const [meta, setMeta] = useState<RuntimeMeta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const primary = devices[0] ?? null;
  const live = useLiveTelemetry(primary?.id ?? null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const [deviceList, runtimeMeta] = await Promise.all([
        api.listDevices(),
        api.meta(),
      ]);
      setDevices(deviceList);
      setMeta(runtimeMeta);
      if (deviceList[0]) {
        const h = await api.getHealth(deviceList[0].id);
        setHealth(h);
      } else {
        setHealth(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load runtime");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 4000);
    return () => clearInterval(timer);
  }, [refresh]);

  const telemetry = live.telemetry ?? health?.latest_telemetry ?? null;

  async function onEmergencyStop() {
    if (!primary) return;
    setBusy(true);
    try {
      await api.emergencyStop(primary.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Emergency stop failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
          <p className="mt-1 text-sm text-zinc-600">
            Live component health and sample telemetry from the local runtime.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge
            label="WS"
            status={live.connected ? "healthy" : "disconnected"}
          />
          <button
            type="button"
            onClick={() => void refresh()}
            className="rounded border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-zinc-50"
          >
            Refresh
          </button>
          <button
            type="button"
            disabled={!primary || busy}
            onClick={() => void onEmergencyStop()}
            className="rounded border border-red-300 bg-red-50 px-3 py-1.5 text-sm font-medium text-red-800 hover:bg-red-100 disabled:opacity-50"
          >
            Emergency stop
          </button>
        </div>
      </div>

      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
          <div className="mt-1 text-xs opacity-80">
            Is the runtime running on http://127.0.0.1:8000?
          </div>
        </div>
      ) : null}

      {meta ? (
        <div className="rounded-md border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-700">
          {meta.note}
        </div>
      ) : null}

      {!primary ? (
        <div className="rounded-md border border-dashed border-zinc-300 bg-white px-4 py-10 text-center text-sm text-zinc-600">
          No devices registered yet.
        </div>
      ) : (
        <>
          <ModeBanner
            mode={health?.connection_mode || primary.connection_type}
            note={
              primary.is_simulation
                ? "Simulated rover seeded by the runtime. Interfaces match the future ESP32 serial adapter."
                : undefined
            }
          />

          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Device"
              value={primary.name}
              hint={`${primary.id} · fw ${primary.firmware_version || "—"}`}
            />
            <MetricCard
              label="Connectivity"
              value={primary.connectivity_status}
              hint={`Heartbeat ${relativeTime(live.lastHeartbeatAt || primary.last_heartbeat_at)}`}
            />
            <MetricCard
              label="Battery"
              value={formatMetric(telemetry?.battery_voltage)}
              unit="V"
              hint="Simulated drain + ripple"
            />
            <MetricCard
              label="Distance"
              value={formatMetric(telemetry?.distance_cm, 1)}
              unit="cm"
              hint={`Enc L/R ${formatMetric(telemetry?.left_encoder, 0)} / ${formatMetric(telemetry?.right_encoder, 0)}`}
            />
          </section>

          <section className="grid gap-3 lg:grid-cols-3">
            <div className="rounded-md border border-zinc-200 bg-white p-4 lg:col-span-2">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
                  Component health
                </h2>
                <StatusBadge status={health?.health_status || primary.health_status} />
              </div>
              {health ? (
                <ComponentTable components={health.components} />
              ) : (
                <p className="text-sm text-zinc-500">Loading components…</p>
              )}
            </div>

            <div className="rounded-md border border-zinc-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
                Live stream
              </h2>
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-zinc-500">Mode</dt>
                  <dd className="font-mono">{telemetry?.mode || "simulation"}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-zinc-500">Uptime</dt>
                  <dd className="font-mono">
                    {formatMetric(telemetry?.uptime_ms, 0)} ms
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-zinc-500">Motors</dt>
                  <dd className="font-mono">
                    {telemetry?.motor_status
                      ? `${telemetry.motor_status.left}/${telemetry.motor_status.right}`
                      : "idle/idle"}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-zinc-500">WS events</dt>
                  <dd className="font-mono">{live.eventCount}</dd>
                </div>
              </dl>
              <pre className="mt-4 max-h-56 overflow-auto rounded border border-zinc-100 bg-zinc-50 p-3 text-[11px] leading-relaxed text-zinc-700">
                {JSON.stringify(telemetry, null, 2) || "Waiting for telemetry…"}
              </pre>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
