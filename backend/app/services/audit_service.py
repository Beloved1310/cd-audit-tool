"""Audit/compare/journey application services.

This module owns use-cases and idempotency/caching policies. The API layer should
remain a thin adapter.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime

from backend.cache.aux_cache import _hash_key, get_cached_model, put_cached_model
from backend.cache.report_cache import cache_report, get_cached_report
from backend.pipeline.graph import run_audit
from backend.pipeline.journey_runner import run_journey
from backend.schemas.audit import AuditReport, ComparisonReport, InsufficientDataReport
from backend.schemas.journey import JourneyReport, JourneyStepInput
from backend.util.url_norm import canonical_url


def build_comparison_report(
    *,
    url_a: str,
    url_b: str,
    report_a: AuditReport | InsufficientDataReport,
    report_b: AuditReport | InsufficientDataReport,
) -> ComparisonReport:
    return ComparisonReport(
        url_a=url_a,
        url_b=url_b,
        hash_a=hashlib.md5(url_a.encode()).hexdigest(),
        hash_b=hashlib.md5(url_b.encode()).hexdigest(),
        report_a=report_a,
        report_b=report_b,
        generated_at_iso=datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    )


def get_or_run_audit(
    *,
    url: str,
    retriever,
    pipeline_version: str,
    http_client=None,
) -> AuditReport | InsufficientDataReport:
    cached = get_cached_report(url, pipeline_version=pipeline_version)
    if cached is not None:
        return cached
    report = run_audit(url, retriever, http_client)
    cache_report(url, report)
    return report


async def get_or_run_compare(
    *,
    url_a: str,
    url_b: str,
    retriever,
    pipeline_version: str,
    http_client=None,
) -> ComparisonReport:
    ua, ub = sorted([url_a.strip(), url_b.strip()])
    key_payload = "|".join([pipeline_version, canonical_url(ua), canonical_url(ub)])
    key_hash = _hash_key("compare", key_payload)
    cached = get_cached_model("compare", key_hash, ComparisonReport)
    if cached is not None:
        return cached

    async def run_single(u: str) -> AuditReport | InsufficientDataReport:
        cached_single = get_cached_report(u, pipeline_version=pipeline_version)
        if cached_single is not None:
            return cached_single
        report = await asyncio.to_thread(run_audit, u, retriever, http_client)
        cache_report(u, report)
        return report

    sem = asyncio.Semaphore(2)

    async def bounded(u: str):
        await sem.acquire()
        try:
            return await run_single(u)
        finally:
            sem.release()

    report_a, report_b = await asyncio.gather(bounded(ua), bounded(ub))
    out = build_comparison_report(url_a=ua, url_b=ub, report_a=report_a, report_b=report_b)
    put_cached_model("compare", key_hash, out)
    return out


def get_or_run_journey(
    *,
    steps: list[JourneyStepInput],
    retriever,
    pipeline_version: str,
    http_client=None,
) -> JourneyReport:
    canon = [canonical_url(s.url) for s in steps]
    key_payload = "|".join([pipeline_version, *canon])
    key_hash = _hash_key("journey", key_payload)
    cached = get_cached_model("journey", key_hash, JourneyReport)
    if cached is not None:
        return cached
    out = run_journey(steps, retriever, http_client)
    put_cached_model("journey", key_hash, out)
    return out

