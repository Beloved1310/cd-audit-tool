# Architecture

This document summarises the system design and key decisions.

## Overview

The Consumer Duty Sludge Audit Tool takes a single public URL (or two URLs for comparison) and produces a structured report against PRIN 2A.2–2A.5.

Pipeline:

1. **Crawl** public pages (bounded).
2. **Validate** minimum evidence; otherwise early exit.
3. **Retrieve** FCA context (ChromaDB).
4. **Score** outcomes via criteria checklist with verbatim evidence.
5. **Detect** dark patterns and vulnerability gaps.
6. **Compile + cache** a deterministic JSON report.

Code pointers:

- **API**: `backend/main.py` (FastAPI entry point)
- **Orchestration**: LangGraph workflow nodes (see `backend/` pipeline modules)
- **Criteria definitions**: `backend/pipeline/scorer.py`
- **Report contracts**: `backend/schemas/audit.py` and `frontend/types/audit.ts`
- **UI**: Next.js app under `frontend/app/`

## Why it is designed this way

### Criteria-based scoring (vs holistic scoring)

Each outcome score is the sum of criterion scores (0–10).

- **Auditability**: criterion name + page URL + verbatim evidence per point.
- **Stability**: reduces drift vs a single holistic score.
- **Actionability**: failures map to a specific gap.

### Early validation gate

If the crawl is too shallow (minimum pages/words), the pipeline returns `INSUFFICIENT_DATA`. This avoids unreliable scoring and reduces cost via early exit.

### Retrieval-augmented grounding for FCA citations

Citations are restricted to retrieved FCA chunks (not model memory).

- **Traceability**: every citation is backed by indexed text.
- **Safety**: reduces hallucinated references.

### Typed state + typed outputs

Typed schemas define orchestration state and persisted report JSON to keep the pipeline debuggable and the UI contract stable.

### URL-keyed caching

Reports are cached under a URL hash key. Rationale:

- **Repeatability**: reopen the same URL without re-running.
- **Cost control**: reduce repeated model calls.

Trade-off: cached results can become stale if the target site changes; see `docs/tradeoffs-and-limitations.md`.

## Data flow and boundaries

### Trust boundaries

- **Crawled website text is untrusted** and may contain prompt-injection attempts. Prompts explicitly instruct the model to treat it as evidence only.
- **Regulatory sources are curated** and ingested into a local index. Only those sources may be cited.

### Public-only vs internal evidence

Two outcomes (“Products & Services” and “Price & Value”) are inherently limited by public website evidence. The report includes scope fields to avoid overstating certainty.

## Failure modes (designed-for)

The system is built to surface failures explicitly:

- **Insufficient data**: crawl returns too few pages/words -> status is `INSUFFICIENT_DATA` with a human-readable reason.
- **Crawl failure**: crawling errors -> `CRAWL_FAILED` / early exit report.
- **Partial outcome scoring**: an outcome may return no checklist rows (e.g. upstream rate limit); the UI treats that as “scoring unavailable” rather than silently showing an empty table.

## Decision log (stack choices)

This section records my engineering rationale: goal → constraints → options → trade-offs → decision → what I would change next.

### Frontend framework: Next.js (App Router) vs plain React SPA

- **Decision**: **Next.js** for fast iteration and page-based UX.
- **Trade-off**: more framework surface area than a small SPA.

### Backend API: FastAPI + Pydantic vs Django/DRF vs Flask

- **Decision**: **FastAPI + Pydantic** for typed request/response contracts.
- **Trade-off**: fewer built-in “product” features than Django; add persistence/auth deliberately if needed.

### Orchestration: LangGraph state machine vs a linear script

- **Decision**: **LangGraph** to make stages, state, and early exits explicit.
- **Trade-off**: added dependency; pays for itself once the pipeline grows.

### Crawling: FireCrawl vs self-managed crawling

- **Decision**: **FireCrawl** to prioritise extraction quality over bespoke scraping.
- **Trade-off**: quotas and vendor dependency; mitigate with clear failure reporting and fallbacks.

### Regulatory source set: minimal FCA corpus vs ingesting every provided document

- **Decision**: start with a **core FCA corpus** (FG22/5 + outcome-specific materials) so retrieval and citations are predictable.
- **Trade-off**: less coverage; expand deliberately with retrieval benchmarks and index versioning.

### Vector store: local ChromaDB vs managed vector database

- **Decision**: **local ChromaDB** for easy local/dev runs.
- **Trade-off**: not ideal for multi-instance production; migrate to pgvector/managed store if needed.

### Embeddings: sentence-transformers (all-MiniLM-L6-v2) vs vendor embeddings

- **Decision**: **sentence-transformers** for predictable local embeddings.
- **Trade-off**: may be weaker than hosted embeddings; validate via retrieval benchmarks.

### LLM provider: Groq (cost/latency) vs Claude (quality)

- **Decision**: **Groq** by default for cost/latency; keep prompts/schemas provider-agnostic.
- **Trade-off**: Claude can produce higher-quality narrative output; use tiered routing for hard cases if needed.

### Sync request vs queue-based processing

- **Decision**: start **synchronous** for simplicity; evolve to queue + workers for scale.
- **Trade-off**: synchronous requests degrade under load; see `docs/scaling-and-production.md`.

## What to improve next (architecture-level)

See:

- `docs/scaling-and-production.md` for scale/production architecture
- `docs/evaluation.md` for how to measure and improve scoring quality

