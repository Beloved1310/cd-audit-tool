"use client";

import Link from "next/link";
import { useState } from "react";
import { runJourney } from "@/lib/api";
import type { JourneyReport, JourneyStepInput } from "@/types/journey";

const linkClass =
  "text-emerald-400 underline decoration-emerald-500/50 underline-offset-2 hover:text-emerald-300";

const inputClass =
  "w-full rounded-lg border border-app-border bg-app-raised px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 outline-none focus:border-emerald-500/60 focus:ring-2 focus:ring-emerald-500/25";

const MIN_STEPS = 2;
const MAX_STEPS = 10;

function emptyStep(): JourneyStepInput {
  return { label: "", url: "" };
}

export default function JourneyPage() {
  const [steps, setSteps] = useState<JourneyStepInput[]>([
    emptyStep(),
    emptyStep(),
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<JourneyReport | null>(null);

  function updateStep(i: number, patch: Partial<JourneyStepInput>) {
    setSteps((prev) => {
      const next = [...prev];
      next[i] = { ...next[i], ...patch };
      return next;
    });
  }

  function addStep() {
    setSteps((prev) =>
      prev.length >= MAX_STEPS ? prev : [...prev, emptyStep()],
    );
  }

  function removeStep(i: number) {
    setSteps((prev) =>
      prev.length <= MIN_STEPS ? prev : prev.filter((_, j) => j !== i),
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = steps.map((s) => ({
      label: s.label.trim(),
      url: s.url.trim(),
    }));
    const bad = trimmed.find((s) => !s.url);
    if (bad) {
      setError("Every step needs a URL.");
      return;
    }
    setLoading(true);
    setReport(null);
    try {
      const data = await runJourney(trimmed);
      setReport(data);
      sessionStorage.setItem("journey_report", JSON.stringify(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  const when = report
    ? new Date(report.generated_at).toLocaleString("en-GB", {
        timeZone: "UTC",
        day: "numeric",
        month: "long",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <Link href="/" className={`text-sm ${linkClass}`}>
        ← Home
      </Link>

      <h1 className="mt-4 text-2xl font-semibold tracking-tight text-zinc-50">
        Journey mode
      </h1>
      <p className="mt-2 text-sm leading-relaxed text-app-muted">
        Define a path (e.g. homepage → product → checkout → support). Each step is
        fetched individually and analysed for friction signals and dark patterns
        with verbatim evidence — complementary to a full-site audit.
      </p>

      <form
        onSubmit={handleSubmit}
        className="mt-8 rounded-2xl border border-app-border bg-app-surface/80 p-6 shadow-xl shadow-black/30"
      >
        <ol className="space-y-4">
          {steps.map((s, i) => (
            <li
              key={i}
              className="rounded-xl border border-app-border bg-app-raised/50 p-4"
            >
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-emerald-400/90">
                  Step {i + 1}
                </span>
                {steps.length > MIN_STEPS ? (
                  <button
                    type="button"
                    onClick={() => removeStep(i)}
                    className="text-xs text-red-400 hover:text-red-300"
                  >
                    Remove
                  </button>
                ) : null}
              </div>
              <label className="block text-xs font-medium text-zinc-400">
                Label (optional)
              </label>
              <input
                type="text"
                className={`${inputClass} mt-1`}
                placeholder="e.g. Product page"
                value={s.label}
                onChange={(e) => updateStep(i, { label: e.target.value })}
                disabled={loading}
              />
              <label className="mt-3 block text-xs font-medium text-zinc-400">
                URL
              </label>
              <input
                type="url"
                required
                className={`${inputClass} mt-1`}
                placeholder="https://…"
                value={s.url}
                onChange={(e) => updateStep(i, { url: e.target.value })}
                disabled={loading}
                autoComplete="off"
              />
            </li>
          ))}
        </ol>

        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={addStep}
            disabled={loading || steps.length >= MAX_STEPS}
            className="rounded-lg border border-app-border px-4 py-2 text-sm text-zinc-300 hover:bg-app-surface disabled:opacity-50"
          >
            Add step
          </button>
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-emerald-500 px-5 py-2 text-sm font-semibold text-app-bg shadow-lg shadow-emerald-900/30 hover:bg-emerald-400 disabled:opacity-50"
          >
            {loading ? "Analysing journey…" : "Run journey audit"}
          </button>
        </div>
        {error ? (
          <p className="mt-4 text-sm text-red-400" role="alert">
            {error}
          </p>
        ) : null}
      </form>

      {report && when ? (
        <section className="mt-12 space-y-8">
          <h2 className="text-lg font-semibold text-zinc-100">Results</h2>
          <p className="text-sm text-app-muted">{when} UTC</p>

          <ol className="relative space-y-0 border-l border-app-border pl-6">
            {report.steps.map((st, idx) => (
              <li key={`${st.url}-${idx}`} className="mb-10 last:mb-0">
                <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full bg-emerald-500 ring-4 ring-app-bg" />
                <div className="rounded-xl border border-app-border bg-app-surface/60 p-5">
                  <h3 className="font-semibold text-zinc-100">
                    {st.label || `Step ${st.step_index + 1}`}
                  </h3>
                  <a
                    href={st.url}
                    className={`mt-1 block break-all text-sm ${linkClass}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {st.url}
                  </a>
                  {st.fetch_error ? (
                    <p className="mt-3 rounded-lg border border-red-500/30 bg-red-950/40 px-3 py-2 text-sm text-red-200">
                      {st.fetch_error}
                    </p>
                  ) : (
                    <>
                      <p className="mt-2 text-xs text-app-muted">
                        {st.page_title ? `${st.page_title} · ` : null}
                        {st.word_count} words
                      </p>
                      <p className="mt-4 text-sm leading-relaxed text-zinc-300">
                        {st.step_summary}
                      </p>
                      {st.friction_flags.length > 0 ? (
                        <div className="mt-4">
                          <p className="text-xs font-medium uppercase tracking-wide text-app-muted">
                            Friction signals
                          </p>
                          <ul className="mt-2 flex flex-wrap gap-2">
                            {st.friction_flags.map((f) => (
                              <li
                                key={f}
                                className="rounded-full bg-amber-950/60 px-2.5 py-0.5 text-xs text-amber-200 ring-1 ring-amber-500/30"
                              >
                                {f.replace(/_/g, " ")}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                      {st.friction_evidence_quotes.length > 0 ? (
                        <div className="mt-4">
                          <p className="text-xs font-medium uppercase tracking-wide text-app-muted">
                            Evidence quotes
                          </p>
                          <ul className="mt-2 space-y-2">
                            {st.friction_evidence_quotes.map((q, qi) => (
                              <li
                                key={qi}
                                className="border-l-2 border-emerald-600/50 pl-3 text-sm italic text-zinc-400"
                              >
                                <q className="text-zinc-300 not-italic">{q}</q>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                      {st.dark_patterns.length > 0 ? (
                        <div className="mt-4">
                          <p className="text-xs font-medium uppercase tracking-wide text-app-muted">
                            Dark patterns
                          </p>
                          <ul className="mt-2 space-y-3">
                            {st.dark_patterns.map((d, di) => (
                              <li
                                key={di}
                                className="rounded-lg border border-red-500/20 bg-red-950/20 p-3 text-sm"
                              >
                                <span className="font-medium text-red-200">
                                  {d.pattern_type.replace(/_/g, " ")}
                                </span>
                                <p className="mt-1 text-zinc-300">{d.description}</p>
                                <blockquote className="mt-2 border-l-2 border-red-500/40 pl-2 text-xs text-zinc-500">
                                  {d.evidence_text}
                                </blockquote>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <p className="mt-10 text-center text-sm text-app-muted">
        <Link href="/" className={linkClass}>
          Full site audit
        </Link>
      </p>
    </main>
  );
}
