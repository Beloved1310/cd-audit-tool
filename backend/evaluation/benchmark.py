"""Regression benchmark: JSON manifest of fixture reports and minimum harness scores."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from backend.evaluation.metrics import compute_report_quality_metrics
from backend.evaluation.schemas import ReportQualityMetrics
from backend.schemas.audit import AuditReport


class BenchmarkCase(BaseModel):
    """One frozen report plus acceptance threshold."""

    fixture_id: str = Field(..., min_length=1)
    report_path: str = Field(
        ...,
        description="Path to AuditReport JSON, relative to repo root unless absolute.",
    )
    min_harness_score: int = Field(default=80, ge=0, le=100)
    notes: str = ""


class BenchmarkManifest(BaseModel):
    cases: list[BenchmarkCase] = Field(default_factory=list)


def load_benchmark_manifest(path: Path) -> BenchmarkManifest:
    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    return BenchmarkManifest.model_validate(raw)


def _resolve_report_path(repo_root: Path, report_path: str) -> Path:
    p = Path(report_path)
    return p if p.is_absolute() else (repo_root / p)


def run_benchmark_manifest(
    manifest_path: Path,
    *,
    repo_root: Path,
) -> tuple[list[tuple[BenchmarkCase, ReportQualityMetrics]], list[str]]:
    """
    Run all cases. Returns ``(results, failures)`` where failures are human-readable
    strings for thresholds not met. ``report_path`` in each case is relative to ``repo_root``.
    """
    root = repo_root.resolve()
    # If manifest is in evaluation/benchmarks/, repo root is parents[2] — caller passes repo_root
    manifest = load_benchmark_manifest(manifest_path)
    results: list[tuple[BenchmarkCase, ReportQualityMetrics]] = []
    failures: list[str] = []

    for case in manifest.cases:
        rp = _resolve_report_path(root, case.report_path)
        if not rp.is_file():
            failures.append(f"{case.fixture_id}: report file missing: {rp}")
            continue
        report = AuditReport.model_validate_json(rp.read_text(encoding="utf-8"))
        metrics = compute_report_quality_metrics(report, fixture_id=case.fixture_id)
        results.append((case, metrics))
        if metrics.harness_score_0_100 < case.min_harness_score:
            failures.append(
                f"{case.fixture_id}: harness {metrics.harness_score_0_100} "
                f"< required {case.min_harness_score}",
            )
        if metrics.violations:
            for v in metrics.violations:
                failures.append(f"{case.fixture_id}: {v}")

    return results, failures
