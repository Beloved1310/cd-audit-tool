"""Format crawled content and FCA retrieval payloads for prompts."""

from __future__ import annotations

import json

from backend.crawler.site_crawler import CrawlResult


def truncate_chars(text: str, max_chars: int, *, suffix: str = "\n\n[... truncated for model size limits ...]") -> str:
    """Trim long strings so LLM prompts stay within provider token limits."""
    if max_chars < 48:
        return text[: max(0, max_chars)]
    if len(text) <= max_chars:
        return text
    take = max_chars - len(suffix)
    if take < 1:
        return text[:max_chars]
    return text[:take].rstrip() + suffix


def build_crawl_markdown(result: CrawlResult, *, max_chars: int | None = 12_000) -> str:
    """Concatenate crawled pages as ``## url`` + content (per pipeline spec)."""
    parts: list[str] = []
    for page in result.pages:
        parts.append(f"\n\n## {page.url}\n\n{page.content}")
    blob = "".join(parts).strip() or "(no page content)"
    if max_chars is None or len(blob) <= max_chars:
        return blob
    return truncate_chars(blob, max_chars)


def format_fca_sources_numbered(source_strings: list[str]) -> str:
    """Numbered list of verified citation strings for prompts."""
    if not source_strings:
        return "(no verified FCA sources — do not fabricate citations)"
    lines = [f"{i + 1}. {s}" for i, s in enumerate(source_strings)]
    return "\n".join(lines)


def format_fca_sources(chunks: list[dict]) -> str:
    """Legacy JSON-line format (unused by new graph; kept for scripts)."""
    lines = []
    for c in chunks:
        sid = c.get("source_id", "")
        label = c.get("document_label", "")
        text = (c.get("text") or "")[:900]
        lines.append(
            json.dumps(
                {"source_id": sid, "document_label": label, "text": text},
                ensure_ascii=False,
            )
        )
    return "\n".join(lines) if lines else "(no FCA chunks retrieved — do not fabricate citations)"


def format_fca_context(chunks: list[dict], *, max_chars: int = 12000) -> str:
    """Longer excerpts for prompts keyed by chunk dicts."""
    parts: list[str] = []
    for c in chunks:
        meta = c.get("metadata") or {}
        cite = meta.get("citation") or meta.get("source") or c.get("document_label") or ""
        text = (c.get("text") or "").strip()
        if not text:
            continue
        head = f"[{cite}]\n" if cite else ""
        parts.append(head + text[:4000])
    blob = "\n\n---\n\n".join(parts)
    if len(blob) <= max_chars:
        return blob
    return blob[:max_chars] + "\n\n[... FCA_CONTEXT truncated ...]"


def build_website_content(docs: list[dict], *, max_chars: int = 28000) -> str:
    """Concatenate legacy ``page_content`` dicts with URL headers."""
    parts: list[str] = []
    for d in docs:
        meta = d.get("metadata") or {}
        label = (
            meta.get("sourceURL")
            or meta.get("url")
            or meta.get("source")
            or meta.get("title")
            or "unknown_page"
        )
        text = (d.get("page_content") or "").strip()
        if not text:
            continue
        parts.append(f"### PAGE_URL: {label}\n{text}")
    blob = "\n\n---\n\n".join(parts)
    if len(blob) <= max_chars:
        return blob
    return blob[: max_chars - 80] + "\n\n[... WEBSITE_CONTENT truncated ...]"
