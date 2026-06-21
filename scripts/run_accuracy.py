"""CLI: run the scoring pipeline against frozen crawls and compare to expert labels.

Usage:
    # Run all sites that have both a frozen crawl and a ground truth label:
    python scripts/run_accuracy.py

    # Run a single site with accuracy gates (exit 1 if thresholds not met):
    python scripts/run_accuracy.py --site example_retail_bank \\
        --max-mae 1.5 --min-rating-agreement 75

    # Override directories:
    python scripts/run_accuracy.py \\
        --frozen evaluation/frozen_crawls \\
        --labels evaluation/ground_truth

Requires: GROQ_API_KEY set in environment or .env (live LLM calls are made for each site).

See evaluation/README.md for freeze-at-label-time workflow and _template.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.evaluation.accuracy import (
    check_accuracy_gates,
    compare_to_ground_truth,
    format_accuracy_report,
    summarise_accuracy,
)
from backend.evaluation.frozen_crawl import load_frozen_crawl, run_pipeline_from_frozen
from backend.evaluation.ground_truth import (
    is_synthetic_expert_label,
    load_ground_truth,
    validate_label_matches_frozen,
)
from backend.ingestion.fca_loader import load_fca_docs, get_retriever
from backend.config import get_settings
from backend.schemas.audit import AuditReport


def _label_json_files(labels_dir: Path) -> dict[str, Path]:
    return {
        p.stem: p
        for p in sorted(labels_dir.glob("*.json"))
        if not p.name.startswith("_")
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score accuracy: pipeline vs expert labels.")
    parser.add_argument(
        "--frozen",
        default="evaluation/frozen_crawls",
        help="Directory of frozen crawl JSON files.",
    )
    parser.add_argument(
        "--labels",
        default="evaluation/ground_truth",
        help="Directory of ground truth label JSON files.",
    )
    parser.add_argument(
        "--site",
        default="",
        help="Run only this site_id (filename stem). Omit to run all matched pairs.",
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="Optional path to write a JSON summary file.",
    )
    parser.add_argument(
        "--max-mae",
        type=float,
        default=None,
        help="Fail (exit 1) if overall MAE exceeds this value (0–10 scale).",
    )
    parser.add_argument(
        "--min-rating-agreement",
        type=float,
        default=None,
        help="Fail (exit 1) if rating agreement %% is below this value.",
    )
    parser.add_argument(
        "--require-expert-labels",
        action="store_true",
        help="Fail if any matched label has synthetic/placeholder labelled_by.",
    )
    parser.add_argument(
        "--require-frozen-at",
        action="store_true",
        help="Fail if label files omit frozen_at (recommended for expert benchmarks).",
    )
    parser.add_argument(
        "--skip-frozen-validation",
        action="store_true",
        help="Do not check label site_id/url/frozen_at against frozen crawl metadata.",
    )
    args = parser.parse_args()

    frozen_dir = Path(args.frozen)
    labels_dir = Path(args.labels)

    frozen_files = {p.stem: p for p in sorted(frozen_dir.glob("*.json"))}
    label_files = _label_json_files(labels_dir)
    matched = sorted(set(frozen_files) & set(label_files))

    if args.site:
        if args.site not in matched:
            print(f"ERROR: site_id '{args.site}' not found in both frozen_crawls/ and ground_truth/")
            sys.exit(1)
        matched = [args.site]

    if not matched:
        print("No matched (frozen crawl + ground truth label) pairs found.")
        print(f"  Frozen crawls: {list(frozen_files)}")
        print(f"  Labels:        {list(label_files)}")
        sys.exit(1)

    print(f"Running accuracy benchmark for {len(matched)} site(s): {matched}\n")

    validation_errors: list[str] = []
    for site_id in matched:
        frozen = json.loads(frozen_files[site_id].read_text(encoding="utf-8"))
        label = load_ground_truth(label_files[site_id])
        if args.require_expert_labels and is_synthetic_expert_label(label):
            validation_errors.append(
                f"[{site_id}] labelled_by={label.labelled_by!r} is not an expert label "
                "(use --require-expert-labels only with real reviewer names)",
            )
        if not args.skip_frozen_validation:
            validation_errors.extend(
                f"[{site_id}] {msg}"
                for msg in validate_label_matches_frozen(
                    label,
                    frozen,
                    require_frozen_at=args.require_frozen_at,
                )
            )

    if validation_errors:
        print("Label / frozen crawl validation failed:\n")
        for err in validation_errors:
            print(f"  {err}")
        print("\nSee evaluation/README.md — copy frozen_at from the frozen crawl at label time.")
        sys.exit(1)

    settings = get_settings()
    chroma = load_fca_docs(str(settings.fca_docs_dir))
    retriever = get_retriever(chroma, k=settings.rag_retrieval_k)

    site_results = []
    for site_id in matched:
        print(f"  [{site_id}] Loading frozen crawl...")
        frozen = load_frozen_crawl(frozen_files[site_id])
        label = load_ground_truth(label_files[site_id])
        crawl_result = frozen["crawl_result"]

        print(f"  [{site_id}] Running pipeline (live LLM calls)...")
        report = run_pipeline_from_frozen(crawl_result, retriever, url=frozen["url"])

        if not isinstance(report, AuditReport):
            print(f"  [{site_id}] SKIPPED — pipeline returned early exit: {report.status}")
            continue

        result = compare_to_ground_truth(report, label)
        site_results.append(result)

        print(f"  [{site_id}] MAE={result.mean_abs_error:.2f} rating_agreement={result.rating_agreement_pct:.0f}%")
        for name, oa in result.outcomes.items():
            agree_str = "✓" if oa.rating_agrees else "✗"
            print(f"    {agree_str} {name:<30} gt={oa.gt_score} pipeline={oa.pipeline_score} |err|={oa.abs_error}")

    if not site_results:
        print("\nNo complete results — all sites returned early exit or errors.")
        sys.exit(1)

    summary = summarise_accuracy(site_results)
    print()
    print(format_accuracy_report(summary))

    if args.json_out:
        out = {
            "site_count": summary.site_count,
            "overall_mae": summary.overall_mae,
            "rating_agreement_pct": summary.rating_agreement_pct,
            "per_outcome_mae": summary.per_outcome_mae,
            "worst_criteria": [
                {"outcome": o, "criterion_id": c, "disagreement_rate": r}
                for o, c, r in summary.worst_criteria
            ],
        }
        Path(args.json_out).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"\nJSON summary written to: {args.json_out}")

    gate_failures = check_accuracy_gates(
        summary,
        max_mae=args.max_mae,
        min_rating_agreement=args.min_rating_agreement,
    )
    if gate_failures:
        print("\nAccuracy gate FAILED:")
        for msg in gate_failures:
            print(f"  {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
