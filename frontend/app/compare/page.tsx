"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { ComparisonTable } from "@/components/ComparisonTable";
import { OutcomeCard } from "@/components/OutcomeCard";
import type { AuditReport, ComparisonReport } from "@/types/audit";
import { OUTCOME_DISPLAY_ORDER } from "@/types/audit";

const linkClass =
  "text-emerald-400 underline decoration-emerald-500/50 underline-offset-2 hover:text-emerald-300";

function CompareInner() {
  const [data, setData] = useState<ComparisonReport | null | undefined>(undefined);

  useEffect(() => {
    const s = sessionStorage.getItem("comparison_report");
    if (!s) {
      setData(null);
      return;
    }
    try {
      setData(JSON.parse(s) as ComparisonReport);
    } catch {
      setData(null);
    }
  }, []);

  if (data === undefined) {
    return <p className="text-app-muted">Loading…</p>;
  }

  if (data === null) {
    return (
      <p className="text-app-muted">
        No comparison found.{" "}
        <Link href="/" className={linkClass}>
          Return home
        </Link>
        .
      </p>
    );
  }

  const comparison = data;
  const { report_a, report_b, url_a, url_b, generated_at_iso, both_sufficient } =
    comparison;

  const when = new Date(generated_at_iso).toLocaleString("en-GB", {
    timeZone: "UTC",
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  const ra = report_a.insufficient_data ? null : (report_a as AuditReport);
  const rb = report_b.insufficient_data ? null : (report_b as AuditReport);

  return (
    <div className="space-y-10">
      <header>
        <Link href="/" className={`text-sm ${linkClass}`}>
          ← Home
        </Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-50">
          Comparison Report
        </h1>
        <p className="mt-1 break-all text-sm text-app-muted">{url_a}</p>
        <p className="break-all text-sm text-app-muted">{url_b}</p>
        <p className="mt-2 text-sm text-zinc-500">{when}</p>
      </header>

      <ComparisonTable comparison={comparison} />

      {both_sufficient && ra && rb ? (
        <>
          {OUTCOME_DISPLAY_ORDER.map((title) => {
            const a = ra.outcomes.find((o) => o.outcome_name === title) ?? null;
            const b = rb.outcomes.find((o) => o.outcome_name === title) ?? null;
            if (!a && !b) return null;
            return (
              <div key={title}>
                <h2 className="mb-4 text-lg font-semibold text-zinc-100">{title}</h2>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  {a ? <OutcomeCard outcome={a} /> : null}
                  {b ? <OutcomeCard outcome={b} /> : null}
                </div>
              </div>
            );
          })}
        </>
      ) : null}

      <div className="space-y-2 text-sm text-app-muted">
        <p>
          Dark Patterns: {ra?.dark_patterns.length ?? "—"} vs{" "}
          {rb?.dark_patterns.length ?? "—"}
        </p>
        <p>
          Vulnerability Gaps: {ra?.vulnerability_gaps.length ?? "—"} vs{" "}
          {rb?.vulnerability_gaps.length ?? "—"}
        </p>
      </div>
    </div>
  );
}

export default function ComparePage() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <Suspense fallback={<p className="text-app-muted">Loading…</p>}>
        <CompareInner />
      </Suspense>
    </main>
  );
}
