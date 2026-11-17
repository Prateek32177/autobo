"use client";

import { useEffect, useState } from "react";

import { api, getApiBase } from "@/lib/api";
import type { RuntimeMeta } from "@/lib/types";

export default function SettingsPage() {
  const [meta, setMeta] = useState<RuntimeMeta | null>(null);
  const [portsNote, setPortsNote] = useState<string | null>(null);
  const [portCount, setPortCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [runtimeMeta, ports] = await Promise.all([api.meta(), api.listPorts()]);
        setMeta(runtimeMeta);
        setPortCount(ports.ports?.length ?? 0);
        setPortsNote(ports.note || null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Backend unavailable");
      }
    })();
  }, []);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-zinc-600">
          Local runtime configuration. LLM provider/key storage is Milestone 4.
        </p>
      </div>

      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      <div className="rounded-md border border-zinc-200 bg-white p-4 text-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Local endpoints
        </h2>
        <dl className="mt-3 space-y-2">
          <div className="flex justify-between gap-3">
            <dt className="text-zinc-500">API base</dt>
            <dd className="font-mono text-xs">{getApiBase()}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-zinc-500">LLM configured</dt>
            <dd className="font-mono text-xs">
              {meta?.llm_configured ? "yes" : "no (not required for simulation)"}
            </dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-zinc-500">AI ready</dt>
            <dd className="font-mono text-xs">{String(meta?.ai_ready ?? false)}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-zinc-500">Serial ports visible</dt>
            <dd className="font-mono text-xs">
              {portCount === null ? "…" : portCount}
            </dd>
          </div>
        </dl>
        {portsNote ? <p className="mt-3 text-xs text-zinc-500">{portsNote}</p> : null}
      </div>

      <div className="rounded-md border border-dashed border-zinc-300 bg-white px-4 py-6 text-sm text-zinc-600">
        LLM API keys will use OS credential storage on the runtime host. They will
        never be returned to this browser UI. No key is required to run simulation.
      </div>
    </div>
  );
}
