"""Dark patterns / sludge detection — Groq structured output."""

from __future__ import annotations

import json
import logging

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from backend.pipeline.content_builder import build_crawl_markdown
from backend.pipeline.groq_llm import chat_groq, invoke_groq
from backend.pipeline.state import AuditState
from backend.schemas.audit import DarkPattern

load_dotenv()

logger = logging.getLogger(__name__)


class DarkPatternDetectionResult(BaseModel):
    patterns_found: list[DarkPattern] = Field(default_factory=list)
    no_patterns_detected: bool = False


_DARK_PROMPT = """You are a UX compliance expert detecting dark patterns \
and sludge on a UK financial services website under FCA Consumer Duty.

Detect ONLY patterns where you have EXACT verbatim evidence text from \
the content below. Do not infer or assume. Do not flag anything without \
a direct quote.

Pattern types to detect:
- urgency_manipulation: countdown timers, 'limited time', \
'only N left', artificial scarcity language
- confirm_shaming: guilt-trip opt-out language
- hidden_costs: fees only revealed late, asterisk pricing
- roach_motel: easy sign-up, difficult cancellation
- misdirection: language drawing attention away from important information
- pre_selection: pre-ticked boxes, default opt-ins
- false_urgency: fabricated social proof

Website content:
{content}

Respond with a JSON object matching the given schema."""


def dark_patterns_node(state: AuditState) -> dict:
    cr = state["crawl_result"]
    assert cr is not None
    content = build_crawl_markdown(cr, max_chars=14_000)

    llm = chat_groq()
    structured = llm.with_structured_output(DarkPatternDetectionResult)
    schema = json.dumps(
        DarkPatternDetectionResult.model_json_schema(),
        separators=(",", ":"),
    )
    prompt = _DARK_PROMPT.format(content=content) + f"\n\nSchema:\n{schema}"

    try:
        result = invoke_groq(structured, prompt)
        if not isinstance(result, DarkPatternDetectionResult):
            result = DarkPatternDetectionResult.model_validate(result)
        patterns = list(result.patterns_found)
    except Exception as e:  # noqa: BLE001
        logger.exception("Dark pattern detection failed")
        patterns = []

    return {"dark_patterns": patterns}
