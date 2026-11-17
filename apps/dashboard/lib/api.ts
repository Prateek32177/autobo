import type { Device, DeviceHealth, DeviceSummary, RuntimeMeta } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const detail = await response.text();
    try {
      const parsed = JSON.parse(detail) as { detail?: string };
      throw new Error(parsed.detail || detail || `Request failed: ${response.status}`);
    } catch (err) {
      if (err instanceof Error && err.message !== detail) throw err;
      throw new Error(detail || `Request failed: ${response.status}`);
    }
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export function getApiBase(): string {
  return API_BASE;
}

export function getWsUrl(): string {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}/ws`;
}

async function readyRequest(): Promise<{
  ready: boolean;
  database: string;
  detail: string;
}> {
  const response = await fetch(`${API_BASE}/ready`, { cache: "no-store" });
  const body = (await response.json()) as {
    ready: boolean;
    database: string;
    detail: string;
  };
  if (!response.ok && response.status !== 503) {
    throw new Error(body.detail || `Ready check failed: ${response.status}`);
  }
  return body;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  ready: () => readyRequest(),
  meta: () => request<RuntimeMeta>("/api/meta"),
  listDevices: () => request<DeviceSummary[]>("/api/devices"),
  getDevice: (id: string) => request<Device>(`/api/devices/${id}`),
  getHealth: (id: string) => request<DeviceHealth>(`/api/devices/${id}/health`),
  listDiagnosticEvents: (deviceId?: string) =>
    request<{ device_id?: string; events: unknown[]; note?: string }>(
      deviceId
        ? `/api/devices/${deviceId}/diagnostics`
        : "/api/diagnostics/events",
    ),
  listPorts: () =>
    request<{ ports: Array<Record<string, unknown>>; note?: string }>(
      "/api/hardware/ports",
    ),
  connect: (deviceId: string) =>
    request<Device>("/api/hardware/connect", {
      method: "POST",
      body: JSON.stringify({ device_id: deviceId }),
    }),
  disconnect: (deviceId: string) =>
    request<Device>("/api/hardware/disconnect", {
      method: "POST",
      body: JSON.stringify({ device_id: deviceId }),
    }),
};
