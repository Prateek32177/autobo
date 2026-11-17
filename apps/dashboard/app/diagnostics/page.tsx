"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";

export default function DiagnosticsPage() {
  const [events, setEvents] = useState<unknown[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      await api.ready();
      setBackendOk(true);
      const devices = await api.listDevices();
      const primary = devices[0];
      if (primary) {
        const payload = await api.listDiagnosticEvents(primary.id);
        setEvents(payload.events || []);
        setNote(payload.note || null);
      } else {
        const payload = await api.listDiagnosticEvents();
        setEvents(payload.events || []);
        setNote(null);
      }
    } catch (err) {
      setBackendOk(false);
      setError(err instanceof Error ? err.message : "Failed to load diagnostics");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Diagnostics</h1>
        <p className="mt-1 text-sm text-zinc-600">
          Event history from the local runtime. Deterministic diagnostic rules
          (Milestone 3) and AI explanations (Milestone 4) are not implemented yet.
        </p>
      </div>

      {backendOk === false || error ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error || "Backend unavailable"}
        </div>
      ) : null}

      {note ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          {note}
        </div>
      ) : null}

      <div className="rounded-md border border-zinc-200 bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Diagnostic events
          </h2>
          <button
            type="button"
            onClick={() => void refresh()}
            className="rounded border border-zinc-300 px-2 py-1 text-xs font-medium hover:bg-zinc-50"
          >
            Refresh
          </button>
        </div>
        {events.length === 0 ? (
          <p className="text-sm text-zinc-600">
            No diagnostic events stored yet. Simulation is healthy until a rule
            engine (M3) records faults.
          </p>
        ) : (
          <pre className="max-h-96 overflow-auto rounded border border-zinc-100 bg-zinc-50 p-3 text-[11px] text-zinc-700">
            {JSON.stringify(events, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
