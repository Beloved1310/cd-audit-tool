"""LangGraph: crawl → validate → analyse or early exit → compile.

``AuditState`` (TypedDict) lives in :mod:`backend.pipeline.state` to avoid
import cycles between this module and node implementations.
"""

from __future__ import annotations

import time
from typing import Any

from langgraph.graph import END, START, StateGraph

from backend.pipeline.nodes.compile_node import compile_node, early_exit_node
from backend.pipeline.nodes.crawl_node import crawl_node
from backend.pipeline.nodes.dark_patterns_node import dark_patterns_node
from backend.pipeline.nodes.price_value_node import price_value_node
from backend.pipeline.nodes.products_services_node import products_services_node
from backend.pipeline.nodes.support_node import support_node
from backend.pipeline.nodes.understanding_node import understanding_node
from backend.pipeline.nodes.validate_node import (
    route_after_validation,
    validate_node,
)
from backend.pipeline.nodes.vulnerability_node import vulnerability_node
from backend.pipeline.state import AuditState
from backend.schemas.audit import AuditReport, InsufficientDataReport

_COMPILED = None


def build_graph():
    g = StateGraph(AuditState)
    g.add_node("crawl", crawl_node)
    g.add_node("validate", validate_node)
    g.add_node("evaluate_products_services", products_services_node)
    g.add_node("evaluate_price_value", price_value_node)
    g.add_node("evaluate_understanding", understanding_node)
    g.add_node("evaluate_support", support_node)
    g.add_node("detect_dark_patterns", dark_patterns_node)
    g.add_node("detect_vulnerabilities", vulnerability_node)
    g.add_node("compile", compile_node)
    g.add_node("early_exit", early_exit_node)

    g.add_edge(START, "crawl")
    g.add_edge("crawl", "validate")
    g.add_conditional_edges(
        "validate",
        route_after_validation,
        {
            "early_exit": "early_exit",
            "evaluate_products_services": "evaluate_products_services",
        },
    )
    g.add_edge("evaluate_products_services", "evaluate_price_value")
    g.add_edge("evaluate_price_value", "evaluate_understanding")
    g.add_edge("evaluate_understanding", "evaluate_support")
    g.add_edge("evaluate_support", "detect_dark_patterns")
    g.add_edge("detect_dark_patterns", "detect_vulnerabilities")
    g.add_edge("detect_vulnerabilities", "compile")
    g.add_edge("compile", END)
    g.add_edge("early_exit", END)
    return g.compile()


def _compiled():
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = build_graph()
    return _COMPILED


def run_audit(url: str, retriever: Any) -> AuditReport | InsufficientDataReport:
    """Run the full audit graph; returns a complete audit or an early-exit report."""
    initial: AuditState = {
        "url": url.strip(),
        "retriever": retriever,
        "crawl_result": None,
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
    final = _compiled().invoke(initial)
    report = final.get("audit_report")
    if isinstance(report, (AuditReport, InsufficientDataReport)):
        return report
    raise RuntimeError("Pipeline finished without audit_report")
