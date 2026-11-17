"use client";

import { useCallback, useEffect, useState } from "react";

import { ModeBanner } from "@/components/ModeBanner";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { Device, DeviceSummary } from "@/lib/types";

export default function DevicesPage() {
  const [devices, setDevices] = useState<DeviceSummary[]>([]);
  const [selected, setSelected] = useState<Device | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const list = await api.listDevices();
      setDevices(list);
      if (list[0]) {
        const detail = await api.getDevice(list[0].id);
        setSelected(detail);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load devices");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function connect(deviceId: string) {
    setBusyId(deviceId);
    try {
      await api.connect(deviceId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connect failed");
    } finally {
      setBusyId(null);
    }
  }

  async function disconnect(deviceId: string) {
    setBusyId(deviceId);
    try {
      await api.disconnect(deviceId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Disconnect failed");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Devices</h1>
        <p className="mt-1 text-sm text-zinc-600">
          Register and connect hardware. Milestone 1 ships a seeded simulated rover.
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
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Firmware</th>
              <th className="px-4 py-3 font-medium">Heartbeat</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {devices.map((device) => (
              <tr key={device.id} className="border-b border-zinc-100 last:border-0">
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
                  <div className="flex flex-col gap-1">
                    <StatusBadge status={device.connectivity_status} />
                    <StatusBadge status={device.health_status} />
                  </div>
                </td>
                <td className="px-4 py-3 font-mono text-xs">
                  {device.firmware_version || "—"}
                </td>
                <td className="px-4 py-3 text-zinc-600">
                  {relativeTime(device.last_heartbeat_at)}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={busyId === device.id}
                      onClick={() => void connect(device.id)}
                      className="rounded border border-zinc-300 px-2 py-1 text-xs font-medium hover:bg-zinc-50 disabled:opacity-50"
                    >
                      Connect
                    </button>
                    <button
                      type="button"
                      disabled={busyId === device.id}
                      onClick={() => void disconnect(device.id)}
                      className="rounded border border-zinc-300 px-2 py-1 text-xs font-medium hover:bg-zinc-50 disabled:opacity-50"
                    >
                      Disconnect
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected ? (
        <div className="space-y-3">
          <ModeBanner mode={selected.connection.type} />
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
