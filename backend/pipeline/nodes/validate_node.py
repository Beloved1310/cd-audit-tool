"""Crawl quality gate: minimum pages and words."""

from __future__ import annotations

from backend.crawler.site_crawler import assess_crawl_quality
from backend.pipeline.state import AuditState


def validate_node(state: AuditState) -> dict:
    cr = state.get("crawl_result")
    if cr is None:
        return {"validated": False}

    ok, reason = assess_crawl_quality(cr)
    if ok:
        return {"validated": True}

    return {
        "validated": False,
        "status": "insufficient_data",
        "insufficient_data_reason": reason,
    }


def route_after_validation(state: AuditState) -> str:
    if state.get("status") == "crawl_failed":
        return "early_exit"
    if not state.get("validated"):
        return "early_exit"
    return "evaluate_products_services"
