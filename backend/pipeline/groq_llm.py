"""Shared Groq chat model — no Anthropic."""

from __future__ import annotations

import logging
import os
import random
import time
from typing import Any

from dotenv import load_dotenv
import httpx
from groq import RateLimitError
from langchain_core.runnables import Runnable
from langchain_groq import ChatGroq

load_dotenv()

logger = logging.getLogger(__name__)


def chat_groq() -> ChatGroq:
    """Llama 3.3 on Groq, temperature 0. ``GROQ_API_KEY`` from the environment (dotenv)."""
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        groq_api_key=os.environ.get("GROQ_API_KEY"),
    )


def _is_groq_rate_limit(exc: BaseException) -> bool:
    """True when the failure chain indicates HTTP 429 / Groq rate limiting."""
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        return True
    e: BaseException | None = exc
    for _ in range(10):
        if e is None:
            break
        if isinstance(e, RateLimitError):
            return True
        if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429:
            return True
        sc = getattr(e, "status_code", None)
        if sc == 429:
            return True
        e = getattr(e, "__cause__", None) or getattr(e, "__context__", None)
    low = str(exc).lower()
    return "429" in low or "too many requests" in low or "rate limit" in low


def invoke_groq(
    runnable: Runnable,
    input: Any,
    *,
    max_attempts: int = 8,
    base_delay_s: float = 1.25,
) -> Any:
    """Run ``runnable.invoke`` with exponential backoff on Groq 429 rate limits.

    Long audits issue many sequential LLM calls; Groq may throttle mid-pipeline.
    """
    last: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return runnable.invoke(input)
        except Exception as e:
            last = e
            if not _is_groq_rate_limit(e) or attempt >= max_attempts - 1:
                raise
            delay = base_delay_s * (2**attempt) + random.uniform(0, 0.75)
            logger.warning(
                "Groq rate limited (attempt %s/%s); retrying in %.1fs",
                attempt + 1,
                max_attempts,
                delay,
            )
            time.sleep(delay)
    assert last is not None
    raise last
