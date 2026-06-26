"""Post-LLM citation grounding against retrieved FCA source lists."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence

from backend.schemas.audit import (
    ConfidenceLevel,
    CriterionScore,
    DarkPattern,
    Finding,
    OutcomeScore,
    VulnerabilityGap,
)

logger = logging.getLogger(__name__)

_NUMBERED_SOURCE_RE = re.compile(r"^\s*(\d+)\.\s*(.+)$")


def parse_numbered_fca_sources(fca_sources_text: str) -> list[str]:
    """Extract citation strings from the numbered ``fca_sources`` prompt block."""
    citations: list[str] = []
    for line in (fca_sources_text or "").splitlines():
        m = _NUMBERED_SOURCE_RE.match(line.strip())
        if m:
            cite = m.group(2).strip()
            if cite and "do not fabricate" not in cite.lower():
                citations.append(cite)
    return citations


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def base_document_label(citation: str) -> str:
    """``FG22/5, p.53`` → ``FG22/5``."""
    s = (citation or "").strip()
    if ", p." in s:
        return s.split(", p.", 1)[0].strip()
    if ", p" in s:
        return s.split(", p", 1)[0].strip()
    return s


def citation_is_grounded(reference: str, allowed_citations: Sequence[str]) -> bool:
    """True when *reference* matches a retrieved citation (exact or same document base)."""
    ref = (reference or "").strip()
    if not ref:
        return False
    if not allowed_citations:
        return False

    ref_norm = _normalize(ref)
    for allowed in allowed_citations:
        allowed = (allowed or "").strip()
        if not allowed:
            continue
        allowed_norm = _normalize(allowed)
        if ref_norm == allowed_norm:
            return True
        if ref_norm in allowed_norm or allowed_norm in ref_norm:
            return True
        base = _normalize(base_document_label(allowed))
        if base and (ref_norm == base or ref_norm.startswith(base) or base in ref_norm):
            return True
    return False


def downgrade_confidence(level: ConfidenceLevel) -> ConfidenceLevel:
    if level == ConfidenceLevel.HIGH:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


_CRITERIA_REVOKE_NOTE = (
    "Point revoked: fca_reference missing or not in retrieved FCA sources."
)


def ground_criteria_scores(
    criteria: list[CriterionScore],
    allowed_citations: Sequence[str],
) -> tuple[list[CriterionScore], int]:
    """Revoke awarded points when ``fca_reference`` is missing or not in retrieved sources."""
    grounded: list[CriterionScore] = []
    revoked = 0
    for row in criteria:
        if row.awarded_points <= 0:
            grounded.append(row)
            continue
        ref = (row.fca_reference or "").strip()
        if allowed_citations and ref and citation_is_grounded(ref, allowed_citations):
            grounded.append(row)
            continue
        revoked += 1
        logger.warning(
            "Revoked criterion %s for ungrounded fca_reference=%r",
            row.criterion_id,
            row.fca_reference,
        )
        evidence = row.evidence
        if _CRITERIA_REVOKE_NOTE not in evidence:
            evidence = f"{evidence} [{_CRITERIA_REVOKE_NOTE}]".strip() if evidence else _CRITERIA_REVOKE_NOTE
        grounded.append(
            row.model_copy(
                update={
                    "awarded_points": 0,
                    "met": False,
                    "fca_reference": "",
                    "evidence": evidence,
                },
            ),
        )
    return grounded, revoked


def apply_outcome_citation_grounding(
    outcome: OutcomeScore,
    allowed_citations: Sequence[str],
) -> tuple[OutcomeScore, str]:
    """Ground checklist rows and findings; downgrade confidence when any citations fail."""
    criteria, criteria_revoked = ground_criteria_scores(
        outcome.criteria_scores,
        allowed_citations,
    )
    outcome = outcome.model_copy(update={"criteria_scores": criteria})

    grounded_findings: list[Finding] = []
    findings_removed = 0
    for finding in outcome.findings:
        if citation_is_grounded(finding.fca_reference, allowed_citations):
            grounded_findings.append(finding)
        else:
            findings_removed += 1
            logger.warning(
                "Removed ungrounded finding for %s: fca_reference=%r",
                outcome.outcome_name,
                finding.fca_reference,
            )

    notes: list[str] = []
    if criteria_revoked:
        notes.append(
            f"{criteria_revoked} criterion point(s) revoked: fca_reference not in retrieved "
            f"FCA sources ({len(allowed_citations)} chunk(s) available).",
        )
    if findings_removed:
        notes.append(
            f"{findings_removed} finding(s) removed: fca_reference not in retrieved FCA sources "
            f"({len(allowed_citations)} chunk(s) available).",
        )

    if not notes:
        return outcome, ""

    updates: dict = {"findings": grounded_findings}
    if criteria_revoked or findings_removed:
        updates["confidence"] = downgrade_confidence(outcome.confidence)
    if criteria_revoked:
        updates["score"] = sum(c.awarded_points for c in criteria)
    return outcome.model_copy(update=updates), " ".join(notes)


def ground_dark_patterns(
    patterns: list[DarkPattern],
    allowed_citations: Sequence[str],
) -> list[DarkPattern]:
    """Keep patterns with grounded citations; drop those citing sources outside retrieval."""
    grounded: list[DarkPattern] = []
    for pattern in patterns:
        ref = (pattern.fca_reference or "").strip()
        if not ref:
            grounded.append(pattern)
            continue
        if citation_is_grounded(ref, allowed_citations):
            grounded.append(pattern)
        else:
            logger.warning(
                "Removed dark pattern with ungrounded fca_reference=%r",
                pattern.fca_reference,
            )
    return grounded


def ground_vulnerability_gaps(
    gaps: list[VulnerabilityGap],
    allowed_citations: Sequence[str],
) -> list[VulnerabilityGap]:
    """Keep vulnerability gaps only when ``fca_reference`` matches retrieved sources."""
    grounded: list[VulnerabilityGap] = []
    for gap in gaps:
        if citation_is_grounded(gap.fca_reference, allowed_citations):
            grounded.append(gap)
        else:
            logger.warning(
                "Removed vulnerability gap with ungrounded fca_reference=%r",
                gap.fca_reference,
            )
    return grounded


def count_grounded_citations(report) -> tuple[int, int]:
    """Return (items_with_non_empty_fca_reference, total_items) across report citation fields."""
    from backend.schemas.audit import AuditReport

    if not isinstance(report, AuditReport):
        return 0, 0

    total = 0
    cited = 0
    for outcome in report.outcomes:
        for criterion in outcome.criteria_scores:
            if criterion.awarded_points > 0:
                total += 1
                if (criterion.fca_reference or "").strip():
                    cited += 1
        for finding in outcome.findings:
            total += 1
            if (finding.fca_reference or "").strip():
                cited += 1
    for pattern in report.dark_patterns:
        total += 1
        if (pattern.fca_reference or "").strip():
            cited += 1
    for gap in report.vulnerability_gaps:
        total += 1
        if (gap.fca_reference or "").strip():
            cited += 1
    return cited, total
