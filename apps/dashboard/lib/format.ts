import type { HealthStatus } from "./types";

export function formatMetric(value: unknown, digits = 2): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(digits);
  }
  return String(value);
}

export function healthTone(status: HealthStatus | string): string {
  switch (status) {
    case "healthy":
      return "text-emerald-700 bg-emerald-50 border-emerald-200";
    case "degraded":
      return "text-amber-800 bg-amber-50 border-amber-200";
    case "unhealthy":
    case "error":
      return "text-red-700 bg-red-50 border-red-200";
    case "disconnected":
      return "text-zinc-600 bg-zinc-100 border-zinc-200";
    default:
      return "text-slate-600 bg-slate-100 border-slate-200";
  }
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "never";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;
  const delta = Date.now() - then;
  if (delta < 2000) return "just now";
  if (delta < 60_000) return `${Math.floor(delta / 1000)}s ago`;
  return `${Math.floor(delta / 60_000)}m ago`;
}
