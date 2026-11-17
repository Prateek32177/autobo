export default function DiagnosticsPage() {
  return (
    <Placeholder
      title="Diagnostics"
      body="Deterministic diagnostic rules and AI explanations arrive in Milestone 3–4. Event history APIs are already stubbed on the runtime."
    />
  );
}

function Placeholder({ title, body }: { title: string; body: string }) {
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <div className="rounded-md border border-dashed border-zinc-300 bg-white px-4 py-8 text-sm text-zinc-600">
        {body}
      </div>
    </div>
  );
}
