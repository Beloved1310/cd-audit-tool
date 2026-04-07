"""Fetch site content via Firecrawl (or WebBase fallback)."""

from __future__ import annotations

import logging

from backend.crawler.site_crawler import crawl_website
from backend.observability import stage_timer
from backend.pipeline.state import AuditState

logger = logging.getLogger(__name__)


def crawl_node(state: AuditState) -> dict:
    url = state["url"]
    try:
        with stage_timer("crawl"):
            result = crawl_website(url, http_client=state.get("http_client"))
        logger.info(
            "Crawl finished: pages=%s total_words=%s method=%s",
            len(result.pages),
            result.total_words,
            result.crawl_method,
        )
        return {"crawl_result": result}
    except Exception as e:  # noqa: BLE001
        logger.exception("crawl_website raised")
        return {
            "crawl_result": None,
            "status": "crawl_failed",
            "error_message": str(e),
        }
