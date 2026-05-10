import json
import unittest
from pathlib import Path

from backend.evaluation.benchmark import run_benchmark_manifest
from backend.evaluation.metrics import compute_report_quality_metrics
from backend.schemas.audit import AuditReport, AuditStatus, ConfidenceLevel, OutcomeScore, RAGRating

_FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Citation labels produced by fca_loader._citation_label() for ingested PDFs.
_KNOWN_FCA_LABELS = {
    "FG22/5",
    "PS22/9",
    "Consumer Understanding Good Practice",
    "Consumer Support Good Practice",
    "FCA Vulnerable Customers Guidance",
}


class TestEvaluationMetrics(unittest.TestCase):
    def test_sample_fixture_high_score(self):
        root = Path(__file__).resolve().parent
        raw = (root / "fixtures" / "sample_audit_report.json").read_text(encoding="utf-8")
        report = AuditReport.model_validate_json(raw)
        m = compute_report_quality_metrics(report, fixture_id="sample")
        self.assertTrue(m.four_outcomes_present)
        self.assertTrue(m.overall_score_matches_mean)
        self.assertEqual(m.harness_score_0_100, 100)
        self.assertFalse(m.violations)

    def test_detects_overall_score_mismatch(self):
        from datetime import datetime, timezone

        o = lambda name, s: OutcomeScore(
            outcome_name=name,
            rating=RAGRating.GREEN if s >= 8 else RAGRating.AMBER,
            score=s,
            confidence=ConfidenceLevel.HIGH,
            summary="x",
            criteria_scores=[
                {
                    "criterion_id": 1,
                    "criterion_name": "a",
                    "max_points": 10,
                    "awarded_points": s,
                    "met": s == 10,
                    "evidence": "e",
                    "page_url": "https://x.com",
                },
            ],
        )
        report = AuditReport(
            insufficient_data=False,
            url="https://x.com",
            audited_at=datetime.now(timezone.utc),
            status=AuditStatus.COMPLETE,
            overall_rating=RAGRating.GREEN,
            overall_score=10,
            outcomes=[
                o("Products & Services", 8),
                o("Price & Value", 8),
                o("Consumer Understanding", 8),
                o("Consumer Support", 8),
            ],
            dark_patterns=[],
            vulnerability_gaps=[],
            pages_crawled=[],
            total_words_analysed=100,
            crawl_duration_seconds=1.0,
            pipeline_duration_seconds=2.0,
        )
        m = compute_report_quality_metrics(report)
        self.assertFalse(m.overall_score_matches_mean)
        self.assertTrue(any("overall_score" in v for v in m.violations))

    def test_default_benchmark_passes(self):
        root = Path(__file__).resolve().parent.parent
        manifest = root / "evaluation" / "benchmarks" / "default.json"
        if not manifest.is_file():
            self.skipTest("benchmark manifest missing")
        results, failures = run_benchmark_manifest(manifest, repo_root=root)
        self.assertTrue(results)
        self.assertEqual(failures, [], msg=json.dumps(failures, indent=2))

    # --- low-quality fixture: harness must detect the problems ---

    def test_low_quality_fixture_harness_score_is_low(self):
        raw = (_FIXTURES / "low_quality_audit_report.json").read_text(encoding="utf-8")
        report = AuditReport.model_validate_json(raw)
        m = compute_report_quality_metrics(report, fixture_id="low_quality")
        self.assertLess(m.harness_score_0_100, 50, "harness did not penalise low-quality report")

    def test_low_quality_fixture_detects_score_mismatch(self):
        raw = (_FIXTURES / "low_quality_audit_report.json").read_text(encoding="utf-8")
        report = AuditReport.model_validate_json(raw)
        m = compute_report_quality_metrics(report, fixture_id="low_quality")
        self.assertFalse(m.overall_score_matches_mean)
        self.assertTrue(any("overall_score" in v for v in m.violations))

    def test_low_quality_fixture_detects_missing_evidence(self):
        raw = (_FIXTURES / "low_quality_audit_report.json").read_text(encoding="utf-8")
        report = AuditReport.model_validate_json(raw)
        m = compute_report_quality_metrics(report, fixture_id="low_quality")
        self.assertEqual(m.criteria_with_evidence_when_partial_or_fail, 0.0)
        self.assertEqual(m.criteria_evidence_any, 0.0)
        self.assertEqual(m.findings_with_verbatim_evidence, 0.0)
        self.assertEqual(m.findings_with_fca_reference, 0.0)
        self.assertEqual(m.dark_patterns_with_evidence, 0.0)
        self.assertEqual(m.vulnerability_gaps_with_fca, 0.0)

    # --- score determinism: same report always produces the same metrics ---

    def test_metrics_are_deterministic(self):
        raw = (_FIXTURES / "sample_audit_report.json").read_text(encoding="utf-8")
        report = AuditReport.model_validate_json(raw)
        results = [compute_report_quality_metrics(report, fixture_id="sample") for _ in range(5)]
        scores = [r.harness_score_0_100 for r in results]
        self.assertEqual(
            len(set(scores)), 1,
            f"harness score varied across runs: {scores}",
        )
        for r in results:
            self.assertEqual(r.violations, results[0].violations)

    # --- faithfulness: FCA references in fixtures must come from ingested documents ---

    def test_sample_fixture_fca_references_use_known_labels(self):
        # Each fca_reference must start with a known ingested document name,
        # e.g. "FG22/5, p.14 — ..." or "Consumer Support Good Practice, p.3".
        raw = (_FIXTURES / "sample_audit_report.json").read_text(encoding="utf-8")
        report = AuditReport.model_validate_json(raw)
        for outcome in report.outcomes:
            for finding in outcome.findings:
                ref = finding.fca_reference.strip()
                if not ref:
                    continue
                grounded = any(ref.startswith(label) for label in _KNOWN_FCA_LABELS)
                self.assertTrue(
                    grounded,
                    f"finding fca_reference {ref!r} does not start with a known FCA document name. "
                    f"Expected one of: {_KNOWN_FCA_LABELS}",
                )


if __name__ == "__main__":
    unittest.main()
