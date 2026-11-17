"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ComponentTable } from "@/components/ComponentTable";
import { MetricCard } from "@/components/MetricCard";
import { ModeBanner } from "@/components/ModeBanner";
import { StatusBadge } from "@/components/StatusBadge";
import { useLiveTelemetry } from "@/hooks/useLiveTelemetry";
import { api } from "@/lib/api";
import { formatMetric, relativeTime } from "@/lib/format";
import type { DeviceHealth, DeviceSummary, RuntimeMeta } from "@/lib/types";

const SELECTED_DEVICE_KEY = "physical_ai_overview_device_id";

function pickDefaultDeviceId(devices: DeviceSummary[], preferred: string | null): string | null {
  if (preferred && devices.some((d) => d.id === preferred)) return preferred;
  const connectedSerial = devices.find(
    (d) => d.connectivity_status === "connected" && d.connection_type === "serial",
  );
  if (connectedSerial) return connectedSerial.id;
  const connected = devices.find((d) => d.connectivity_status === "connected");
  if (connected) return connected.id;
  return devices[0]?.id ?? null;
}

export default function OverviewPage() {
  const [devices, setDevices] = useState<DeviceSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [health, setHealth] = useState<DeviceHealth | null>(null);
  const [meta, setMeta] = useState<RuntimeMeta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const selectedIdRef = useRef<string | null>(null);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(SELECTED_DEVICE_KEY);
      if (stored) {
        selectedIdRef.current = stored;
        setSelectedId(stored);
      }
    } catch {
      // ignore
    }
  }, []);

  const primary = useMemo(
    () => devices.find((d) => d.id === selectedId) ?? null,
    [devices, selectedId],
  );
  const live = useLiveTelemetry(primary?.id ?? null);
  const connected = primary?.connectivity_status === "connected";

  const selectDevice = useCallback((deviceId: string) => {
    selectedIdRef.current = deviceId;
    setSelectedId(deviceId);
    setHealth(null);
    try {
      window.localStorage.setItem(SELECTED_DEVICE_KEY, deviceId);
    } catch {
      // ignore
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const [deviceList, runtimeMeta] = await Promise.all([
        api.listDevices(),
        api.meta(),
      ]);
      setDevices(deviceList);
      setMeta(runtimeMeta);

      const nextId = pickDefaultDeviceId(deviceList, selectedIdRef.current);
      if (nextId && nextId !== selectedIdRef.current) {
        selectedIdRef.current = nextId;
        setSelectedId(nextId);
        try {
          window.localStorage.setItem(SELECTED_DEVICE_KEY, nextId);
        } catch {
          // ignore
        }
      }

      const activeId = nextId;
      if (activeId) {
        const h = await api.getHealth(activeId);
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

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    void api
      .getHealth(selectedId)
      .then((h) => {
        if (!cancelled) setHealth(h);
      })
      .catch(() => {
        /* refresh loop will surface errors */
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const telemetry = live.telemetry ?? health?.latest_telemetry ?? null;
  const emergencyStopped = Boolean(
    health?.emergency_stopped || telemetry?.emergency_stopped,
  );

  async function onToggleEmergencyStop() {
    if (!primary) return;
    setBusy(true);
    setError(null);
    try {
      if (emergencyStopped) {
        const result = await api.clearEmergencyStop(primary.id);
        if (result.emergency_stopped) {
          setError(result.message || "Failed to clear emergency stop");
        }
      } else {
        if (!connected) {
          await api.connect(primary.id);
          await refresh();
        }
        const result = await api.emergencyStop(primary.id);
        if (!result.stopped?.length) {
          setError(result.message || "Emergency stop had no effect");
        }
      }
      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : emergencyStopped
            ? "Failed to clear emergency stop"
            : "Emergency stop failed",
      );
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
            Live component health and telemetry for the selected device.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {devices.length > 0 ? (
            <label className="flex items-center gap-2 text-sm text-zinc-600">
              <span className="whitespace-nowrap">Device</span>
              <select
                className="max-w-[18rem] rounded border border-zinc-300 bg-white px-2 py-1.5 text-sm font-medium text-zinc-900"
                value={primary?.id ?? ""}
                onChange={(event) => selectDevice(event.target.value)}
              >
                {devices.map((device) => (
                  <option key={device.id} value={device.id}>
                    {device.name} · {device.connection_type} ·{" "}
                    {device.connectivity_status}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
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
            onClick={() => void onToggleEmergencyStop()}
            className={
              emergencyStopped
                ? "rounded border border-emerald-400 bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-900 hover:bg-emerald-100 disabled:opacity-50"
                : "rounded border border-red-300 bg-red-50 px-3 py-1.5 text-sm font-medium text-red-800 hover:bg-red-100 disabled:opacity-50"
            }
          >
            {busy
              ? emergencyStopped
                ? "Clearing…"
                : "Stopping…"
              : emergencyStopped
                ? "Clear emergency stop"
                : "Emergency stop"}
          </button>
        </div>
      </div>

      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      {emergencyStopped ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-red-400 bg-red-100 px-4 py-3 text-sm text-red-950">
          <div>
            <div className="font-semibold tracking-wide">Emergency stop: ENGAGED</div>
            <p className="mt-1">
              Motors are idle and motion is blocked. Press{" "}
              <strong>Clear emergency stop</strong> to resume.
            </p>
          </div>
          <button
            type="button"
            disabled={busy || !primary}
            onClick={() => void onToggleEmergencyStop()}
            className="rounded border border-emerald-500 bg-white px-3 py-1.5 text-sm font-medium text-emerald-900 hover:bg-emerald-50 disabled:opacity-50"
          >
            Clear emergency stop
          </button>
        </div>
      ) : null}

      {primary && !connected && !error ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          Device is <strong>disconnected</strong>. Connect it on the Devices page
          before expecting live telemetry or motion.
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
                ? "MockHardwareAdapter seed — not the Virtual ESP32 serial path."
                : "Serial path (Virtual ESP32 or physical board) via SerialHardwareAdapter."
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
              hint={
                primary.is_simulation
                  ? "Simulated drain + ripple"
                  : "From serial telemetry"
              }
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
                  <dt className="text-zinc-500">E-stop</dt>
                  <dd className="font-mono">
                    {emergencyStopped ? "ENGAGED" : "clear"}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-zinc-500">Mode</dt>
                  <dd className="font-mono">
                    {telemetry?.mode || primary.connection_type}
                  </dd>
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
