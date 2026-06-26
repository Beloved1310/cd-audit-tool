"""Dark patterns / sludge detection — Groq structured output + FCA RAG."""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field

from backend.observability import stage_timer
from backend.pipeline.content_builder import build_crawl_markdown
from backend.pipeline.groq_llm import chat_groq, invoke_groq
from backend.pipeline.prompt_loader import load_prompt_text
from backend.pipeline.citation_grounding import ground_dark_patterns
from backend.pipeline.outcome_rag import retrieve_fca_for_outcome
from backend.pipeline.state import AuditState
from backend.schemas.audit import DarkPattern

logger = logging.getLogger(__name__)

_OUTCOME_NAME = "Dark Patterns"


class DarkPatternDetectionResult(BaseModel):
    patterns_found: list[DarkPattern] = Field(default_factory=list)
    no_patterns_detected: bool = False


def dark_patterns_node(state: AuditState) -> dict:
    cr = state["crawl_result"]
    retriever = state["retriever"]
    assert cr is not None

    with stage_timer("dark_patterns_prepare"):
        content = build_crawl_markdown(cr, max_chars=14_000)

    with stage_timer("dark_patterns_retrieve"):
        fca = retrieve_fca_for_outcome(retriever, _OUTCOME_NAME)

    llm = chat_groq()
    structured = llm.with_structured_output(DarkPatternDetectionResult)
    schema = json.dumps(
        DarkPatternDetectionResult.model_json_schema(),
        separators=(",", ":"),
    )
    template = load_prompt_text("dark_patterns.txt")
    prompt = template.format(
        fca_sources=fca.fca_sources,
        fca_context=fca.fca_context,
        content=content,
    ) + f"\n\nSchema:\n{schema}"

    try:
        with stage_timer("dark_patterns_llm"):
            result = invoke_groq(structured, prompt)
        if not isinstance(result, DarkPatternDetectionResult):
            result = DarkPatternDetectionResult.model_validate(result)
        patterns = ground_dark_patterns(list(result.patterns_found), fca.allowed_citations)
    except Exception as e:  # noqa: BLE001
        logger.exception("Dark pattern detection failed")
        patterns = []

    return {"dark_patterns": patterns}
