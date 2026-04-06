"""Criteria definitions (0–10 points per outcome), crawl confidence, and helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass

from backend.schemas.audit import ConfidenceLevel


@dataclass(frozen=True)
class CriterionDef:
    """Static checklist row used in prompts and compile-time validation."""

    criterion_id: int
    name: str
    max_points: int


UNDERSTANDING_CRITERIA: tuple[CriterionDef, ...] = tuple(
    CriterionDef(i, name, 1)
    for i, name in enumerate(
        [
            "Key product/service terms explained in plain language (not only legal jargon).",
            "Material risks, limitations, or conditions are clearly signposted.",
            "Costs, charges, or interest are discoverable and explained before commitment where relevant.",
            "Important deadlines or consequences of actions are stated clearly.",
            "Navigation and labels help users find information without unnecessary complexity.",
            "Marketing or promotional content is balanced with clear risk/cost context where applicable.",
            "Key documents or terms are available or clearly described.",
            "Language appears appropriate for a broad retail audience on core pages.",
            "Contact or next-step paths are obvious where a decision is implied.",
            "No evidence of critical information hidden behind unnecessary clicks only.",
        ],
        start=1,
    )
)

SUPPORT_CRITERIA: tuple[CriterionDef, ...] = tuple(
    CriterionDef(i, name, 1)
    for i, name in enumerate(
        [
            "Customer service or help contact options are easy to find.",
            "Support hours or response expectations are stated where channels are advertised.",
            "A complaints or feedback process is described and reachable.",
            "Guidance for users struggling financially or in arrears is referenced where relevant.",
            "Accessibility or reasonable adjustment information is present or linked.",
            "Vulnerable customer support or additional help is mentioned where expected.",
            "Self-serve help (FAQs, guides) is organised for common issues.",
            "Escalation or dispute paths beyond first-line support are indicated if applicable.",
            "Safety or fraud reporting guidance is available where relevant.",
            "Key support journeys are not obviously obscured in crawled content.",
        ],
        start=1,
    )
)

# PRIN 2A.2 — aligned to FG22/5 (products & services outcome) / PS22/9 rules framework
PRODUCTS_SERVICES_CRITERIA: tuple[CriterionDef, ...] = tuple(
    CriterionDef(i, name, 1)
    for i, name in enumerate(
        [
            "Product/service purpose and main features are clear for the retail audience.",
            "Target market or who the product is for is stated or inferable without jargon.",
            "Material risks, limitations, and exclusions are described before application or sale.",
            "Product design or governance signals (e.g. reviews, fair value) are visible where relevant.",
            "Vulnerable customers: adaptations or considerations in product design are referenced.",
            "Distribution/channel fit: information matches how the product is sold (online, advised, etc.).",
            "Closed-book / legacy or product changes are explained if referenced on site.",
            "Cross-selling or bundling is transparent where products are combined.",
            "Key documents (summary, terms) are linked or described for core products.",
            "Conflicts or incentives are disclosed where the site discusses advice or sales.",
        ],
        start=1,
    )
)

# PRIN 2A.3 — aligned to FG22/5 (price & value outcome) / PS22/9
PRICE_VALUE_CRITERIA: tuple[CriterionDef, ...] = tuple(
    CriterionDef(i, name, 1)
    for i, name in enumerate(
        [
            "Total cost of ownership or main charges are discoverable on product pages.",
            "Interest rates, APR, or price basis are shown where relevant to credit or savings.",
            "Fees (ongoing, exit, early repayment) are listed or clearly signposted.",
            "Fair value or value-for-money framing is consistent with price information.",
            "Introductory or promotional pricing shows what happens after the offer ends.",
            "Comparison with alternatives or benchmarks is offered where the Duty expects clarity.",
            "Price changes and how customers are informed are described if relevant.",
            "Bundled benefits vs paid features are distinguishable in price messaging.",
            "Currency, timing, and frequency of charges are clear (e.g. monthly vs annual).",
            "Sludge indicators: no evidence that fees are hidden behind unnecessary steps only.",
        ],
        start=1,
    )
)


def criteria_json(defs: tuple[CriterionDef, ...]) -> str:
    return json.dumps(
        [{"id": d.criterion_id, "name": d.name, "max_points": d.max_points} for d in defs],
        ensure_ascii=False,
        indent=2,
    )


def max_points(defs: tuple[CriterionDef, ...]) -> int:
    return sum(d.max_points for d in defs)


def confidence_level(pages_crawled: int, words_analysed: int) -> ConfidenceLevel:
    """HIGH / MEDIUM / LOW from crawl depth (Consumer Duty audit confidence)."""
    if pages_crawled >= 10 and words_analysed >= 5000:
        return ConfidenceLevel.HIGH
    if pages_crawled < 5 or words_analysed < 2000:
        return ConfidenceLevel.LOW
    return ConfidenceLevel.MEDIUM


def confidence_note(pages_crawled: int, words_analysed: int) -> str:
    """Short explanation for OutcomeScore.confidence_note."""
    parts: list[str] = []
    if pages_crawled < 10:
        parts.append(f"Only {pages_crawled} page(s) crawled (fewer than 10).")
    if words_analysed < 5000:
        parts.append(f"Only {words_analysed} words analysed (under 5000).")
    if not parts:
        return "Crawl depth meets HIGH confidence thresholds (10+ pages and 5000+ words)."
    return " ".join(parts)
