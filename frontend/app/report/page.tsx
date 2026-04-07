"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { DarkPatternList } from "@/components/DarkPatternList";
import { FrictionMap } from "@/components/FrictionMap";
import { OutcomeCard } from "@/components/OutcomeCard";
import { RAGBadge } from "@/components/RAGBadge";
import {
  OUTCOME_DISPLAY_ORDER,
  type AuditReport,
  type AuditResponse,
  type OutcomeScore,
} from "@/types/audit";
import { fetchCachedReport, type ApiErrorInfo } from "@/lib/api";

const linkClass =
  "text-emerald-400 underline decoration-emerald-500/50 underline-offset-2 hover:text-emerald-300";

function titleizeGap(slug: string): string {
  return slug
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

function pageUrlsFromOutcomes(outcomes: OutcomeScore[]): string[] {
  return Array.from(
    new Set(
      outcomes.flatMap((o) =>
        o.criteria_scores.map((c) => c.page_url).filter(Boolean),
      ) as string[],
    ),
  );
}

function ReportInner() {
  const searchParams = useSearchParams();
  const urlParam = searchParams.get("url")?.trim() ?? "";

  const [raw, setRaw] = useState<AuditResponse | null | undefined>(undefined);
  const [fetchError, setFetchError] = useState<ApiErrorInfo | null>(null);

  useEffect(() => {
    let cancelled = false;

    if (urlParam) {
      setFetchError(null);
      setRaw(undefined);

      const fromSession = sessionStorage.getItem("audit_report");
      if (fromSession) {
        try {
          const parsed = JSON.parse(fromSession) as AuditResponse;
          if (parsed.url?.trim() === urlParam) {
            setRaw(parsed);
            return () => {
              cancelled = true;
            };
          }
        } catch {
          sessionStorage.removeItem("audit_report");
        }
      }

      void (async () => {
        try {
          const data = await fetchCachedReport(urlParam);
          if (cancelled) return;
          sessionStorage.setItem("audit_report", JSON.stringify(data));
          setRaw(data);
        } catch (e) {
          if (cancelled) return;
          if (e && typeof e === "object" && "message" in (e as object)) {
            setFetchError(e as ApiErrorInfo);
          } else {
            setFetchError({ message: "Request failed" });
          }
          setRaw(null);
        }
      })();

      return () => {
        cancelled = true;
      };
    }

    const s = sessionStorage.getItem("audit_report");
    if (!s) {
      setRaw(null);
      return;
    }
    try {
      setRaw(JSON.parse(s) as AuditResponse);
    } catch {
      setRaw(null);
    }
  }, [urlParam]);

  if (raw === undefined) {
    return <p className="text-app-muted">Loading…</p>;
  }

  if (fetchError) {
    return (
      <div className="space-y-3">
        <div
          className="rounded-xl border border-amber-500/30 bg-amber-950/40 p-4 text-sm text-amber-100"
          role="alert"
        >
          <p className="font-medium text-amber-200">Could not load report</p>
          <p className="mt-2 text-amber-100/90">{fetchError.message}</p>
          {fetchError.requestId ? (
            <p className="mt-2 text-xs text-amber-200/70">
              Request ID: {fetchError.requestId}
            </p>
          ) : null}
          <p className="mt-3 text-app-muted">
            Cached reports can be opened via{" "}
            <code className="rounded bg-app-bg px-1.5 py-0.5 text-xs text-zinc-300">
              /report?url=…
            </code>{" "}
            after running an audit at least once for that exact URL.
          </p>
        </div>
        <Link href="/" className={linkClass}>
          Return home
        </Link>
      </div>
    );
  }

  if (raw === null) {
    return (
      <p className="text-app-muted">
        No report found.{" "}
        <Link href="/" className={linkClass}>
          Return home
        </Link>
        .
      </p>
    );
  }

  if (raw.insufficient_data) {
    return (
      <div className="space-y-4">
        <div className="rounded-xl border border-amber-500/30 bg-amber-950/40 p-4 text-amber-100">
          <p className="font-medium text-amber-200">{raw.reason}</p>
          <p className="mt-2 text-sm text-app-muted">
            {raw.pages_crawled.length} pages crawled · {raw.total_words_analysed}{" "}
            words analysed
          </p>
        </div>
        <Link href="/" className={`text-sm ${linkClass}`}>
          ← Home
        </Link>
      </div>
    );
  }

  const report = raw as AuditReport;
  if (report.status !== "complete") {
    return (
      <div className="rounded-xl border border-amber-500/30 bg-amber-950/40 p-4 text-sm text-amber-100">
        <p>Audit status: {report.status}</p>
        <p className="mt-2">{report.insufficient_data_reason ?? ""}</p>
        <Link href="/" className={`mt-4 inline-block ${linkClass}`}>
          Home
        </Link>
      </div>
    );
  }

  const pageUrls = pageUrlsFromOutcomes(report.outcomes);

  const audited = new Date(report.audited_at).toLocaleString("en-GB", {
    timeZone: "UTC",
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });

  return (
    <div className="space-y-10">
      <header className="space-y-3">
        <Link href="/" className={`text-sm ${linkClass}`}>
          ← Home
        </Link>
        <h1
          className="break-words text-xl font-semibold text-zinc-50"
          title={report.url}
        >
          {report.url.length > 60 ? `${report.url.slice(0, 60)}…` : report.url}
        </h1>
        <p className="text-sm text-app-muted">{audited}</p>
        <div className="flex flex-wrap gap-2">
          <span className="rounded-full border border-app-border bg-app-raised px-3 py-1 text-xs text-app-muted">
            {report.pages_crawled.length} pages crawled
          </span>
          <span className="rounded-full border border-app-border bg-app-raised px-3 py-1 text-xs text-app-muted">
            {report.total_words_analysed} words analysed
          </span>
          {report.overall_rating != null && report.overall_score != null ? (
            <RAGBadge
              rating={report.overall_rating}
              score={report.overall_score}
            />
          ) : null}
        </div>
      </header>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {OUTCOME_DISPLAY_ORDER.map((name) => {
          const o = report.outcomes.find((x) => x.outcome_name === name);
          return o ? <OutcomeCard key={name} outcome={o} /> : null;
        })}
      </section>

      <section className="rounded-xl border border-app-border bg-app-surface/60 p-4 text-sm leading-relaxed text-app-muted">
        Scores cover all four Consumer Duty outcomes (PRIN 2A.2–2A.5), grounded in
        retrieved FCA material (FG22/5, PS22/9, and good practice publications in
        the index). Products & Services and Price & Value are based on public
        website evidence only and should be treated as partial where internal firm
        data is required. Overall score is the mean of the four outcome scores
        (0–10 each). Every finding includes verbatim evidence from the crawled
        website.
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-zinc-100">
          Page-Level Friction Map
        </h2>
        <FrictionMap pageUrls={pageUrls} outcomes={report.outcomes} />
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-zinc-100">Dark Patterns</h2>
        <DarkPatternList patterns={report.dark_patterns} />
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-zinc-100">
          Vulnerability Gaps
        </h2>
        {report.vulnerability_gaps.length === 0 ? (
          <p className="rounded-lg border border-emerald-500/25 bg-emerald-950/30 px-3 py-2 text-emerald-300">
            ✓ No vulnerability gaps detected
          </p>
        ) : (
          <ul className="space-y-4">
            {report.vulnerability_gaps.map((g, i) => (
              <li key={i} className="rounded-lg border border-app-border bg-app-raised/50 p-4">
                <h3 className="font-semibold text-zinc-100">
                  {titleizeGap(g.gap_type)}
                </h3>
                <p className="mt-1 text-sm text-app-muted">{g.description}</p>
                <span className="mt-2 inline-block rounded bg-app-bg px-2 py-0.5 text-xs text-emerald-200/90">
                  FCA: {g.fca_reference}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <footer>
        <button
          type="button"
          className="rounded-lg border border-app-border bg-app-raised px-4 py-2.5 text-sm font-medium text-zinc-200 transition hover:border-emerald-500/40 hover:bg-app-surface hover:text-emerald-200"
          onClick={() => window.print()}
        >
          Download Report
        </button>
      </footer>
    </div>
  );
}

export default function ReportPage() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <Suspense fallback={<p className="text-app-muted">Loading…</p>}>
        <ReportInner />
      </Suspense>
    </main>
  );
}
