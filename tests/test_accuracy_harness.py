"""Unit tests for the scoring accuracy harness.

These tests do NOT call the LLM or ChromaDB. They verify:
  - Ground truth label schema validates correctly
  - CrawlResult serialises and deserialises without loss
  - compare_to_ground_truth() computes correct MAE and rating agreement
  - summarise_accuracy() aggregates correctly across multiple sites
  - format_accuracy_report() produces non-empty output

Offline accuracy integration (aligned criterion IDs, no LLM):
  tests/test_accuracy_offline_integration.py

Live pipeline vs frozen crawl (requires GROQ_API_KEY):
  tests/test_accuracy_integration.py
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.crawler.site_crawler import CrawledPage, CrawlResult
from backend.evaluation.accuracy import (
    compare_to_ground_truth,
    format_accuracy_report,
    summarise_accuracy,
)
from backend.evaluation.frozen_crawl import load_frozen_crawl, save_frozen_crawl
from backend.evaluation.ground_truth import GroundTruthLabel, load_ground_truth, save_ground_truth
from backend.schemas.audit import (
    AuditReport,
    AuditStatus,
    ConfidenceLevel,
    CriterionScore,
    Finding,
    OutcomeScore,
    RAGRating,
)

_FIXTURES = Path(__file__).resolve().parent.parent / "evaluation"


def _make_crawl_result(pages: int = 3, words: int = 5000) -> CrawlResult:
    return CrawlResult(
        pages=[
            CrawledPage(
                url=f"https://test.example/page{i}",
                title=f"Page {i}",
                content="word " * (words // pages),
                word_count=words // pages,
                crawled_at=datetime.now(timezone.utc),
            )
            for i in range(pages)
        ],
        total_words=words,
        duration_seconds=5.0,
        crawl_method="frozen_replay",
        errors=[],
    )


def _make_criterion(cid: int, awarded: int, max_pts: int = 1) -> CriterionScore:
    return CriterionScore(
        criterion_id=cid,
        criterion_name=f"Criterion {cid}",
        max_points=max_pts,
        awarded_points=awarded,
        met=(awarded == max_pts),
        evidence="Some evidence text." if awarded else "",
        page_url="https://test.example/" if awarded else "",
    )


def _make_outcome(name: str, score: int) -> OutcomeScore:
    # Ten binary criteria (IDs 1–10), same shape as scorer.py / ground truth labels.
    criteria = [
        _make_criterion(i, 1 if i <= score else 0, max_pts=1) for i in range(1, 11)
    ]
    return OutcomeScore(
        outcome_name=name,
        rating=RAGRating.GREEN,  # overwritten by validator
        score=score,
        confidence=ConfidenceLevel.HIGH,
        summary="Test summary.",
        criteria_scores=criteria,
        findings=[],
    )


def _make_report(ps=8, pv=7, cu=6, cs=9) -> AuditReport:
    outcomes = [
        _make_outcome("Products & Services", ps),
        _make_outcome("Price & Value", pv),
        _make_outcome("Consumer Understanding", cu),
        _make_outcome("Consumer Support", cs),
    ]
    overall = round((ps + pv + cu + cs) / 4)
    return AuditReport(
        url="https://test.example/",
        audited_at=datetime.now(timezone.utc),
        status=AuditStatus.COMPLETE,
        overall_score=overall,
        overall_rating=RAGRating.GREEN,
        outcomes=outcomes,
        dark_patterns=[],
        vulnerability_gaps=[],
        pages_crawled=["https://test.example/"],
        total_words_analysed=5000,
        crawl_duration_seconds=5.0,
        pipeline_duration_seconds=30.0,
    )


def _make_label(site_id: str, ps=8, pv=7, cu=6, cs=9) -> GroundTruthLabel:
    def _outcome_dict(score: int) -> dict:
        return {
            "notes": "",
            "criteria": {str(i): {"awarded": 1 if i <= score else 0, "note": ""} for i in range(1, 11)},
        }
    return GroundTruthLabel(
        site_id=site_id,
        url="https://test.example/",
        labelled_by="test",
        labelled_at="2026-05-10",
        outcomes={
            "Products & Services": _outcome_dict(ps),
            "Price & Value": _outcome_dict(pv),
            "Consumer Understanding": _outcome_dict(cu),
            "Consumer Support": _outcome_dict(cs),
        },
    )


class TestGroundTruthSchema(unittest.TestCase):
    def test_valid_label_loads(self):
        label = _make_label("test_site", ps=8, pv=7, cu=6, cs=9)
        self.assertEqual(label.outcome_score("Products & Services"), 8)
        self.assertEqual(label.outcome_score("Price & Value"), 7)
        self.assertEqual(label.outcome_score("Consumer Understanding"), 6)
        self.assertEqual(label.outcome_score("Consumer Support"), 9)

    def test_overall_score_is_mean(self):
        label = _make_label("t", ps=8, pv=6, cu=6, cs=8)
        self.assertEqual(label.overall_score(), 7)

    def test_missing_outcome_raises(self):
        with self.assertRaises(Exception):
            GroundTruthLabel(
                site_id="x",
                url="https://x.com",
                outcomes={"Products & Services": {"notes": "", "criteria": {"1": {"awarded": 1}}}},
            )

    def test_invalid_criterion_id_raises(self):
        with self.assertRaises(Exception):
            GroundTruthLabel(
                site_id="x",
                url="https://x.com",
                outcomes={
                    o: {"notes": "", "criteria": {"abc": {"awarded": 1}}}
                    for o in ("Products & Services", "Price & Value", "Consumer Understanding", "Consumer Support")
                },
            )

    def test_roundtrip_to_disk(self):
        label = _make_label("roundtrip_site")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "roundtrip_site.json"
            save_ground_truth(label, p)
            loaded = load_ground_truth(p)
        self.assertEqual(loaded.site_id, label.site_id)
        self.assertEqual(loaded.outcome_score("Consumer Support"), label.outcome_score("Consumer Support"))

    def test_sample_fixture_validates(self):
        fixture = _FIXTURES / "ground_truth" / "example_retail_bank.json"
        if not fixture.is_file():
            self.skipTest("sample fixture missing")
        label = load_ground_truth(fixture)
        self.assertEqual(label.site_id, "example_retail_bank")
        for outcome in ("Products & Services", "Price & Value", "Consumer Understanding", "Consumer Support"):
            self.assertIn(outcome, label.outcomes)
            score = label.outcome_score(outcome)
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 10)


class TestFrozenCrawlSerialisation(unittest.TestCase):
    def test_roundtrip(self):
        crawl = _make_crawl_result(pages=3, words=900)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "test_site.json"
            save_frozen_crawl(crawl, p, site_id="test_site", url="https://test.example/")
            loaded = load_frozen_crawl(p)

        result = loaded["crawl_result"]
        self.assertIsInstance(result, CrawlResult)
        self.assertEqual(len(result.pages), 3)
        self.assertEqual(result.pages[0].url, "https://test.example/page0")
        self.assertEqual(loaded["site_id"], "test_site")

    def test_page_content_preserved(self):
        crawl = _make_crawl_result(pages=2, words=200)
        original_content = crawl.pages[0].content
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "content_test.json"
            save_frozen_crawl(crawl, p, site_id="content_test")
            loaded = load_frozen_crawl(p)
        self.assertEqual(loaded["crawl_result"].pages[0].content, original_content)

    def test_sample_frozen_crawl_loads(self):
        fixture = _FIXTURES / "frozen_crawls" / "example_retail_bank.json"
        if not fixture.is_file():
            self.skipTest("sample frozen crawl missing")
        data = load_frozen_crawl(fixture)
        crawl = data["crawl_result"]
        self.assertGreater(len(crawl.pages), 0)
        self.assertGreater(crawl.total_words, 0)


class TestAccuracyComparison(unittest.TestCase):
    def test_perfect_agreement(self):
        report = _make_report(ps=8, pv=7, cu=6, cs=9)
        label = _make_label("site_a", ps=8, pv=7, cu=6, cs=9)
        result = compare_to_ground_truth(report, label)
        self.assertEqual(result.mean_abs_error, 0.0)
        self.assertEqual(result.rating_agreement_pct, 100.0)
        for oa in result.outcomes.values():
            self.assertEqual(oa.abs_error, 0)
            self.assertTrue(oa.rating_agrees)

    def test_partial_error(self):
        # Pipeline says 8,7,6,9 — expert says 5,5,5,5
        report = _make_report(ps=8, pv=7, cu=6, cs=9)
        label = _make_label("site_b", ps=5, pv=5, cu=5, cs=5)
        result = compare_to_ground_truth(report, label)
        # Errors: 3,2,1,4 → mean = 2.5
        self.assertAlmostEqual(result.mean_abs_error, 2.5)
        # Pipeline 8→GREEN, expert 5→AMBER: disagree on P&S
        # Pipeline 7→AMBER, expert 5→AMBER: agree on P&V
        # Pipeline 6→AMBER, expert 5→AMBER: agree on CU
        # Pipeline 9→GREEN, expert 5→AMBER: disagree on CS
        self.assertEqual(result.rating_agreement_pct, 50.0)

    def test_non_complete_report_raises(self):
        from backend.schemas.audit import InsufficientDataReport
        report = _make_report()
        report = report.model_copy(update={"status": AuditStatus.INSUFFICIENT_DATA})
        label = _make_label("site_c")
        with self.assertRaises(ValueError):
            compare_to_ground_truth(report, label)

    def test_abs_error_values(self):
        report = _make_report(ps=3, pv=3, cu=3, cs=3)
        label = _make_label("site_d", ps=8, pv=8, cu=8, cs=8)
        result = compare_to_ground_truth(report, label)
        for oa in result.outcomes.values():
            self.assertEqual(oa.abs_error, 5)
        self.assertEqual(result.mean_abs_error, 5.0)


class TestAccuracySummary(unittest.TestCase):
    def test_single_site(self):
        report = _make_report(ps=7, pv=7, cu=7, cs=7)
        label = _make_label("s1", ps=8, pv=6, cu=7, cs=8)
        result = compare_to_ground_truth(report, label)
        summary = summarise_accuracy([result])
        self.assertEqual(summary.site_count, 1)
        self.assertAlmostEqual(summary.overall_mae, 0.75)

    def test_multiple_sites_aggregate(self):
        r1 = compare_to_ground_truth(_make_report(8, 8, 8, 8), _make_label("s1", 8, 8, 8, 8))
        r2 = compare_to_ground_truth(_make_report(3, 3, 3, 3), _make_label("s2", 8, 8, 8, 8))
        summary = summarise_accuracy([r1, r2])
        self.assertEqual(summary.site_count, 2)
        self.assertAlmostEqual(summary.overall_mae, 2.5)  # (0 + 5) / 2

    def test_empty_returns_zero(self):
        summary = summarise_accuracy([])
        self.assertEqual(summary.site_count, 0)
        self.assertEqual(summary.overall_mae, 0.0)

    def test_format_report_non_empty(self):
        r1 = compare_to_ground_truth(_make_report(7, 6, 8, 7), _make_label("s1", 8, 7, 7, 8))
        summary = summarise_accuracy([r1])
        report_text = format_accuracy_report(summary)
        self.assertIn("MAE", report_text)
        self.assertIn("Rating agreement", report_text)
        self.assertGreater(len(report_text), 50)

    def test_worst_criteria_sorted_descending(self):
        r1 = compare_to_ground_truth(_make_report(5, 8, 8, 8), _make_label("s1", 8, 8, 8, 8))
        summary = summarise_accuracy([r1])
        if summary.worst_criteria:
            rates = [rate for _, _, rate in summary.worst_criteria]
            self.assertEqual(rates, sorted(rates, reverse=True))


if __name__ == "__main__":
    unittest.main()
