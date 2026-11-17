export default function SettingsPage() {
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
      <div className="rounded-md border border-dashed border-zinc-300 bg-white px-4 py-8 text-sm text-zinc-600">
        LLM provider configuration (LiteLLM + OS keyring) is Milestone 4. No-LLM
        mode will remain available for hardware and diagnostics testing.
      </div>
    </div>
  );
}
