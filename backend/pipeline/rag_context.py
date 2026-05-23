"""Shared FCA retrieval helpers for pipeline nodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.config import get_settings
from backend.ingestion.fca_loader import get_sources_from_docs, merge_retrieved_docs
from backend.pipeline.content_builder import format_fca_sources_numbered, truncate_chars


@dataclass(frozen=True)
class FcaPromptContext:
    """Numbered sources list + concatenated chunk text for LLM prompts."""

    fca_sources: str
    fca_context: str
    chunk_count: int


def build_fca_prompt_context(
    retriever: Any,
    *queries: str,
    max_chunks: int | None = None,
    max_context_chars: int | None = None,
    k_per_query: int | None = None,
) -> FcaPromptContext:
    """
    Run one or more similarity queries, dedupe chunks, and format for prompts.

    Uses ``Settings.rag_retrieval_k`` per query unless ``k_per_query`` is set.
    """
    settings = get_settings()
    k = k_per_query if k_per_query is not None else settings.rag_retrieval_k
    cap = max_chunks if max_chunks is not None else settings.rag_max_chunks
    char_limit = (
        max_context_chars if max_context_chars is not None else settings.rag_context_max_chars
    )

    if not queries:
        raise ValueError("build_fca_prompt_context requires at least one query")

    docs = merge_retrieved_docs(retriever, *queries, k_each=k, max_docs=cap)
    sources = get_sources_from_docs(docs)
    return FcaPromptContext(
        fca_sources=format_fca_sources_numbered(sources),
        fca_context=truncate_chars(
            "\n\n".join(d.page_content for d in docs),
            char_limit,
        ),
        chunk_count=len(docs),
    )
