"""Run user-defined journey: fetch each URL, analyse friction + dark patterns per step."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from backend.crawler.site_crawler import fetch_single_page
from backend.ingestion.fca_loader import get_sources_from_docs
from backend.pipeline.content_builder import format_fca_sources_numbered, truncate_chars
from backend.pipeline.groq_llm import chat_groq, invoke_groq
from backend.pipeline.llm_errors import friendly_eval_error
from backend.schemas.audit import DarkPattern
from backend.schemas.journey import (
    JourneyReport,
    JourneyStepInput,
    JourneyStepLLMOutput,
    JourneyStepResult,
)

logger = logging.getLogger(__name__)

_JOURNEY_RAG_QUERY = (
    "FCA consumer duty sludge friction dark patterns fair treatment "
    "vulnerable customers clarity pricing support journey"
)

_MAX_STEP_CHARS = 6_000
JOURNEY_MAX_STEPS = 10
JOURNEY_MIN_STEPS = 2


def _prompt_for_step(
    *,
    step_index: int,
    total: int,
    label: str,
    url: str,
    title: str,
    page_text: str,
    fca_context: str,
    fca_sources: str,
    output_schema: str,
) -> str:
    lab = label.strip() or f"Step {step_index + 1}"
    return f"""You are an FCA Consumer Duty and digital journey expert analysing ONE step \
in a UK financial services customer path.

Step {step_index + 1} of {total}: "{lab}"
Page URL: {url}
Page title: {title}

CITATION RULE for regulatory strings: use only these numbered FCA source labels if you mention rules (otherwise omit):
{fca_sources}

Relevant FCA excerpt (may be partial):
{fca_context}

Page content to analyse:
{page_text}

YOUR TASK (this page only — do not assume other pages):
1. friction_flag_slugs: snake_case labels for negative friction or sludge you can support with evidence \
on this page. Examples: unclear_pricing, buried_key_info, high_cognitive_load, confusing_cta, \
forced_navigation, unexpected_fee_signal, accessibility_friction, imbalance_promo_vs_risk.
2. friction_evidence_quotes: up to 3 SHORT verbatim quotes from the page text above (exact substrings).
3. dark_patterns: only if EXACT evidence exists on this page. Allowed pattern_type values: \
urgency_manipulation, confirm_shaming, hidden_costs, roach_motel, misdirection, pre_selection, false_urgency. \
Each must include evidence_text copied verbatim from the page. Set page_url to: {url}
4. step_summary: 2–4 sentences on how this step helps or hinders a typical retail customer.

If nothing negative applies, use empty lists and a neutral summary.

Respond with JSON matching this schema exactly:
{output_schema}
"""


def _analyse_step_llm(
    *,
    step_index: int,
    total: int,
    inp: JourneyStepInput,
    page_title: str,
    page_text: str,
    fca_context: str,
    fca_sources: str,
) -> JourneyStepLLMOutput:
    schema = json.dumps(
        JourneyStepLLMOutput.model_json_schema(),
        separators=(",", ":"),
    )
    truncated = truncate_chars(page_text, _MAX_STEP_CHARS)
    prompt = _prompt_for_step(
        step_index=step_index,
        total=total,
        label=inp.label,
        url=inp.url.strip(),
        title=page_title,
        page_text=truncated,
        fca_context=fca_context,
        fca_sources=fca_sources,
        output_schema=schema,
    )
    llm = chat_groq()
    structured = llm.with_structured_output(JourneyStepLLMOutput)
    try:
        out = invoke_groq(structured, prompt)
        if not isinstance(out, JourneyStepLLMOutput):
            out = JourneyStepLLMOutput.model_validate(out)
    except Exception as e:  # noqa: BLE001
        logger.exception("Journey step LLM failed for %s", inp.url)
        return JourneyStepLLMOutput(
            step_summary=friendly_eval_error(e),
        )

    # Ensure dark patterns always reference the current step URL.
    fixed_dps: list[DarkPattern] = []
    for dp in out.dark_patterns:
        fixed_dps.append(
            dp.model_copy(
                update={"page_url": inp.url.strip()},
            ),
        )
    return out.model_copy(update={"dark_patterns": fixed_dps})


def run_journey(
    steps: list[JourneyStepInput],
    retriever: Any,
    http_client: Any | None = None,
) -> JourneyReport:
    if len(steps) < JOURNEY_MIN_STEPS:
        raise ValueError(f"At least {JOURNEY_MIN_STEPS} steps are required")
    if len(steps) > JOURNEY_MAX_STEPS:
        raise ValueError(f"At most {JOURNEY_MAX_STEPS} steps allowed")

    docs = retriever.invoke(_JOURNEY_RAG_QUERY)[:4]
    sources = get_sources_from_docs(docs)
    fca_context = truncate_chars(
        "\n\n".join(d.page_content for d in docs),
        3_000,
    )
    fca_sources = format_fca_sources_numbered(sources)

    results: list[JourneyStepResult] = []
    total = len(steps)

    for i, inp in enumerate(steps):
        url = inp.url.strip()
        label = inp.label.strip() or f"Step {i + 1}"
        page, err = fetch_single_page(url, http_client=http_client)
        if page is None:
            results.append(
                JourneyStepResult(
                    step_index=i,
                    label=label,
                    url=url,
                    fetch_error=err or "Could not load page",
                    step_summary="Page could not be analysed.",
                ),
            )
            continue

        analysis = _analyse_step_llm(
            step_index=i,
            total=total,
            inp=inp,
            page_title=page.title,
            page_text=page.content,
            fca_context=fca_context,
            fca_sources=fca_sources,
        )

        results.append(
            JourneyStepResult(
                step_index=i,
                label=label,
                url=page.url,
                page_title=page.title,
                word_count=page.word_count,
                friction_flags=list(analysis.friction_flag_slugs),
                friction_evidence_quotes=list(analysis.friction_evidence_quotes),
                dark_patterns=list(analysis.dark_patterns),
                step_summary=analysis.step_summary.strip() or "No summary returned.",
            ),
        )

    return JourneyReport(
        generated_at=datetime.now(timezone.utc),
        steps=results,
    )
