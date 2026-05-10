#!/usr/bin/env python3
"""Offline evaluation harness: quality metrics on frozen AuditReport JSON.

Usage (from repository root):

  python scripts/run_evaluation.py
  python scripts/run_evaluation.py --report tests/fixtures/sample_audit_report.json
  python scripts/run_evaluation.py --benchmark evaluation/benchmarks/default.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> int:
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    parser = argparse.ArgumentParser(description="Audit report evaluation harness")
    parser.add_argument(
        "--report",
        type=str,
        default="tests/fixtures/sample_audit_report.json",
        help="Path to AuditReport JSON (relative to repo root unless absolute).",
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        default="",
        help="If set, run benchmark manifest JSON (paths relative to repo root).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print metrics as JSON only.",
    )
    args = parser.parse_args()

    if args.benchmark:
        from backend.evaluation.benchmark import run_benchmark_manifest

        manifest = Path(args.benchmark)
        mp = manifest if manifest.is_absolute() else (root / manifest)
        results, failures = run_benchmark_manifest(mp, repo_root=root)
        if args.json:
            out = {
                "cases": [
                    {
                        "fixture_id": c.fixture_id,
                        "harness_score": m.harness_score_0_100,
                        "min_required": c.min_harness_score,
                        "violations": m.violations,
                    }
                    for c, m in results
                ],
                "failures": failures,
            }
            print(json.dumps(out, indent=2))
        else:
            for case, metrics in results:
                print(f"=== {case.fixture_id} ===")
                print(metrics.model_dump_json(indent=2))
            if failures:
                print("\nFAILURES:", file=sys.stderr)
                for f in failures:
                    print(f"  - {f}", file=sys.stderr)
                return 1
        return 0 if not failures else 1

    from backend.evaluation.metrics import compute_report_quality_metrics
    from backend.schemas.audit import AuditReport

    rp = Path(args.report)
    path = rp if rp.is_absolute() else (root / rp)
    report = AuditReport.model_validate_json(path.read_text(encoding="utf-8"))
    metrics = compute_report_quality_metrics(report, fixture_id=path.stem)
    if args.json:
        print(metrics.model_dump_json(indent=2))
    else:
        print(f"Report: {path}")
        print(metrics.model_dump_json(indent=2))
        if metrics.violations:
            print("\nViolations:")
            for v in metrics.violations:
                print(f"  - {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
