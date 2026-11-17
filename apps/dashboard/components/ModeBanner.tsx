export function ModeBanner({
  mode,
  note,
}: {
  mode: "simulation" | "serial" | string;
  note?: string;
}) {
  const isSim = mode === "simulation";
  return (
    <div
      className={`rounded-md border px-4 py-3 text-sm ${
        isSim
          ? "border-sky-300 bg-sky-50 text-sky-950"
          : "border-violet-300 bg-violet-50 text-violet-950"
      }`}
    >
      <div className="font-semibold tracking-wide">
        Hardware mode: {isSim ? "SIMULATION" : mode.toUpperCase()}
      </div>
      <p className="mt-1 text-sm opacity-90">
        {note ||
          (isSim
            ? "This device is explicitly simulated. No physical ESP32 is connected."
            : "Live serial hardware mode.")}
      </p>
    </div>
  );
}
