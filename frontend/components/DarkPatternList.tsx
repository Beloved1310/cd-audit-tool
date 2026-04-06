import type { DarkPattern } from "@/types/audit";

const linkClass =
  "text-emerald-400 underline decoration-emerald-500/40 underline-offset-2 hover:text-emerald-300";

function titleizePatternType(slug: string): string {
  return slug
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

export function DarkPatternList({ patterns }: { patterns: DarkPattern[] }) {
  if (patterns.length === 0) {
    return (
      <p className="rounded-lg border border-emerald-500/25 bg-emerald-950/30 px-3 py-3 text-emerald-300">
        ✓ No dark patterns detected
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-red-500/30 bg-red-950/40 px-3 py-2 font-medium text-red-200">
        {patterns.length} Dark Pattern(s) Detected
      </div>
      <ul className="space-y-6">
        {patterns.map((p, idx) => (
          <li key={idx} className="border-b border-app-border pb-6 last:border-0">
            <h4 className="font-semibold text-zinc-100">
              {titleizePatternType(p.pattern_type)}
            </h4>
            <p className="mt-2 text-sm text-zinc-300">{p.description}</p>
            {p.evidence_text ? (
              <blockquote className="mt-3 border-l-4 border-emerald-600/40 bg-app-bg/60 py-2 pl-3 text-sm text-zinc-400">
                {p.evidence_text}
              </blockquote>
            ) : null}
            {p.page_url ? (
              <a
                href={p.page_url}
                className={`mt-2 inline-block text-xs ${linkClass}`}
                target="_blank"
                rel="noreferrer"
              >
                {p.page_url}
              </a>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
