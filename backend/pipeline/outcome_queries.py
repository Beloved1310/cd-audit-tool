"""Natural-language FCA retrieval queries (one per pipeline outcome).

Hybrid search (BM25 + vector) handles exact rule references; queries stay semantic.
"""

from __future__ import annotations

PRODUCTS_SERVICES_QUERY = (
    "Consumer Duty products and services outcome: target market, product design, "
    "fair value, product governance, distribution, and closed-book products."
)

PRICE_VALUE_QUERY = (
    "Consumer Duty price and value outcome: fees, charges, APR, fair value, "
    "total cost of product, and transparency for retail customers."
)

CONSUMER_UNDERSTANDING_QUERY = (
    "Consumer Duty consumer understanding outcome: plain language, risk warnings, "
    "informed decisions, and balanced promotional communications."
)

CONSUMER_SUPPORT_QUERY = (
    "Consumer Duty consumer support outcome: complaints, contact channels, "
    "accessibility, financial difficulty, and ease of exit."
)

VULNERABILITY_QUERY = (
    "Vulnerable customers under Consumer Duty: reasonable adjustments, "
    "financial difficulty support, accessibility, and signposting obligations."
)

DARK_PATTERNS_QUERY = (
    "Consumer Duty sludge and dark patterns: deceptive design, hidden fees, "
    "unfair friction, urgency manipulation, and opt-out difficulty."
)

# Dedicated query for PS22/9 retrieval smoke tests (policy statement is a distinct doc).
PS22_POLICY_QUERY = (
    "FCA Consumer Duty policy statement PS22/9: rules framework and firm obligations."
)

OUTCOME_QUERIES: dict[str, str] = {
    "Products & Services": PRODUCTS_SERVICES_QUERY,
    "Price & Value": PRICE_VALUE_QUERY,
    "Consumer Understanding": CONSUMER_UNDERSTANDING_QUERY,
    "Consumer Support": CONSUMER_SUPPORT_QUERY,
    "Vulnerability": VULNERABILITY_QUERY,
    "Dark Patterns": DARK_PATTERNS_QUERY,
}

# Thematic retrieval aspects for non-checklist pipeline stages (parallel to per-criterion queries).
DARK_PATTERNS_ASPECTS: tuple[str, ...] = (
    "hidden fees, drip pricing, and unclear total cost",
    "urgency, scarcity, and countdown pressure tactics",
    "difficult cancellation, opt-out friction, and roach-motel patterns",
    "misleading defaults, pre-ticked boxes, and deceptive choice architecture",
    "confirmshaming and guilt-based nudges",
    "buried terms, misdirection, and important information obscured",
    "unfair friction in complaints, support, or exit journeys",
    "bundling and cross-sell pressure without clear consent",
    "comparison and anchoring tricks that distort value",
    "sludge in application or onboarding flows",
)

VULNERABILITY_ASPECTS: tuple[str, ...] = (
    "reasonable adjustments and accessibility for disabled customers",
    "financial difficulty, forbearance, and arrears support",
    "mental capacity, cognitive vulnerability, and clear communications",
    "signposting to specialist vulnerability or hardship support",
    "digital accessibility, assistive technology, and channel choice",
    "vulnerable customer policies and public commitments",
    "financial abuse, coercion, and third-party assistance",
    "bereavement, life events, and temporary vulnerability",
    "language, literacy, and non-standard communication needs",
    "proactive identification and tailored support for vulnerable customers",
)

OUTCOME_ASPECTS: dict[str, tuple[str, ...]] = {
    "Dark Patterns": DARK_PATTERNS_ASPECTS,
    "Vulnerability": VULNERABILITY_ASPECTS,
}


def criterion_query(outcome_name: str, criterion_name: str) -> str:
    """Build a targeted retrieval query for one checklist criterion."""
    base = OUTCOME_QUERIES.get(outcome_name, outcome_name)
    return f"{base} Checklist criterion: {criterion_name}"


def aspect_query(outcome_name: str, aspect: str) -> str:
    """Build a targeted retrieval query for one detection theme."""
    base = OUTCOME_QUERIES.get(outcome_name, outcome_name)
    return f"{base} Focus: {aspect}"


def criterion_queries_for_outcome(outcome_name: str) -> tuple[str, ...]:
    """Ten targeted queries — one per criterion ID for an outcome."""
    from backend.pipeline.scorer import criteria_defs_for_outcome

    defs = criteria_defs_for_outcome(outcome_name)
    return tuple(criterion_query(outcome_name, d.name) for d in defs)


def aspect_queries_for_outcome(outcome_name: str) -> tuple[str, ...]:
    """Thematic queries for checklist-free stages (dark patterns, vulnerability)."""
    aspects = OUTCOME_ASPECTS.get(outcome_name)
    if not aspects:
        raise ValueError(f"No thematic aspects for outcome: {outcome_name!r}")
    return tuple(aspect_query(outcome_name, aspect) for aspect in aspects)


def retrieval_queries_for_outcome(outcome_name: str, *, per_aspect_enabled: bool | None = None) -> tuple[str, ...]:
    """Queries for an outcome: per-criterion/aspect when enabled, else one outcome query."""
    from backend.config import get_settings
    from backend.pipeline.scorer import OUTCOME_CRITERIA

    settings = get_settings()
    multi = (
        settings.rag_per_criterion_enabled
        if per_aspect_enabled is None
        else per_aspect_enabled
    )
    if multi:
        if outcome_name in OUTCOME_CRITERIA:
            return criterion_queries_for_outcome(outcome_name)
        if outcome_name in OUTCOME_ASPECTS:
            return aspect_queries_for_outcome(outcome_name)
    query = OUTCOME_QUERIES.get(outcome_name)
    if not query:
        raise ValueError(f"No FCA retrieval query for outcome: {outcome_name!r}")
    return (query,)
