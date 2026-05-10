"""Compute heuristic quality metrics on completed audit reports (offline)."""

from __future__ import annotations

from backend.evaluation.schemas import ReportQualityMetrics
from backend.schemas.audit import AuditReport, AuditStatus, RAGRating


def _rating_matches_score(score: int, rating: RAGRating) -> bool:
    if score >= 8:
        return rating == RAGRating.GREEN
    if score >= 5:
        return rating == RAGRating.AMBER
    return rating == RAGRating.RED


def compute_report_quality_metrics(
    report: AuditReport,
    *,
    fixture_id: str = "",
) -> ReportQualityMetrics:
    """Derive :class:`ReportQualityMetrics` from a complete audit report."""
    violations: list[str] = []

    required = (
        "Products & Services",
        "Price & Value",
        "Consumer Understanding",
        "Consumer Support",
    )
    by_name = {o.outcome_name: o for o in report.outcomes}
    four_ok = all(by_name.get(n) is not None for n in required)
    if not four_ok:
        violations.append("Missing one or more required outcomes (four PRIN outcomes).")

    overall_ok = True
    if report.status == AuditStatus.COMPLETE and four_ok:
        scores = [by_name[n].score for n in required]
        mean_s = int(round(sum(scores) / len(scores)))
        if report.overall_score is None:
            overall_ok = False
            violations.append("COMPLETE report missing overall_score.")
        elif report.overall_score != mean_s:
            overall_ok = False
            violations.append(
                f"overall_score {report.overall_score} != mean of outcomes {mean_s}",
            )
        if report.overall_rating is not None and report.overall_score is not None:
            if not _rating_matches_score(report.overall_score, report.overall_rating):
                overall_ok = False
                violations.append("overall_rating inconsistent with overall_score band.")

    criteria_total = 0
    crit_partial_with_proof = 0
    crit_partial_total = 0
    crit_any_proof = 0

    findings_total = 0
    findings_evidence = 0
    findings_fca = 0

    scores_ok = True
    rating_ok = True

    for o in report.outcomes:
        if not (0 <= o.score <= 10):
            scores_ok = False
            violations.append(f"Outcome {o.outcome_name!r} score out of range: {o.score}")
        if not _rating_matches_score(o.score, o.rating):
            rating_ok = False
            violations.append(
                f"Outcome {o.outcome_name!r} rating {o.rating} inconsistent with score {o.score}",
            )

        for c in o.criteria_scores:
            criteria_total += 1
            has_proof = bool((c.evidence or "").strip() or (c.page_url or "").strip())
            if has_proof:
                crit_any_proof += 1
            if c.awarded_points < c.max_points:
                crit_partial_total += 1
                if has_proof:
                    crit_partial_with_proof += 1

        for f in o.findings:
            findings_total += 1
            if (f.evidence_text or "").strip():
                findings_evidence += 1
            if (f.fca_reference or "").strip():
                findings_fca += 1

    dp_total = len(report.dark_patterns)
    dp_evidence = sum(1 for d in report.dark_patterns if (d.evidence_text or "").strip())

    vg_total = len(report.vulnerability_gaps)
    vg_fca = sum(1 for g in report.vulnerability_gaps if (g.fca_reference or "").strip())

    rate_partial = (
        crit_partial_with_proof / crit_partial_total if crit_partial_total else 1.0
    )
    rate_any = crit_any_proof / criteria_total if criteria_total else 1.0
    rate_f_ev = findings_evidence / findings_total if findings_total else 1.0
    rate_f_fca = findings_fca / findings_total if findings_total else 1.0
    rate_dp = dp_evidence / dp_total if dp_total else 1.0
    rate_vg = vg_fca / vg_total if vg_total else 1.0

    # Weighted harness score (weights sum to 100 when all boolean gates pass and rates are 1.0)
    w = (
        10 * int(four_ok)
        + 10 * int(overall_ok)
        + 10 * int(scores_ok and rating_ok)
        + 25 * rate_partial
        + 15 * rate_any
        + 12 * rate_f_ev
        + 13 * rate_f_fca
        + 3 * rate_dp
        + 2 * rate_vg
    )
    harness = int(round(min(100, max(0, w))))

    return ReportQualityMetrics(
        fixture_id=fixture_id,
        pipeline_version=report.pipeline_version or "",
        four_outcomes_present=four_ok,
        overall_score_matches_mean=overall_ok,
        criteria_total=criteria_total,
        criteria_with_evidence_when_partial_or_fail=round(rate_partial, 4),
        criteria_evidence_any=round(rate_any, 4),
        findings_total=findings_total,
        findings_with_verbatim_evidence=round(rate_f_ev, 4),
        findings_with_fca_reference=round(rate_f_fca, 4),
        dark_patterns_total=dp_total,
        dark_patterns_with_evidence=round(rate_dp, 4),
        vulnerability_gaps_total=vg_total,
        vulnerability_gaps_with_fca=round(rate_vg, 4),
        all_scores_in_0_10=scores_ok,
        rating_matches_score_bands=rating_ok,
        violations=violations,
        harness_score_0_100=harness,
    )
