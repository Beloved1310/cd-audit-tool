import type { RAGRating } from "@/types/audit";

const styles: Record<RAGRating, string> = {
  RED: "bg-red-600 text-white ring-1 ring-red-500/50",
  AMBER: "bg-amber-500 text-zinc-950 ring-1 ring-amber-400/60",
  GREEN: "bg-emerald-500 text-zinc-950 ring-1 ring-emerald-400/50",
};

/** Coloured RAG pill; optional numeric score shown beside it (not inside the pill). */
export function RAGBadge({ rating, score }: { rating: RAGRating; score?: number }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className={`rounded-full px-2.5 py-1 text-xs font-semibold ${styles[rating]}`}
      >
        {rating}
      </span>
      {score !== undefined ? (
        <span className="text-sm font-semibold tabular-nums text-emerald-300">
          {score}/10
        </span>
      ) : null}
    </span>
  );
}
