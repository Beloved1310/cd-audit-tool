import type { OutcomeScore } from "@/types/audit";

type Cell = "red" | "amber" | "green" | "none";

function cellForPage(outcome: OutcomeScore, pageUrl: string): Cell {
  let hasGreen = false;
  let hasAmber = false;
  let hasRed = false;
  for (const c of outcome.criteria_scores) {
    if (c.page_url !== pageUrl) continue;
    if (c.met) hasGreen = true;
    else if (c.awarded_points > 0) hasAmber = true;
    else hasRed = true;
  }
  if (hasGreen) return "green";
  if (hasAmber) return "amber";
  if (hasRed) return "red";
  return "none";
}

function CellIcon({ cell }: { cell: Cell }) {
  if (cell === "none") return <span className="text-zinc-600">—</span>;
  if (cell === "green") return <span title="Passed">✅</span>;
  if (cell === "amber") return <span title="Partial">⚠️</span>;
  return <span title="Failed">❌</span>;
}

export function FrictionMap({
  pageUrls,
  outcomes,
}: {
  pageUrls: string[];
  outcomes: OutcomeScore[];
}) {
  return (
    <div className="space-y-3 rounded-xl border border-app-border bg-app-surface/40 p-4">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[400px] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-app-border">
              <th className="py-2 pr-2 font-medium text-app-muted" />
              {outcomes.map((o) => (
                <th
                  key={o.outcome_name}
                  className="px-2 py-2 font-medium text-zinc-200"
                >
                  {o.outcome_name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageUrls.map((url) => (
              <tr key={url} className="border-b border-app-border/70">
                <td
                  className="max-w-[220px] truncate py-2 pr-2 font-mono text-xs text-zinc-400"
                  title={url}
                >
                  {url.length > 40 ? `…${url.slice(-40)}` : url}
                </td>
                {outcomes.map((o) => (
                  <td key={o.outcome_name} className="px-2 py-2 text-center">
                    <CellIcon cell={cellForPage(o, url)} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-app-muted">
        <span className="mr-3">❌ Failed</span>
        <span className="mr-3">⚠️ Partial</span>
        <span className="mr-3">✅ Passed</span>
        <span>— Not assessed</span>
      </p>
    </div>
  );
}
