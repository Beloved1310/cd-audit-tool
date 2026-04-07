import type { Finding, OutcomeScore } from "@/types/audit";
import { useEffect, useMemo, useState } from "react";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { CriteriaBreakdown } from "./CriteriaBreakdown";
import { RAGBadge } from "./RAGBadge";
import { fetchFindingsPage, type ApiErrorInfo } from "@/lib/api";

const linkClass =
  "text-emerald-400 underline decoration-emerald-500/40 underline-offset-2 hover:text-emerald-300";

function severityClass(s: Finding["severity"]) {
  if (s === "critical") return "bg-red-950/80 text-red-300 ring-1 ring-red-500/30";
  if (s === "moderate")
    return "bg-amber-950/60 text-amber-200 ring-1 ring-amber-500/30";
  return "bg-sky-950/60 text-sky-200 ring-1 ring-sky-500/30";
}

function isScoringFailure(outcome: OutcomeScore): boolean {
  const s = outcome.summary ?? "";
  return (
    outcome.criteria_scores.length === 0 &&
    (s.includes("could not") ||
      s.includes("rate limit") ||
      s.includes("exceeded") ||
      s.includes("did not complete"))
  );
}

export function OutcomeCard({ outcome }: { outcome: OutcomeScore }) {
  const recs = outcome.recommendations?.filter(Boolean) ?? [];
  const failed = isScoringFailure(outcome);
  const partial =
    outcome.assessment_scope === "public_website_only" &&
    (outcome.outcome_name === "Products & Services" ||
      outcome.outcome_name === "Price & Value");

  const reportUrl =
    typeof window !== "undefined"
      ? new URLSearchParams(window.location.search).get("url")?.trim() ?? ""
      : "";

  const totalFindings = outcome.findings.length;
  const pageSize = 5;
  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(totalFindings / pageSize)),
    [totalFindings],
  );
  const [findingsOpen, setFindingsOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<ApiErrorInfo | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!findingsOpen) return;
    if (!reportUrl) return;
    if (totalFindings <= pageSize) {
      setItems(outcome.findings);
      return;
    }
    void (async () => {
      setLoading(true);
      setErr(null);
      try {
        const data = await fetchFindingsPage({
          url: reportUrl,
          outcome: outcome.outcome_name,
          page,
          page_size: pageSize,
        });
        if (cancelled) return;
        setItems(data.items);
      } catch (e) {
        if (cancelled) return;
        setErr(e as ApiErrorInfo);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [findingsOpen, page, reportUrl, outcome.outcome_name, totalFindings, outcome.findings]);

  return (
    <article className="rounded-xl border border-app-border bg-app-surface/80 p-5 shadow-lg shadow-black/20 backdrop-blur-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-lg font-semibold text-zinc-50">{outcome.outcome_name}</h3>
        {partial ? (
          <span className="rounded-md border border-sky-500/20 bg-sky-950/40 px-2 py-1 text-xs font-medium text-sky-200">
            Public evidence only (partial)
          </span>
        ) : null}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3 sm:items-end">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-app-muted">
            RAG band
          </div>
          <div className="mt-1">
            <RAGBadge rating={outcome.rating} />
          </div>
        </div>
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-app-muted">
            Score (0–10)
          </div>
          <div className="mt-1 text-2xl font-semibold tabular-nums text-emerald-300">
            {outcome.score}
            <span className="text-base font-normal text-app-muted">/10</span>
          </div>
        </div>
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-app-muted">
            Confidence
          </div>
          <div className="mt-1">
            <ConfidenceBadge
              confidence={outcome.confidence}
              note={outcome.confidence_note}
            />
          </div>
        </div>
      </div>

      {partial && outcome.scope_note ? (
        <p className="mt-3 text-xs leading-relaxed text-sky-200/80">
          {outcome.scope_note}
        </p>
      ) : null}

      {failed ? (
        <div
          className="mt-4 rounded-lg border border-amber-500/35 bg-amber-950/35 px-4 py-3 text-sm text-amber-100"
          role="status"
        >
          <p className="font-medium text-amber-200">Scoring unavailable</p>
          <p className="mt-1 leading-relaxed text-amber-100/90">{outcome.summary}</p>
        </div>
      ) : (
        <p className="mt-4 text-sm leading-relaxed text-zinc-300">{outcome.summary}</p>
      )}

      <details open className="mt-4">
        <summary className="cursor-pointer list-none text-sm font-medium text-emerald-400/90 marker:content-none [&::-webkit-details-marker]:hidden">
          Scoring Breakdown
        </summary>
        <div className="mt-3">
          <CriteriaBreakdown criteria={outcome.criteria_scores} />
        </div>
      </details>

      {totalFindings > 0 ? (
        <details className="mt-4" onToggle={(e) => setFindingsOpen((e.target as HTMLDetailsElement).open)}>
          <summary className="cursor-pointer list-none text-sm font-medium text-emerald-400/90 marker:content-none [&::-webkit-details-marker]:hidden">
            Findings ({totalFindings})
          </summary>
          {loading ? (
            <p className="mt-3 text-sm text-app-muted" aria-live="polite">
              Loading findings…
            </p>
          ) : null}
          {err ? (
            <p className="mt-3 text-sm text-red-300" role="alert">
              {err.message || "Could not load findings"}
            </p>
          ) : null}
          <ul className="mt-3 space-y-4">
            {(items.length > 0 ? items : outcome.findings.slice(0, pageSize)).map((f, i) => (
              <li
                key={i}
                className="border-b border-app-border pb-4 last:border-0"
              >
                <span
                  className={`inline-block rounded-md px-2 py-0.5 text-xs font-medium ${severityClass(f.severity)}`}
                >
                  {f.severity}
                </span>
                <p className="mt-2 text-sm text-zinc-200">{f.description}</p>
                <blockquote className="mt-2 border-l-4 border-emerald-600/50 bg-app-bg/80 py-2 pl-3 text-sm text-zinc-300">
                  {f.evidence_text}
                </blockquote>
                <span className="mt-2 inline-block rounded bg-app-bg px-2 py-0.5 text-xs text-emerald-200/80">
                  FCA: {f.fca_reference}
                </span>
                {f.page_url ? (
                  <a
                    href={f.page_url}
                    className={`mt-1 block text-xs ${linkClass}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {f.page_url}
                  </a>
                ) : null}
              </li>
            ))}
          </ul>
          {totalFindings > pageSize ? (
            <div className="mt-3 flex items-center justify-between gap-3 text-xs text-app-muted">
              <button
                type="button"
                className="rounded-md border border-app-border bg-app-raised px-3 py-1.5 text-zinc-200 disabled:opacity-50"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1 || loading}
              >
                Prev
              </button>
              <span>
                Page {page} / {totalPages}
              </span>
              <button
                type="button"
                className="rounded-md border border-app-border bg-app-raised px-3 py-1.5 text-zinc-200 disabled:opacity-50"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages || loading}
              >
                Next
              </button>
            </div>
          ) : null}
        </details>
      ) : null}

      {recs.length > 0 ? (
        <div className="mt-4 rounded-lg border border-emerald-500/20 bg-emerald-950/20 p-4">
          <h4 className="text-sm font-medium text-emerald-200">Recommendations</h4>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm leading-relaxed text-zinc-300">
            {recs.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ol>
        </div>
      ) : null}
    </article>
  );
}
