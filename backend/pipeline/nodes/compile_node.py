"""Assemble :class:`~backend.schemas.audit.AuditReport` from graph state."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from backend.pipeline.state import AuditState
from backend.schemas.audit import AuditReport, AuditStatus, InsufficientDataReport


def compile_node(state: AuditState) -> dict:
    cr = state["crawl_result"]
    if cr is None:
        raise RuntimeError("compile_node requires crawl_result")
    ps = state.get("products_services_score")
    pv = state.get("price_value_score")
    u = state.get("understanding_score")
    s = state.get("support_score")
    if ps is None or pv is None or u is None or s is None:
        raise RuntimeError(
            "compile_node requires products_services_score, price_value_score, "
            "understanding_score, and support_score",
        )

    t0 = float(state.get("pipeline_start_time") or time.time())
    now = datetime.now(timezone.utc)
    pipeline_duration = time.time() - t0

    report = AuditReport(
        insufficient_data=False,
        url=state["url"],
        audited_at=now,
        status=AuditStatus.COMPLETE,
        outcomes=[ps, pv, u, s],
        dark_patterns=list(state.get("dark_patterns") or []),
        vulnerability_gaps=list(state.get("vulnerability_gaps") or []),
        pages_crawled=[p.url for p in cr.pages],
        total_words_analysed=cr.total_words,
        crawl_duration_seconds=cr.duration_seconds,
        pipeline_duration_seconds=pipeline_duration,
    )
    report.compute_overall()
    return {"audit_report": report, "status": "complete"}


def early_exit_node(state: AuditState) -> dict:
    now = datetime.now(timezone.utc)
    t0 = float(state.get("pipeline_start_time") or time.time())
    pipeline_duration = time.time() - t0

    cr = state.get("crawl_result")
    pages_crawled = [p.url for p in cr.pages] if cr else []
    words = cr.total_words if cr else 0
    crawl_dur = cr.duration_seconds if cr else 0.0

    status_raw = state.get("status") or ""
    if status_raw == "crawl_failed":
        ast = AuditStatus.CRAWL_FAILED
    else:
        ast = AuditStatus.INSUFFICIENT_DATA

    reason = (
        state.get("insufficient_data_reason")
        or state.get("error_message")
        or "Audit could not be completed"
    )

    report = InsufficientDataReport(
        url=state["url"],
        audited_at=now,
        status=ast,
        reason=reason,
        pages_crawled=pages_crawled,
        total_words_analysed=words,
        crawl_duration_seconds=crawl_dur,
        pipeline_duration_seconds=pipeline_duration,
    )
    return {"audit_report": report}
