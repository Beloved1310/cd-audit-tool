import {
  OUTCOME_DISPLAY_ORDER,
  type AuditReport,
  type ComparisonReport,
  type InsufficientDataReport,
  type OutcomeScore,
} from "@/types/audit";
import { RAGBadge } from "./RAGBadge";

function getOutcome(
  report: AuditReport | InsufficientDataReport,
  name: string,
): OutcomeScore | null {
  if (report.insufficient_data) return null;
  return report.outcomes.find((o) => o.outcome_name === name) ?? null;
}

function truncate(u: string, n: number) {
  return u.length <= n ? u : `${u.slice(0, n)}…`;
}

/** Mean of outcome scores; prefers API overall_score when present (four-outcome audits). */
function overallMetric(report: AuditReport): number {
  if (report.overall_score != null) {
    return report.overall_score;
  }
  const n = report.outcomes.length;
  if (n === 0) return 0;
  return Math.round(report.outcomes.reduce((s, o) => s + o.score, 0) / n);
}

export function ComparisonTable({ comparison }: { comparison: ComparisonReport }) {
  const { report_a: ra, report_b: rb, url_a, url_b, both_sufficient } = comparison;
  const warn = ra.insufficient_data === true || rb.insufficient_data === true;

  const da = ra.insufficient_data ? null : ra;
  const db = rb.insufficient_data ? null : rb;

  const darkA = da?.dark_patterns.length ?? "—";
  const darkB = db?.dark_patterns.length ?? "—";
  const vulnA = da?.vulnerability_gaps.length ?? "—";
  const vulnB = db?.vulnerability_gaps.length ?? "—";

  const darkWinner =
    da && db
      ? da.dark_patterns.length < db.dark_patterns.length
        ? "a"
        : db.dark_patterns.length < da.dark_patterns.length
          ? "b"
          : null
      : null;

  const vulnWinner =
    da && db
      ? da.vulnerability_gaps.length < db.vulnerability_gaps.length
        ? "a"
        : db.vulnerability_gaps.length < da.vulnerability_gaps.length
          ? "b"
          : null
      : null;

  let overallWinner: "a" | "b" | null = null;
  let scoreA = 0;
  let scoreB = 0;
  if (both_sufficient && da && db) {
    scoreA = overallMetric(da);
    scoreB = overallMetric(db);
    if (scoreA > scoreB) overallWinner = "a";
    else if (scoreB > scoreA) overallWinner = "b";
  }

  const cell = "border-b border-app-border p-3";
  const cellHead = `${cell} text-zinc-300`;
  const winnerBg = "bg-emerald-950/50 ring-1 ring-inset ring-emerald-500/25";

  return (
    <div className="space-y-4">
      {warn ? (
        <div className="rounded-lg border border-amber-500/35 bg-amber-950/40 px-4 py-3 text-sm text-amber-100">
          One or both audits could not be completed
        </div>
      ) : null}

      <div className="overflow-x-auto rounded-xl border border-app-border bg-app-surface/50 shadow-lg shadow-black/20">
        <table className="w-full min-w-[360px] border-collapse text-sm">
          <thead>
            <tr className="bg-app-raised/80">
              <th className={`${cell} border-app-border font-medium text-app-muted`} />
              <th
                className={`${cell} border-l border-app-border font-medium text-zinc-100`}
              >
                {truncate(url_a, 40)}
              </th>
              <th
                className={`${cell} border-l border-app-border font-medium text-zinc-100`}
              >
                {truncate(url_b, 40)}
              </th>
            </tr>
          </thead>
          <tbody>
            {OUTCOME_DISPLAY_ORDER.map((name) => {
              const oA = getOutcome(ra, name);
              const oB = getOutcome(rb, name);
              return (
                <tr key={name}>
                  <td className={cellHead}>{name}</td>
                  <td className={`${cell} border-l border-app-border`}>
                    {oA ? (
                      <RAGBadge rating={oA.rating} score={oA.score} />
                    ) : (
                      <span className="text-zinc-500">N/A</span>
                    )}
                  </td>
                  <td className={`${cell} border-l border-app-border`}>
                    {oB ? (
                      <RAGBadge rating={oB.rating} score={oB.score} />
                    ) : (
                      <span className="text-zinc-500">N/A</span>
                    )}
                  </td>
                </tr>
              );
            })}
            <tr>
              <td className={cellHead}>Dark Patterns</td>
              <td
                className={`${cell} border-l border-app-border ${
                  darkWinner === "a" ? winnerBg : ""
                }`}
              >
                {darkA}
              </td>
              <td
                className={`${cell} border-l border-app-border ${
                  darkWinner === "b" ? winnerBg : ""
                }`}
              >
                {darkB}
              </td>
            </tr>
            <tr>
              <td className={cellHead}>Vulnerability Gaps</td>
              <td
                className={`${cell} border-l border-app-border ${
                  vulnWinner === "a" ? winnerBg : ""
                }`}
              >
                {vulnA}
              </td>
              <td
                className={`${cell} border-l border-app-border ${
                  vulnWinner === "b" ? winnerBg : ""
                }`}
              >
                {vulnB}
              </td>
            </tr>
            <tr>
              <td className="p-3 font-medium text-zinc-200">Overall (0–10)</td>
              <td
                className={`border-l border-app-border p-3 ${
                  overallWinner === "a" ? winnerBg : ""
                }`}
              >
                {!both_sufficient || !da ? (
                  <span className="text-zinc-500">Incomplete</span>
                ) : (
                  <div>
                    <div className="font-medium text-emerald-300">{scoreA}</div>
                    {overallWinner === "a" ? (
                      <div className="text-xs font-semibold text-emerald-400/90">
                        Winner
                      </div>
                    ) : null}
                  </div>
                )}
              </td>
              <td
                className={`border-l border-app-border p-3 ${
                  overallWinner === "b" ? winnerBg : ""
                }`}
              >
                {!both_sufficient || !db ? (
                  <span className="text-zinc-500">Incomplete</span>
                ) : (
                  <div>
                    <div className="font-medium text-emerald-300">{scoreB}</div>
                    {overallWinner === "b" ? (
                      <div className="text-xs font-semibold text-emerald-400/90">
                        Winner
                      </div>
                    ) : null}
                  </div>
                )}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
