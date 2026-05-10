"""Freeze a live CrawlResult to disk and replay the scoring pipeline against it.

This is the foundation of scoring accuracy validation: both the human expert and
the pipeline evaluate *identical* content, so any score difference is attributable
to the pipeline — not to a page changing between runs.

Usage (CLI):
    python scripts/freeze_crawl.py --url https://example.co.uk --out evaluation/frozen_crawls/example.json

Usage (Python):
    from backend.evaluation.frozen_crawl import load_frozen_crawl, run_pipeline_from_frozen
    crawl = load_frozen_crawl("evaluation/frozen_crawls/example.json")
    report = run_pipeline_from_frozen(crawl["crawl_result"], retriever)
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from backend.crawler.site_crawler import CrawlResult, CrawledPage
from backend.pipeline.nodes.compile_node import compile_node, early_exit_node
from backend.pipeline.nodes.dark_patterns_node import dark_patterns_node
from backend.pipeline.nodes.price_value_node import price_value_node
from backend.pipeline.nodes.products_services_node import products_services_node
from backend.pipeline.nodes.support_node import support_node
from backend.pipeline.nodes.understanding_node import understanding_node
from backend.pipeline.nodes.validate_node import route_after_validation, validate_node
from backend.pipeline.nodes.vulnerability_node import vulnerability_node
from backend.pipeline.state import AuditState
from backend.pipeline.versioning import compute_pipeline_version
from backend.schemas.audit import AuditReport, InsufficientDataReport

_REPLAY_GRAPH = None


def _replay_graph():
    """LangGraph starting at validate (crawl already injected)."""
    global _REPLAY_GRAPH
    if _REPLAY_GRAPH is None:
        g = StateGraph(AuditState)
        g.add_node("validate", validate_node)
        g.add_node("evaluate_products_services", products_services_node)
        g.add_node("evaluate_price_value", price_value_node)
        g.add_node("evaluate_understanding", understanding_node)
        g.add_node("evaluate_support", support_node)
        g.add_node("detect_dark_patterns", dark_patterns_node)
        g.add_node("detect_vulnerabilities", vulnerability_node)
        g.add_node("compile", compile_node)
        g.add_node("early_exit", early_exit_node)
        g.add_edge(START, "validate")
        g.add_conditional_edges(
            "validate",
            route_after_validation,
            {"early_exit": "early_exit", "evaluate_products_services": "evaluate_products_services"},
        )
        g.add_edge("evaluate_products_services", "evaluate_price_value")
        g.add_edge("evaluate_price_value", "evaluate_understanding")
        g.add_edge("evaluate_understanding", "evaluate_support")
        g.add_edge("evaluate_support", "detect_dark_patterns")
        g.add_edge("detect_dark_patterns", "detect_vulnerabilities")
        g.add_edge("detect_vulnerabilities", "compile")
        g.add_edge("compile", END)
        g.add_edge("early_exit", END)
        _REPLAY_GRAPH = g.compile()
    return _REPLAY_GRAPH


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def _crawl_result_to_dict(result: CrawlResult) -> dict:
    return {
        "total_words": result.total_words,
        "duration_seconds": result.duration_seconds,
        "crawl_method": result.crawl_method,
        "errors": result.errors,
        "pages": [
            {
                "url": p.url,
                "title": p.title,
                "content": p.content,
                "word_count": p.word_count,
                "crawled_at": p.crawled_at.isoformat(),
            }
            for p in result.pages
        ],
    }


def _crawl_result_from_dict(d: dict) -> CrawlResult:
    pages = [
        CrawledPage(
            url=p["url"],
            title=p.get("title", ""),
            content=p["content"],
            word_count=p.get("word_count", len(p["content"].split())),
            crawled_at=datetime.fromisoformat(p["crawled_at"]),
        )
        for p in d.get("pages", [])
    ]
    return CrawlResult(
        pages=pages,
        total_words=d.get("total_words", sum(p.word_count for p in pages)),
        duration_seconds=d.get("duration_seconds", 0.0),
        crawl_method=d.get("crawl_method", "frozen_replay"),
        errors=d.get("errors", []),
    )


def save_frozen_crawl(
    crawl_result: CrawlResult,
    path: Path | str,
    *,
    site_id: str = "",
    url: str = "",
) -> None:
    """Serialise a CrawlResult to a JSON file for later replay."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "site_id": site_id or path.stem,
        "url": url or (crawl_result.pages[0].url if crawl_result.pages else ""),
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "crawl_result": _crawl_result_to_dict(crawl_result),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_frozen_crawl(path: Path | str) -> dict:
    """Load a frozen crawl file. Returns the full dict including site_id and url."""
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    data["crawl_result"] = _crawl_result_from_dict(data["crawl_result"])
    return data


# ---------------------------------------------------------------------------
# Replay runner
# ---------------------------------------------------------------------------

def run_pipeline_from_frozen(
    crawl_result: CrawlResult,
    retriever: Any,
    *,
    url: str = "",
) -> AuditReport | InsufficientDataReport:
    """Score a frozen crawl through the full pipeline (validate → compile), no HTTP calls."""
    site_url = url or (crawl_result.pages[0].url if crawl_result.pages else "unknown")
    initial: AuditState = {
        "url": site_url,
        "pipeline_version": compute_pipeline_version(),
        "retriever": retriever,
        "http_client": None,
        "crawl_result": crawl_result,
        "validated": False,
        "status": "pending",
        "insufficient_data_reason": "",
        "error_message": "",
        "products_services_score": None,
        "price_value_score": None,
        "understanding_score": None,
        "support_score": None,
        "dark_patterns": [],
        "vulnerability_gaps": [],
        "audit_report": None,
        "pipeline_start_time": time.time(),
    }
    final = _replay_graph().invoke(initial)
    report = final.get("audit_report")
    if isinstance(report, (AuditReport, InsufficientDataReport)):
        return report
    raise RuntimeError("Replay pipeline finished without audit_report in state")
