import { formatMetric, relativeTime } from "@/lib/format";
import type { DeviceHealth } from "@/lib/types";

import { StatusBadge } from "./StatusBadge";

export function ComponentTable({
  components,
}: {
  components: DeviceHealth["components"];
}) {
  return (
    <div className="overflow-hidden rounded-md border border-zinc-200 bg-white">
      <table className="min-w-full text-left text-sm">
        <thead className="border-b border-zinc-200 bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
          <tr>
            <th className="px-4 py-3 font-medium">Component</th>
            <th className="px-4 py-3 font-medium">Type</th>
            <th className="px-4 py-3 font-medium">Health</th>
            <th className="px-4 py-3 font-medium">Last reading</th>
            <th className="px-4 py-3 font-medium">Metrics</th>
          </tr>
        </thead>
        <tbody>
          {components.map((component) => (
            <tr key={component.id} className="border-b border-zinc-100 last:border-0">
              <td className="px-4 py-3 font-medium text-zinc-900">
                {component.name}
              </td>
              <td className="px-4 py-3 font-mono text-xs text-zinc-600">
                {component.component_type}
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={component.health_status} />
              </td>
              <td className="px-4 py-3 text-zinc-600">
                {relativeTime(component.last_reading_at)}
              </td>
              <td className="px-4 py-3 font-mono text-xs text-zinc-700">
                {Object.keys(component.metrics || {}).length === 0
                  ? "—"
                  : Object.entries(component.metrics)
                      .map(([k, v]) => `${k}=${formatMetric(v)}`)
                      .join(" · ")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
