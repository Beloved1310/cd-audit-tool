"""Consumer Understanding outcome — structured LLM + FCA RAG (Groq)."""

from __future__ import annotations

import json
import logging

from backend.ingestion.fca_loader import get_sources_from_docs
from backend.observability import stage_timer
from backend.pipeline.content_builder import (
    build_crawl_markdown,
    format_fca_sources_numbered,
    truncate_chars,
)
from backend.pipeline.llm_errors import friendly_eval_error
from backend.pipeline.groq_llm import chat_groq, invoke_groq
from backend.pipeline.prompt_loader import load_prompt_text
from backend.pipeline.scorer import confidence_level, confidence_note
from backend.pipeline.state import AuditState
from backend.security.prompt_injection import sanitise_website_content
from backend.schemas.audit import ConfidenceLevel, OutcomeScore, RAGRating
from backend.schemas.llm_io import OutcomeGroqOutput, outcome_from_groq_output

logger = logging.getLogger(__name__)

_QUERY = (
    "consumer understanding plain language risk warnings "
    "fee disclosure informed decisions promotional balance"
)
_OUTCOME_NAME = "Consumer Understanding"


def _failed_outcome(exc: Exception) -> OutcomeScore:
    return OutcomeScore(
        outcome_name=_OUTCOME_NAME,
        rating=RAGRating.RED,
        score=0,
        confidence=ConfidenceLevel.LOW,
        confidence_note="Scoring did not complete for this outcome.",
        summary=friendly_eval_error(exc),
        criteria_scores=[],
    )


def understanding_node(state: AuditState) -> dict:
    cr = state["crawl_result"]
    retriever = state["retriever"]
    assert cr is not None

    with stage_timer("understanding_prepare"):
        website_content = sanitise_website_content(build_crawl_markdown(cr, max_chars=10_000))
    with stage_timer("understanding_retrieve"):
        docs = retriever.invoke(_QUERY)[:4]
    sources = get_sources_from_docs(docs)
    fca_context = truncate_chars(
        "\n\n".join(d.page_content for d in docs),
        4_000,
    )
    fca_sources = format_fca_sources_numbered(sources)

    template = load_prompt_text("understanding.txt")
    output_schema = json.dumps(
        OutcomeGroqOutput.model_json_schema(),
        separators=(",", ":"),
    )
    formatted_prompt = template.format(
        fca_sources=fca_sources,
        fca_context=fca_context,
        website_content=website_content,
        output_schema=output_schema,
    )

    llm = chat_groq()
    structured = llm.with_structured_output(OutcomeGroqOutput)
    try:
        with stage_timer("understanding_llm"):
            raw = invoke_groq(structured, formatted_prompt)
        if not isinstance(raw, OutcomeGroqOutput):
            raw = OutcomeGroqOutput.model_validate(raw)
        result = outcome_from_groq_output(raw)
    except Exception as e:  # noqa: BLE001
        logger.exception("Understanding structured output failed")
        result = _failed_outcome(e)
    else:
        conf = confidence_level(len(cr.pages), cr.total_words)
        note = confidence_note(len(cr.pages), cr.total_words)
        result = result.model_copy(
            update={
                "outcome_name": _OUTCOME_NAME,
                "confidence": conf,
                "confidence_note": note,
            },
        )

    return {"understanding_score": result}
