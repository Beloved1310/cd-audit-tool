"""Compare pipeline output with vs without FCA retrieval (RAG ablation)."""

from __future__ import annotations

from dataclasses import dataclass

from backend.pipeline.citation_grounding import count_grounded_citations
from backend.schemas.audit import AuditReport

_REQUIRED_OUTCOMES = (
    "Products & Services",
    "Price & Value",
    "Consumer Understanding",
    "Consumer Support",
)


@dataclass(frozen=True)
class RagAblationComparison:
    """Metrics comparing full-RAG vs empty-RAG runs on the same frozen crawl."""

    site_id: str
    score_mae: float
    outcome_scores_with_rag: dict[str, int]
    outcome_scores_without_rag: dict[str, int]
    citation_rate_with_rag: float
    citation_rate_without_rag: float
    findings_count_with_rag: int
    findings_count_without_rag: int
    rag_decorative: bool
    detail: str


def _outcome_scores(report: AuditReport) -> dict[str, int]:
    by_name = {o.outcome_name: o.score for o in report.outcomes}
    return {name: by_name.get(name, 0) for name in _REQUIRED_OUTCOMES}


def _citation_rate(report: AuditReport) -> float:
    cited, total = count_grounded_citations(report)
    if total == 0:
        return 0.0
    return round(cited / total, 4)


def _findings_count(report: AuditReport) -> int:
    return sum(len(o.findings) for o in report.outcomes) + len(report.dark_patterns) + len(
        report.vulnerability_gaps,
    )


def compare_rag_ablation(
    *,
    site_id: str,
    with_rag: AuditReport,
    without_rag: AuditReport,
    min_score_delta: float = 0.25,
    min_citation_delta: float = 0.05,
) -> RagAblationComparison:
    """Flag RAG as decorative when scores and citation rates barely change without retrieval."""
    scores_a = _outcome_scores(with_rag)
    scores_b = _outcome_scores(without_rag)
    errors = [abs(scores_a[n] - scores_b[n]) for n in _REQUIRED_OUTCOMES]
    score_mae = round(sum(errors) / len(errors), 3)

    cite_a = _citation_rate(with_rag)
    cite_b = _citation_rate(without_rag)
    cite_delta = abs(cite_a - cite_b)

    findings_a = _findings_count(with_rag)
    findings_b = _findings_count(without_rag)

    decorative = score_mae < min_score_delta and cite_delta < min_citation_delta
    if decorative:
        detail = (
            f"RAG appears decorative: outcome score MAE {score_mae:.2f} "
            f"(threshold {min_score_delta}) and citation-rate delta {cite_delta:.2f} "
            f"(threshold {min_citation_delta})."
        )
    else:
        detail = (
            f"RAG affects output: outcome score MAE {score_mae:.2f}, "
            f"citation-rate delta {cite_delta:.2f} "
            f"({cite_a:.0%} with RAG vs {cite_b:.0%} without)."
        )

    return RagAblationComparison(
        site_id=site_id,
        score_mae=score_mae,
        outcome_scores_with_rag=scores_a,
        outcome_scores_without_rag=scores_b,
        citation_rate_with_rag=cite_a,
        citation_rate_without_rag=cite_b,
        findings_count_with_rag=findings_a,
        findings_count_without_rag=findings_b,
        rag_decorative=decorative,
        detail=detail,
    )


def format_ablation_report(result: RagAblationComparison) -> str:
    lines = [
        f"RAG ablation: {result.site_id}",
        f"  Outcome score MAE (with vs without RAG): {result.score_mae:.2f}",
        f"  Citation rate with RAG:    {result.citation_rate_with_rag:.0%}",
        f"  Citation rate without RAG: {result.citation_rate_without_rag:.0%}",
        f"  Findings count with RAG:    {result.findings_count_with_rag}",
        f"  Findings count without RAG: {result.findings_count_without_rag}",
        "",
        f"  Scores with RAG:    {result.outcome_scores_with_rag}",
        f"  Scores without RAG: {result.outcome_scores_without_rag}",
        "",
        f"  {'WARNING' if result.rag_decorative else 'OK'}: {result.detail}",
    ]
    return "\n".join(lines)
