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
