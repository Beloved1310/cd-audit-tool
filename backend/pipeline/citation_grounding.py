"""Post-LLM citation grounding against retrieved FCA source lists."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence

from backend.schemas.audit import (
    ConfidenceLevel,
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


def apply_outcome_citation_grounding(
    outcome: OutcomeScore,
    allowed_citations: Sequence[str],
) -> tuple[OutcomeScore, str]:
    """Drop findings with ungrounded ``fca_reference``; downgrade confidence when any are removed."""
    if not outcome.findings:
        return outcome, ""

    grounded: list[Finding] = []
    removed = 0
    for finding in outcome.findings:
        if citation_is_grounded(finding.fca_reference, allowed_citations):
            grounded.append(finding)
        else:
            removed += 1
            logger.warning(
                "Removed ungrounded finding for %s: fca_reference=%r",
                outcome.outcome_name,
                finding.fca_reference,
            )

    if removed == 0:
        return outcome, ""

    note = (
        f"{removed} finding(s) removed: fca_reference not in retrieved FCA sources "
        f"({len(allowed_citations)} chunk(s) available)."
    )
    return outcome.model_copy(
        update={
            "findings": grounded,
            "confidence": downgrade_confidence(outcome.confidence),
        },
    ), note


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
