"""Scoring accuracy metrics: compare pipeline AuditReport against expert ground truth.

This is the module that produces a real accuracy number.  It does not measure
whether the pipeline's output is well-formed (that is the harness in metrics.py).
It measures whether the *scores* match what a human expert would assign.

Key metrics:
  - Mean Absolute Error (MAE) per outcome and overall
  - Rating agreement % (RED / AMBER / GREEN match rate)
  - Per-criterion agreement rate — shows *which* criteria the pipeline gets wrong most
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.evaluation.ground_truth import GroundTruthLabel, _REQUIRED_OUTCOMES
from backend.schemas.audit import AuditReport, AuditStatus, RAGRating, rating_from_score_10


@dataclass
class CriterionAccuracy:
    criterion_id: int
    gt_awarded: int          # 0 or 1 from expert label
    pipeline_awarded: int    # 0 or 1 from pipeline criteria_scores
    agrees: bool             # gt_awarded == pipeline_awarded


@dataclass
class OutcomeAccuracy:
    outcome_name: str
    gt_score: int
    pipeline_score: int
    abs_error: int
    gt_rating: RAGRating
    pipeline_rating: RAGRating
    rating_agrees: bool
    criteria: list[CriterionAccuracy] = field(default_factory=list)
    criterion_agreement_rate: float = 0.0


@dataclass
class SiteAccuracy:
    site_id: str
    url: str
    outcomes: dict[str, OutcomeAccuracy]
    mean_abs_error: float              # average |gt - pipeline| across four outcomes
    rating_agreement_pct: float        # % of outcomes where rating matches
    overall_gt_score: int
    overall_pipeline_score: int
    overall_abs_error: int


@dataclass
class AccuracySummary:
    """Aggregate accuracy across multiple sites."""
    site_count: int
    per_outcome_mae: dict[str, float]   # outcome_name → mean |error| across sites
    overall_mae: float
    rating_agreement_pct: float
    # (outcome_name, criterion_id) → error_rate across sites — highest = pipeline's blind spots
    worst_criteria: list[tuple[str, int, float]]
    site_results: list[SiteAccuracy] = field(default_factory=list)


def _pipeline_outcome_score(report: AuditReport, outcome_name: str) -> int | None:
    for o in report.outcomes:
        if o.outcome_name == outcome_name:
            return o.score
    return None


def _pipeline_criterion_awarded(report: AuditReport, outcome_name: str, criterion_id: int) -> int | None:
    for o in report.outcomes:
        if o.outcome_name == outcome_name:
            for c in o.criteria_scores:
                if c.criterion_id == criterion_id:
                    return min(1, c.awarded_points)
    return None


def compare_to_ground_truth(
    report: AuditReport,
    label: GroundTruthLabel,
) -> SiteAccuracy:
    """Compute per-outcome and overall accuracy for one site."""
    if report.status != AuditStatus.COMPLETE:
        raise ValueError(
            f"Cannot compare accuracy: report status is {report.status!r}, need COMPLETE"
        )

    outcome_results: dict[str, OutcomeAccuracy] = {}

    for outcome_name in _REQUIRED_OUTCOMES:
        gt_score = label.outcome_score(outcome_name)
        pipeline_score = _pipeline_outcome_score(report, outcome_name)
        if pipeline_score is None:
            raise ValueError(f"Pipeline report missing outcome: {outcome_name!r}")

        gt_rating = rating_from_score_10(gt_score)
        pipeline_rating = rating_from_score_10(pipeline_score)

        criteria_acc: list[CriterionAccuracy] = []
        outcome_label = label.outcomes[outcome_name]
        for cid_str, crit_label in outcome_label.criteria.items():
            cid = int(cid_str)
            pipeline_awarded = _pipeline_criterion_awarded(report, outcome_name, cid)
            if pipeline_awarded is None:
                continue
            agrees = pipeline_awarded == crit_label.awarded
            criteria_acc.append(
                CriterionAccuracy(
                    criterion_id=cid,
                    gt_awarded=crit_label.awarded,
                    pipeline_awarded=pipeline_awarded,
                    agrees=agrees,
                ),
            )

        expected_criteria = len(outcome_label.criteria)
        if len(criteria_acc) < expected_criteria:
            missing = expected_criteria - len(criteria_acc)
            raise ValueError(
                f"{outcome_name}: pipeline report missing {missing} criterion row(s) "
                f"(have {len(criteria_acc)}/{expected_criteria}). "
                "Ensure prompts use the fixed scorer.py checklist (IDs 1–10).",
            )

        agreement_rate = (
            sum(1 for c in criteria_acc if c.agrees) / len(criteria_acc)
            if criteria_acc else 0.0
        )

        outcome_results[outcome_name] = OutcomeAccuracy(
            outcome_name=outcome_name,
            gt_score=gt_score,
            pipeline_score=pipeline_score,
            abs_error=abs(pipeline_score - gt_score),
            gt_rating=gt_rating,
            pipeline_rating=pipeline_rating,
            rating_agrees=(gt_rating == pipeline_rating),
            criteria=criteria_acc,
            criterion_agreement_rate=round(agreement_rate, 4),
        )

    errors = [o.abs_error for o in outcome_results.values()]
    rating_matches = [o.rating_agrees for o in outcome_results.values()]
    gt_overall = label.overall_score()
    pipeline_overall = report.overall_score or 0

    return SiteAccuracy(
        site_id=label.site_id,
        url=label.url,
        outcomes=outcome_results,
        mean_abs_error=round(sum(errors) / len(errors), 3),
        rating_agreement_pct=round(sum(rating_matches) / len(rating_matches) * 100, 1),
        overall_gt_score=gt_overall,
        overall_pipeline_score=pipeline_overall,
        overall_abs_error=abs(pipeline_overall - gt_overall),
    )


def summarise_accuracy(site_results: list[SiteAccuracy]) -> AccuracySummary:
    """Aggregate accuracy across multiple sites into a single summary."""
    if not site_results:
        return AccuracySummary(
            site_count=0,
            per_outcome_mae={},
            overall_mae=0.0,
            rating_agreement_pct=0.0,
            worst_criteria=[],
        )

    per_outcome_errors: dict[str, list[float]] = {o: [] for o in _REQUIRED_OUTCOMES}
    rating_agrees: list[bool] = []
    criterion_errors: dict[tuple[str, int], list[int]] = {}

    for site in site_results:
        for name, oa in site.outcomes.items():
            per_outcome_errors[name].append(oa.abs_error)
            rating_agrees.append(oa.rating_agrees)
            for ca in oa.criteria:
                key = (name, ca.criterion_id)
                criterion_errors.setdefault(key, []).append(0 if ca.agrees else 1)

    per_outcome_mae = {
        name: round(sum(errs) / len(errs), 3)
        for name, errs in per_outcome_errors.items()
        if errs
    }
    overall_mae = round(
        sum(site.mean_abs_error for site in site_results) / len(site_results), 3
    )
    overall_rating_pct = round(sum(rating_agrees) / len(rating_agrees) * 100, 1)

    worst = sorted(
        [(name, cid, round(sum(errs) / len(errs), 3)) for (name, cid), errs in criterion_errors.items()],
        key=lambda x: x[2],
        reverse=True,
    )[:10]

    return AccuracySummary(
        site_count=len(site_results),
        per_outcome_mae=per_outcome_mae,
        overall_mae=overall_mae,
        rating_agreement_pct=overall_rating_pct,
        worst_criteria=worst,
        site_results=site_results,
    )


def format_accuracy_report(summary: AccuracySummary) -> str:
    """Human-readable accuracy report for CLI output."""
    lines = [
        f"Accuracy summary across {summary.site_count} site(s)",
        f"  Overall MAE:          {summary.overall_mae:.2f} points (0–10 scale)",
        f"  Rating agreement:     {summary.rating_agreement_pct:.1f}% (RED/AMBER/GREEN match)",
        "",
        "  Per-outcome MAE:",
    ]
    for name, mae in summary.per_outcome_mae.items():
        lines.append(f"    {name:<30} {mae:.2f}")

    if summary.worst_criteria:
        lines += ["", "  Highest-error criteria (pipeline vs expert disagreement rate):"]
        for outcome, cid, rate in summary.worst_criteria:
            lines.append(f"    {outcome} criterion {cid:>2}: {rate:.0%} disagreement")

    return "\n".join(lines)
