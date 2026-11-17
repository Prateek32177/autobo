"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

export default function TasksPage() {
  const [backendOk, setBackendOk] = useState<boolean | null>(null);

  useEffect(() => {
    void api
      .ready()
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false));
  }, []);

  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-semibold tracking-tight">AI Playground</h1>
      <div className="rounded-md border border-dashed border-zinc-300 bg-white px-4 py-8 text-sm text-zinc-600">
        <p>
          Natural-language task planning is <strong>not implemented yet</strong>{" "}
          (Milestone 4). Capability registration and the action executor exist on
          the runtime, but this UI will not pretend they are complete.
        </p>
        <p className="mt-3">
          Backend status:{" "}
          {backendOk === null ? "checking…" : backendOk ? "reachable" : "unreachable"}
        </p>
      </div>
    </div>
  );
}
