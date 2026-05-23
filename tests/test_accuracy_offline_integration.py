"""Offline accuracy path: ground truth ↔ pipeline report with aligned criterion IDs (no LLM)."""

from __future__ import annotations

import unittest
from pathlib import Path

from backend.evaluation.accuracy import compare_to_ground_truth, summarise_accuracy
from backend.evaluation.fixtures import audit_report_from_ground_truth
from backend.evaluation.ground_truth import load_ground_truth
from backend.pipeline.scorer import (
    UNDERSTANDING_CRITERIA,
    format_criteria_for_prompt,
    normalize_outcome_criteria,
)
from backend.schemas.audit import CriterionScore

_LABEL = Path(__file__).resolve().parents[1] / "evaluation/ground_truth/example_retail_bank.json"


class TestAccuracyOfflineIntegration(unittest.TestCase):
    def test_perfect_agreement_when_report_matches_labels(self):
        label = load_ground_truth(_LABEL)
        report = audit_report_from_ground_truth(label)
        site = compare_to_ground_truth(report, label)
        self.assertEqual(site.mean_abs_error, 0.0)
        self.assertEqual(site.rating_agreement_pct, 100.0)
        for oa in site.outcomes.values():
            self.assertEqual(len(oa.criteria), 10)
            self.assertEqual(oa.criterion_agreement_rate, 1.0)

    def test_mae_when_outcome_scores_diverge(self):
        label = load_ground_truth(_LABEL)
        report = audit_report_from_ground_truth(label)
        bumped = report.model_copy(
            update={
                "outcomes": [
                    o.model_copy(update={"score": min(10, o.score + 2)})
                    if o.outcome_name == "Price & Value"
                    else o
                    for o in report.outcomes
                ],
            },
        )
        site = compare_to_ground_truth(bumped, label)
        self.assertGreater(site.mean_abs_error, 0.0)

    def test_normalize_fills_missing_criterion_rows(self):
        partial = [
            CriterionScore(
                criterion_id=1,
                criterion_name="x",
                max_points=1,
                awarded_points=1,
                met=True,
                evidence="e",
                page_url="https://example.test/",
            ),
        ]
        full = normalize_outcome_criteria(partial, UNDERSTANDING_CRITERIA)
        self.assertEqual(len(full), 10)
        self.assertEqual(full[0].criterion_name, UNDERSTANDING_CRITERIA[0].name)

    def test_prompt_checklist_matches_ground_truth_ids(self):
        text = format_criteria_for_prompt(UNDERSTANDING_CRITERIA)
        self.assertIn("Criterion 1 (max 1 point(s)):", text)
        self.assertIn("Criterion 10 (max 1 point(s)):", text)


class TestAccuracySummaryOffline(unittest.TestCase):
    def test_summarise_multiple_sites(self):
        label = load_ground_truth(_LABEL)
        report = audit_report_from_ground_truth(label)
        sites = [compare_to_ground_truth(report, label)]
        summary = summarise_accuracy(sites)
        self.assertEqual(summary.site_count, 1)
        self.assertEqual(summary.overall_mae, 0.0)


if __name__ == "__main__":
    unittest.main()
