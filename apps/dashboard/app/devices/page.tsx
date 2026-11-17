"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ModeBanner } from "@/components/ModeBanner";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { Device, DeviceSummary } from "@/lib/types";

const SELECTED_DEVICE_KEY = "physical_ai_overview_device_id";

export default function DevicesPage() {
  const [devices, setDevices] = useState<DeviceSummary[]>([]);
  const [selected, setSelected] = useState<Device | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const selectedIdRef = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const list = await api.listDevices();
      setDevices(list);
      const keepId = selectedIdRef.current;
      const nextId =
        (keepId && list.some((d) => d.id === keepId) && keepId) ||
        list.find((d) => d.connectivity_status === "connected")?.id ||
        list[0]?.id ||
        null;
      if (nextId) {
        const detail = await api.getDevice(nextId);
        selectedIdRef.current = detail.id;
        setSelected(detail);
      } else {
        selectedIdRef.current = null;
        setSelected(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load devices");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function selectRow(deviceId: string) {
    try {
      setError(null);
      const detail = await api.getDevice(deviceId);
      selectedIdRef.current = detail.id;
      setSelected(detail);
      try {
        window.localStorage.setItem(SELECTED_DEVICE_KEY, deviceId);
      } catch {
        // ignore
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load device");
    }
  }

  async function toggleConnection(device: DeviceSummary) {
    setBusyId(device.id);
    try {
      if (device.connectivity_status === "connected") {
        await api.disconnect(device.id);
      } else {
        await api.connect(device.id);
      }
      await selectRow(device.id);
      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : device.connectivity_status === "connected"
            ? "Disconnect failed"
            : "Connect failed",
      );
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Devices</h1>
        <p className="mt-1 text-sm text-zinc-600">
          Click a row to inspect it. Use the single connection button to connect
          or disconnect.
        </p>
      </div>

      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-md border border-zinc-200 bg-white">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-zinc-200 bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Mode</th>
              <th className="px-4 py-3 font-medium">Link</th>
              <th className="px-4 py-3 font-medium">Health</th>
              <th className="px-4 py-3 font-medium">Firmware</th>
              <th className="px-4 py-3 font-medium">Heartbeat</th>
              <th className="px-4 py-3 font-medium">Action</th>
            </tr>
          </thead>
          <tbody>
            {devices.map((device) => {
              const isConnected = device.connectivity_status === "connected";
              const busy = busyId === device.id;
              return (
                <tr
                  key={device.id}
                  className={`cursor-pointer border-b border-zinc-100 last:border-0 ${
                    selected?.id === device.id ? "bg-sky-50/70" : "hover:bg-zinc-50"
                  }`}
                  onClick={() => void selectRow(device.id)}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium">{device.name}</div>
                    <div className="font-mono text-xs text-zinc-500">{device.id}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded border border-sky-200 bg-sky-50 px-2 py-0.5 text-xs font-medium uppercase text-sky-800">
                      {device.connection_type}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge
                      status={isConnected ? "connected" : "disconnected"}
                    />
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={device.health_status} />
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">
                    {device.firmware_version || "—"}
                  </td>
                  <td className="px-4 py-3 text-zinc-600">
                    {relativeTime(device.last_heartbeat_at)}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={(event) => {
                        event.stopPropagation();
                        void toggleConnection(device);
                      }}
                      className={
                        isConnected
                          ? "rounded border border-zinc-400 bg-white px-3 py-1 text-xs font-semibold text-zinc-800 hover:bg-zinc-50 disabled:opacity-50"
                          : "rounded border border-emerald-400 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-900 hover:bg-emerald-100 disabled:opacity-50"
                      }
                    >
                      {busy
                        ? isConnected
                          ? "Disconnecting…"
                          : "Connecting…"
                        : isConnected
                          ? "Disconnect"
                          : "Connect"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {selected ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <ModeBanner mode={selected.connection.type} />
            <StatusBadge
              status={
                selected.connectivity_status === "connected"
                  ? "connected"
                  : "disconnected"
              }
            />
          </div>
          <div className="rounded-md border border-zinc-200 bg-white p-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
              Components ({selected.components.length})
            </h2>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              {selected.components.map((component) => (
                <li
                  key={component.id}
                  className="flex items-center justify-between rounded border border-zinc-100 bg-zinc-50 px-3 py-2 text-sm"
                >
                  <span>
                    <span className="font-medium">{component.name}</span>
                    <span className="ml-2 font-mono text-xs text-zinc-500">
                      {component.component_type}
                    </span>
                  </span>
                  <StatusBadge status={component.health_status} />
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-md border border-zinc-200 bg-white p-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
              Capabilities
            </h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {selected.capabilities.map((cap) => (
                <span
                  key={cap.name}
                  className="rounded border border-zinc-200 bg-zinc-50 px-2 py-1 font-mono text-xs text-zinc-700"
                  title={cap.description}
                >
                  {cap.name}
                </span>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
