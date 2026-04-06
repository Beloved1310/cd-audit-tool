import type { ConfidenceLevel } from "@/types/audit";

const styles: Record<ConfidenceLevel, string> = {
  high:
    "border border-emerald-500/40 bg-emerald-950/50 text-emerald-300 ring-1 ring-emerald-500/20",
  medium:
    "border border-amber-500/40 bg-amber-950/40 text-amber-200 ring-1 ring-amber-500/20",
  low: "border border-red-500/40 bg-red-950/40 text-red-300 ring-1 ring-red-500/20",
};

const labels: Record<ConfidenceLevel, string> = {
  high: "High Confidence",
  medium: "Medium Confidence",
  low: "Low Confidence",
};

export function ConfidenceBadge({
  confidence,
  note,
}: {
  confidence: ConfidenceLevel;
  note?: string;
}) {
  const inner = (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[confidence]}`}
      title={note}
    >
      {confidence === "low" && <span className="mr-0.5">⚠</span>}
      {labels[confidence]}
    </span>
  );
  return <span className="inline-block">{inner}</span>;
}
