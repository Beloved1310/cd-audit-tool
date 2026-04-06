"""User-facing messages when Groq / structured output fails."""

from __future__ import annotations


def friendly_eval_error(exc: Exception) -> str:
    """Short, readable summary for audit UI (no raw stack traces)."""
    raw = str(exc)
    low = raw.lower()
    if "413" in raw or "too large" in low or (
        "token" in low and ("limit" in low or "minute" in low or "tpm" in low)
    ):
        return (
            "Scoring could not run because the request exceeded the model "
            "provider’s current size or rate limits. Try again in a minute, or "
            "audit a site with fewer pages."
        )
    if "429" in raw or "rate limit" in low:
        return (
            "The model provider rate limit was reached. Please wait a minute "
            "and try again."
        )
    if len(raw) > 300:
        return f"Scoring could not complete: {raw[:300]}…"
    return f"Scoring could not complete: {raw}"
