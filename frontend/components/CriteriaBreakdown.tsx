import type { CriterionScore } from "@/types/audit";
import { Fragment } from "react";

const linkClass =
  "text-emerald-400 underline decoration-emerald-500/40 underline-offset-2 hover:text-emerald-300";

export function CriteriaBreakdown({ criteria }: { criteria: CriterionScore[] }) {
  if (criteria.length === 0) {
    return (
      <p className="py-4 text-sm text-app-muted">
        No checklist rows were returned. This usually means automated scoring did
        not finish for this outcome.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-app-border">
            <th className="py-2 pr-3 font-medium text-zinc-300">Criterion</th>
            <th className="py-2 pr-3 font-medium text-zinc-300">Points</th>
            <th className="py-2 pr-3 font-medium text-zinc-300">Progress</th>
            <th className="py-2 font-medium text-zinc-300">Met</th>
          </tr>
        </thead>
        <tbody>
          {criteria.map((c, idx) => {
            const pct =
              c.max_points > 0
                ? Math.min(100, (c.awarded_points / c.max_points) * 100)
                : 0;
            let barBg = "bg-red-500";
            if (c.met) barBg = "bg-emerald-400";
            else if (c.awarded_points > 0) barBg = "bg-amber-400";

            return (
              <Fragment key={`${c.criterion_id}-${idx}`}>
                <tr className="border-b border-app-border/60 align-top">
                  <td className="py-3 pr-3 text-zinc-100">{c.criterion_name}</td>
                  <td className="py-3 pr-3 whitespace-nowrap tabular-nums text-zinc-400">
                    {c.awarded_points} / {c.max_points}
                  </td>
                  <td className="py-3 pr-3">
                    <div className="h-2 w-full max-w-[140px] overflow-hidden rounded bg-zinc-800">
                      <div
                        className={`h-full ${barBg}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </td>
                  <td className="py-3">
                    {c.met ? (
                      <span className="text-emerald-400" title="Met">
                        ✓
                      </span>
                    ) : (
                      <span className="text-red-400" title="Not met">
                        ✗
                      </span>
                    )}
                  </td>
                </tr>
                {!c.met && (c.evidence || c.page_url) ? (
                  <tr>
                    <td colSpan={4} className="pb-4 pt-0">
                      {c.evidence ? (
                        <blockquote className="border-l-4 border-emerald-600/40 bg-app-bg/60 pl-3 text-sm italic text-zinc-400">
                          {c.evidence}
                        </blockquote>
                      ) : null}
                      {c.page_url ? (
                        <a
                          href={c.page_url}
                          className={`mt-1 block text-xs ${linkClass}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {c.page_url}
                        </a>
                      ) : null}
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
