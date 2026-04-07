"""LangGraph pipeline state (AuditState)."""

from __future__ import annotations

from typing import Any, TypedDict


class AuditState(TypedDict, total=False):
    """State carried through the Consumer Duty audit graph."""

    url: str
    pipeline_version: str
    retriever: Any
    http_client: Any
    crawl_result: Any  # CrawlResult | None
    validated: bool
    status: str  # "pending", "crawl_failed", "insufficient_data", "complete"
    insufficient_data_reason: str
    error_message: str
    products_services_score: Any  # OutcomeScore | None
    price_value_score: Any  # OutcomeScore | None
    understanding_score: Any  # OutcomeScore | None
    support_score: Any  # OutcomeScore | None
    dark_patterns: list  # list[DarkPattern]
    vulnerability_gaps: list  # list[VulnerabilityGap]
    audit_report: Any  # AuditReport | None
    pipeline_start_time: float
