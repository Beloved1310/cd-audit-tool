"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { runAudit, runCompare } from "@/lib/api";
import type { ComparisonReport } from "@/types/audit";
import type { ApiErrorInfo } from "@/lib/api";

const LOADING_MESSAGES = [
  "Crawling website pages...",
  "Evaluating Products & Services...",
  "Evaluating Price & Value...",
  "Evaluating Consumer Understanding...",
  "Evaluating Consumer Support...",
  "Detecting dark patterns...",
  "Compiling report...",
];

const linkClass =
  "text-emerald-400 underline decoration-emerald-500/50 underline-offset-2 hover:text-emerald-300";

export default function HomePage() {
  const router = useRouter();
  const [tab, setTab] = useState<"single" | "compare">("single");
  const [url, setUrl] = useState("");
  const [urlA, setUrlA] = useState("");
  const [urlB, setUrlB] = useState("");
  const [loading, setLoading] = useState(false);
  const [msgIdx, setMsgIdx] = useState(0);
  const [error, setError] = useState<ApiErrorInfo | null>(null);
  useEffect(() => {
    if (!loading) return;
    const t = setInterval(() => {
      setMsgIdx((i) => (i + 1) % LOADING_MESSAGES.length);
    }, 3000);
    return () => clearInterval(t);
  }, [loading]);

  async function handleAudit() {
    setError(null);
    setLoading(true);
    setMsgIdx(0);
    try {
      const data = await runAudit(url.trim());
      const u = url.trim();
      sessionStorage.setItem("audit_last_url", u);
      const raw = JSON.stringify(data);
      const maxBytes = 200_000;
      if (raw.length <= maxBytes) {
        sessionStorage.setItem("audit_report", raw);
      } else {
        sessionStorage.removeItem("audit_report");
      }
      router.push(`/report?url=${encodeURIComponent(u)}`);
    } catch (e) {
      if (e && typeof e === "object" && "message" in (e as any)) {
        setError(e as ApiErrorInfo);
      } else {
        setError({ message: "Request failed" });
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleCompare() {
    setError(null);
    setLoading(true);
    setMsgIdx(0);
    try {
      const data: ComparisonReport = await runCompare(
        urlA.trim(),
        urlB.trim(),
      );
      sessionStorage.setItem("comparison_last", JSON.stringify({ urlA: urlA.trim(), urlB: urlB.trim() }));
      sessionStorage.setItem("comparison_report", JSON.stringify(data));
      const [a, b] = [urlA.trim(), urlB.trim()].sort();
      router.push(
        `/compare?url_a=${encodeURIComponent(a)}&url_b=${encodeURIComponent(b)}`,
      );
    } catch (e) {
      if (e && typeof e === "object" && "message" in (e as any)) {
        setError(e as ApiErrorInfo);
      } else {
        setError({ message: "Request failed" });
      }
    } finally {
      setLoading(false);
    }
  }

  const tabBtn = (active: boolean) =>
    `rounded-t-lg px-4 py-2.5 text-sm font-medium transition-colors ${
      active
        ? "bg-app-raised text-emerald-300 ring-1 ring-inset ring-app-border"
        : "text-app-muted hover:bg-app-surface/80 hover:text-zinc-200"
    }`;

  const inputClass =
    "mt-2 w-full rounded-lg border border-app-border bg-app-raised px-4 py-3.5 text-zinc-100 placeholder:text-zinc-500 shadow-inner shadow-black/20 outline-none transition focus:border-emerald-500/60 focus:ring-2 focus:ring-emerald-500/25";

  const primaryBtn =
    "mt-4 w-full rounded-lg bg-emerald-500 py-3.5 text-sm font-semibold text-app-bg shadow-lg shadow-emerald-900/30 transition hover:bg-emerald-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <main className="mx-auto max-w-lg px-4 py-12 sm:py-16">
      <div className="rounded-2xl border border-app-border bg-app-surface/80 p-6 shadow-xl shadow-black/30 backdrop-blur-sm sm:p-8">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-50">
          Consumer Duty Sludge Audit
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-app-muted">
          FCA Consumer Duty compliance checker for UK financial services websites
        </p>

        <div className="mt-8 flex gap-1 rounded-t-lg border-b border-app-border">
          <button type="button" onClick={() => setTab("single")} className={tabBtn(tab === "single")}>
            Single Audit
          </button>
          <button type="button" onClick={() => setTab("compare")} className={tabBtn(tab === "compare")}>
            Compare Two Sites
          </button>
        </div>

        <div className="rounded-b-2xl rounded-tr-2xl border border-t-0 border-app-border bg-app-raised/50 p-5 sm:p-6">
          {tab === "single" ? (
            <div>
              <label htmlFor="audit-url" className="text-sm font-medium text-zinc-300">
                Website URL
              </label>
              <input
                id="audit-url"
                type="url"
                className={inputClass}
                placeholder="https://www.example-firm.co.uk"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={loading}
                autoComplete="url"
              />
              <button
                type="button"
                className={primaryBtn}
                disabled={loading || !url.trim()}
                onClick={handleAudit}
              >
                {loading ? "Working…" : "Run Audit"}
              </button>
              {loading ? (
                <p className="mt-4 text-sm text-emerald-400/90" aria-live="polite">
                  {LOADING_MESSAGES[msgIdx]}
                </p>
              ) : null}
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label htmlFor="url-a" className="text-sm font-medium text-zinc-300">
                  Website A
                </label>
                <input
                  id="url-a"
                  type="url"
                  className={inputClass}
                  placeholder="https://..."
                  value={urlA}
                  onChange={(e) => setUrlA(e.target.value)}
                  disabled={loading}
                  autoComplete="url"
                />
              </div>
              <div>
                <label htmlFor="url-b" className="text-sm font-medium text-zinc-300">
                  Website B
                </label>
                <input
                  id="url-b"
                  type="url"
                  className={inputClass}
                  placeholder="https://..."
                  value={urlB}
                  onChange={(e) => setUrlB(e.target.value)}
                  disabled={loading}
                  autoComplete="url"
                />
              </div>
              <button
                type="button"
                className={primaryBtn}
                disabled={loading || !urlA.trim() || !urlB.trim()}
                onClick={handleCompare}
              >
                {loading ? "Working…" : "Compare Sites"}
              </button>
              {loading ? (
                <p className="mt-2 text-sm text-emerald-400/90" aria-live="polite">
                  {LOADING_MESSAGES[msgIdx]}
                </p>
              ) : null}
            </div>
          )}

          {error ? (
            <div
              className="mt-4 rounded-lg border border-red-500/25 bg-red-950/30 px-4 py-3 text-sm text-red-100"
              role="alert"
            >
              <p className="font-medium text-red-200">Request failed</p>
              <p className="mt-1 text-red-100/90">{error.message}</p>
              {error.requestId ? (
                <p className="mt-2 text-xs text-red-200/70">
                  Request ID: {error.requestId}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>

      <p className="mt-10 text-center text-sm text-app-muted">
        <Link href="/report" className={linkClass}>
          Open last report
        </Link>
        <span className="mx-2 text-zinc-600">·</span>
        <Link href="/compare" className={linkClass}>
          Open comparison
        </Link>
        <span className="mx-2 text-zinc-600">·</span>
        <Link href="/journey" className={linkClass}>
          User journey
        </Link>
      </p>
    </main>
  );
}
