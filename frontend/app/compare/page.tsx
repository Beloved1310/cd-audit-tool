"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ComparisonTable } from "@/components/ComparisonTable";
import { OutcomeCard } from "@/components/OutcomeCard";
import type { AuditReport, ComparisonReport } from "@/types/audit";
import { OUTCOME_DISPLAY_ORDER } from "@/types/audit";
import { fetchCachedCompareReport, type ApiErrorInfo } from "@/lib/api";

const linkClass =
  "text-emerald-400 underline decoration-emerald-500/50 underline-offset-2 hover:text-emerald-300";

function CompareInner() {
  const searchParams = useSearchParams();
  const urlA = searchParams.get("url_a")?.trim() ?? "";
  const urlB = searchParams.get("url_b")?.trim() ?? "";
  const hasPair = Boolean(urlA && urlB);
  const [sortedA, sortedB] = [urlA, urlB].sort();

  const [data, setData] = useState<ComparisonReport | null | undefined>(undefined);
  const [fetchError, setFetchError] = useState<ApiErrorInfo | null>(null);

  useEffect(() => {
    let cancelled = false;

    if (hasPair) {
      setFetchError(null);
      setData(undefined);

      const fromSession = sessionStorage.getItem("comparison_report");
      if (fromSession) {
        try {
          const parsed = JSON.parse(fromSession) as ComparisonReport;
          if (parsed.url_a === sortedA && parsed.url_b === sortedB) {
            setData(parsed);
            return () => {
              cancelled = true;
            };
          }
        } catch {
          /* fetch below */
        }
      }

      void (async () => {
        try {
          const report = await fetchCachedCompareReport(urlA, urlB);
          if (cancelled) return;
          sessionStorage.setItem("comparison_report", JSON.stringify(report));
          setData(report);
        } catch (e) {
          if (cancelled) return;
          if (e && typeof e === "object" && "message" in (e as object)) {
            setFetchError(e as ApiErrorInfo);
          } else {
            setFetchError({ message: "Request failed" });
          }
          setData(null);
        }
      })();

      return () => {
        cancelled = true;
      };
    }

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
  }, [hasPair, sortedA, sortedB, urlA, urlB]);

  if (data === undefined) {
    return <p className="text-app-muted">Loading…</p>;
  }

  if (fetchError) {
    return (
      <div className="space-y-3">
        <div
          className="rounded-xl border border-amber-500/30 bg-amber-950/40 p-4 text-sm text-amber-100"
          role="alert"
        >
          <p className="font-medium text-amber-200">Could not load comparison</p>
          <p className="mt-2 text-amber-100/90">{fetchError.message}</p>
          {fetchError.requestId ? (
            <p className="mt-2 text-xs text-amber-200/70">
              Request ID: {fetchError.requestId}
            </p>
          ) : null}
          <p className="mt-3 text-app-muted">
            Use{" "}
            <code className="rounded bg-app-bg px-1.5 py-0.5 text-xs text-zinc-300">
              {`/compare?url_a=…&url_b=…`}
            </code>{" "}
            after both URLs have been audited (for example via Compare on the home page).
          </p>
        </div>
        <Link href="/" className={linkClass}>
          Return home
        </Link>
      </div>
    );
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
