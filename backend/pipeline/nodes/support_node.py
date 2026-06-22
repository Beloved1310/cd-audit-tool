"""Consumer Support outcome — structured LLM + FCA RAG (Groq)."""

from __future__ import annotations

import json
import logging

from backend.observability import stage_timer
from backend.pipeline.content_builder import build_crawl_markdown
from backend.pipeline.groq_llm import chat_groq, invoke_groq
from backend.pipeline.llm_errors import friendly_eval_error
from backend.pipeline.outcome_rag import finalize_outcome_score, retrieve_fca_for_outcome
from backend.pipeline.prompt_loader import load_prompt_text
from backend.pipeline.scorer import SUPPORT_CRITERIA, format_criteria_for_prompt
from backend.pipeline.state import AuditState
from backend.security.prompt_injection import sanitise_website_content
from backend.schemas.audit import ConfidenceLevel, OutcomeScore, RAGRating
from backend.schemas.llm_io import OutcomeGroqOutput, outcome_from_groq_output

logger = logging.getLogger(__name__)

_OUTCOME_NAME = "Consumer Support"


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


def support_node(state: AuditState) -> dict:
    cr = state["crawl_result"]
    retriever = state["retriever"]
    assert cr is not None

    with stage_timer("support_prepare"):
        website_content = sanitise_website_content(build_crawl_markdown(cr, max_chars=10_000))
    with stage_timer("support_retrieve"):
        fca = retrieve_fca_for_outcome(retriever, _OUTCOME_NAME)

    template = load_prompt_text("support.txt")
    output_schema = json.dumps(
        OutcomeGroqOutput.model_json_schema(),
        separators=(",", ":"),
    )
    formatted_prompt = template.format(
        fca_sources=fca.fca_sources,
        fca_context=fca.fca_context,
        scoring_criteria=format_criteria_for_prompt(SUPPORT_CRITERIA),
        website_content=website_content,
        output_schema=output_schema,
    )

    llm = chat_groq()
    structured = llm.with_structured_output(OutcomeGroqOutput)
    try:
        with stage_timer("support_llm"):
            raw = invoke_groq(structured, formatted_prompt)
        if not isinstance(raw, OutcomeGroqOutput):
            raw = OutcomeGroqOutput.model_validate(raw)
        result = outcome_from_groq_output(raw)
    except Exception as e:  # noqa: BLE001
        logger.exception("Support structured output failed")
        result = _failed_outcome(e)
    else:
        result = finalize_outcome_score(
            result,
            outcome_name=_OUTCOME_NAME,
            criteria_defs=SUPPORT_CRITERIA,
            fca=fca,
            crawl=cr,
            scope_note="",
        )

    return {"support_score": result}
