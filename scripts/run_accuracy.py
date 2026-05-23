"""CLI: run the scoring pipeline against frozen crawls and compare to expert labels.

Usage:
    # Run all sites that have both a frozen crawl and a ground truth label:
    python scripts/run_accuracy.py

    # Run a single site:
    python scripts/run_accuracy.py --site example_retail_bank

    # Override directories:
    python scripts/run_accuracy.py \\
        --frozen evaluation/frozen_crawls \\
        --labels evaluation/ground_truth

Requires: GROQ_API_KEY set in environment or .env (live LLM calls are made for each site).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.evaluation.accuracy import (
    compare_to_ground_truth,
    format_accuracy_report,
    summarise_accuracy,
)
from backend.evaluation.frozen_crawl import load_frozen_crawl, run_pipeline_from_frozen
from backend.evaluation.ground_truth import load_ground_truth
from backend.ingestion.fca_loader import load_fca_docs, get_retriever
from backend.config import get_settings
from backend.schemas.audit import AuditReport


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
    args = parser.parse_args()

    frozen_dir = Path(args.frozen)
    labels_dir = Path(args.labels)

    frozen_files = {p.stem: p for p in sorted(frozen_dir.glob("*.json"))}
    label_files = {p.stem: p for p in sorted(labels_dir.glob("*.json"))}
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


if __name__ == "__main__":
    main()
