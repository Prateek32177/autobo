import { healthTone } from "@/lib/format";

export function StatusBadge({
  label,
  status,
}: {
  label?: string;
  status: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${healthTone(status)}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-80" />
      {label ? `${label}: ` : ""}
      {status}
    </span>
  );
}
