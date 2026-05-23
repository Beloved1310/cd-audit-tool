"""Live accuracy integration: frozen crawl + Groq pipeline vs expert labels (optional)."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from backend.config import get_settings
from backend.crawler.site_crawler import CrawlResult
from backend.evaluation.accuracy import compare_to_ground_truth
from backend.evaluation.frozen_crawl import load_frozen_crawl, run_pipeline_from_frozen
from backend.evaluation.ground_truth import load_ground_truth
from backend.ingestion.fca_loader import get_retriever, load_fca_docs
from backend.schemas.audit import AuditStatus

_SITE = "example_retail_bank"
_FROZEN = (
    Path(__file__).resolve().parents[1] / "evaluation/frozen_crawls" / f"{_SITE}.json"
)
_LABEL = (
    Path(__file__).resolve().parents[1] / "evaluation/ground_truth" / f"{_SITE}.json"
)


@unittest.skipUnless(
    os.environ.get("GROQ_API_KEY", "").strip(),
    "Set GROQ_API_KEY to run live accuracy integration",
)
class TestAccuracyLiveIntegration(unittest.TestCase):
    """Runs one frozen site end-to-end; labels are synthetic so MAE is informational only."""

    def test_pipeline_produces_ten_criteria_per_outcome(self):
        settings = get_settings()
        chroma = load_fca_docs(str(settings.fca_docs_dir))
        retriever = get_retriever(chroma, k=settings.rag_retrieval_k)
        frozen = load_frozen_crawl(_FROZEN)
        crawl_result = CrawlResult.model_validate(frozen["crawl_result"])
        label = load_ground_truth(_LABEL)

        report = run_pipeline_from_frozen(
            crawl_result,
            retriever,
            url=frozen["url"],
        )
        self.assertEqual(report.status, AuditStatus.COMPLETE)
        for outcome in report.outcomes:
            self.assertEqual(
                len(outcome.criteria_scores),
                10,
                f"{outcome.outcome_name} criteria count",
            )
        site = compare_to_ground_truth(report, label)
        self.assertGreaterEqual(site.mean_abs_error, 0.0)


if __name__ == "__main__":
    unittest.main()
