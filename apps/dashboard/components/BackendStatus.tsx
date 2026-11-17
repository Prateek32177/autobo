"use client";

import { useCallback, useEffect, useState } from "react";

import { api, getApiBase } from "@/lib/api";

type Status = "checking" | "online" | "offline";

export function BackendStatus() {
  const [status, setStatus] = useState<Status>("checking");
  const [detail, setDetail] = useState<string>(getApiBase());

  const ping = useCallback(async () => {
    try {
      const ready = await api.ready();
      if (ready.ready) {
        setStatus("online");
        setDetail(`${getApiBase()} · ready`);
      } else {
        setStatus("offline");
        setDetail(ready.detail || "backend not ready");
      }
    } catch {
      setStatus("offline");
      setDetail(`${getApiBase()} unreachable`);
    }
  }, []);

  useEffect(() => {
    void ping();
    const timer = setInterval(() => void ping(), 5000);
    return () => clearInterval(timer);
  }, [ping]);

  const tone =
    status === "online"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : status === "offline"
        ? "border-red-200 bg-red-50 text-red-800"
        : "border-zinc-200 bg-zinc-50 text-zinc-600";

  return (
    <div
      className={`rounded border px-2.5 py-1 text-xs font-medium ${tone}`}
      title={detail}
    >
      Backend: {status}
    </div>
  );
}
