# Architecture

This document answers:

- why the system is designed the way it is
- the major components and data flow
- where to look in the codebase for each part

## Overview

The Consumer Duty Sludge Audit Tool takes a single public URL (or two URLs for comparison) and produces a structured report against PRIN 2A.2–2A.5.

At a high level:

1. **Crawl**: fetch and extract clean text from a bounded set of public pages.
2. **Validate**: stop early if there isn’t enough usable content to score responsibly.
3. **Retrieve FCA context**: pull relevant regulatory chunks from a local vector index (ChromaDB).
4. **Score outcomes**: evaluate each outcome using a criteria checklist and require verbatim page evidence.
5. **Detect**: extract suspected dark patterns and vulnerability-support gaps.
6. **Compile + cache**: assemble a single JSON report and cache it deterministically by URL.

Code pointers:

- **API**: `backend/main.py` (FastAPI entry point)
- **Orchestration**: LangGraph workflow nodes (see `backend/` pipeline modules)
- **Criteria definitions**: `backend/pipeline/scorer.py`
- **Report contracts**: `backend/schemas/audit.py` and `frontend/types/audit.ts`
- **UI**: Next.js app under `frontend/app/`

## Why it is designed this way

### Criteria-based scoring (vs holistic scoring)

Each outcome is scored as a sum of criterion scores (0–10). This is intentional:

- **Auditability**: every point has a named criterion, page URL, and verbatim evidence.
- **Lower variance**: breaking judgement into smaller decisions tends to reduce run-to-run drift vs “give me a score out of 10”.
- **Actionability**: failures map to a specific customer-facing gap (e.g., “complaints process accessibility”) rather than a generic narrative.

### Early validation gate

The pipeline refuses to score if the crawl is too shallow (minimum pages/words). This avoids “confident-looking” but unreliable outputs when the input evidence base is tiny.

This also reduces cost by taking an early exit before expensive model calls.

### Retrieval-augmented grounding for FCA citations

Regulatory references must be grounded in retrieved FCA chunks (not model memory). Prompts enforce a “cite only from provided sources” rule.

Intent:

- **Traceability**: citations should be traceable to indexed PDFs/chunks.
- **Safety**: reduces hallucinated references (a common failure mode in compliance tooling).

### Typed state + typed outputs

The system uses typed schemas for:

- **runtime orchestration state** (to keep the graph deterministic and debuggable)
- **persisted report JSON** (to make reports stable for caching and UI rendering)

This is a deliberate choice to keep the tool maintainable as the pipeline grows.

### URL-keyed caching

Reports are cached under a URL hash key. Rationale:

- **repeatability**: the same input URL can be reopened without re-running the crawl/model calls
- **cost control**: avoids repeated model usage during iteration/demos

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

- **Goal**: ship a clean UI fast, with simple routing and good dev experience.
- **Constraints**: small team/time; the frontend is primarily a report viewer + form submission.
- **Options**: Next.js, Vite + React SPA, Remix.
- **Trade-offs**:
  - Next.js adds framework complexity, but gives conventions for routing/layout and production defaults.
  - A plain SPA is simpler, but you end up re-solving routing, env management, and deployment conventions anyway.
- **Decision**: use **Next.js** for rapid iteration and straightforward page-based UX (`frontend/app/`).
- **Next**: if the UI needs auth, multi-tenancy, or server-side rendering for shareable reports, Next.js becomes even more beneficial; if it stays tiny, a Vite SPA would also be fine.

### Backend API: FastAPI + Pydantic vs Django/DRF vs Flask

- **Goal**: typed API contracts and fast iteration for a pipeline-heavy service.
- **Constraints**: correctness matters (report schema), and I want a clean boundary between pipeline and UI.
- **Options**: FastAPI, Django/DRF, Flask.
- **Trade-offs**:
  - FastAPI + Pydantic makes schemas first-class and keeps handlers lightweight.
  - Django adds batteries (auth/admin/ORM) but is heavier than needed for this project’s current shape.
  - Flask is minimal but you rebuild typing/validation conventions yourself.
- **Decision**: use **FastAPI + Pydantic** for strong request/response validation and explicit report contracts (`backend/schemas/audit.py`).
- **Next**: if I add multi-user auth, audit logging, and persistence, Django becomes more attractive; otherwise keep FastAPI and add a DB layer deliberately.

### Orchestration: LangGraph state machine vs a linear script

- **Goal**: a pipeline with explicit stages, early exits, and debuggable state.
- **Constraints**: multiple steps with different failure modes to avoid “giant function” drift.
- **Options**: LangGraph, a single Python script, Celery pipeline, custom DAG.
- **Trade-offs**:
  - LangGraph adds a dependency, but makes stages and state explicit and composable.
  - A linear script is easiest at first but becomes hard to maintain and test as nodes grow.
- **Decision**: use **LangGraph** to encode the workflow as a typed state machine and support early exits.
- **Next**: for production scale, run the graph inside worker processes and attach real tracing (per-node timings, retries, and error taxonomy).

### Crawling: FireCrawl vs self-managed crawling

- **Goal**: reliably extract readable text/markdown from arbitrary public websites with minimal bespoke scraping code.
- **Constraints**: web variability is enormous; writing and maintaining a crawler is expensive.
- **Options**: FireCrawl, Playwright-based custom crawler, Requests+BeautifulSoup, other crawl APIs.
- **Trade-offs**:
  - A provider like FireCrawl reduces engineering effort but introduces quotas, vendor dependency, and failure modes outside my control.
  - A self-managed crawler offers control but is a long-term maintenance commitment.
- **Decision**: use **FireCrawl** to move effort from “scraping engineering” to “audit quality and safety.”
- **Next**: add fallback strategies (e.g., retry policies, alternate extraction, PDF ingestion) and surface “what I failed to fetch” clearly in the report.

### Regulatory source set: minimal FCA corpus vs ingesting every provided document

- **Goal**: ensure regulatory citations are correct, traceable, and consistent with the evidence and the scoring rubric.
- **Constraints**:
  - ingestion quality matters more than ingestion quantity (chunking, labelling, metadata, and retrieval behaviour)
  - the more documents added, the more the validation retrieval precision to avoid citing irrelevant or outdated material
  - I want a small, defensible baseline that is easy to keep current
- **Options**:
  - ingest the full list of FCA documents up front (guidance, good practice reports, portfolio letters, thematic reviews)
  - start with a minimal “core” set and expand iteratively with evaluation coverage
- **Trade-offs**:
  - a minimal set reduces retrieval noise and makes citation behaviour easier to test and explain, but can miss niche guidance that affects certain products/journeys
  - a large corpus improves coverage, but increases the risk of low-precision retrieval and makes versioning and quality assurance non-negotiable
- **Decision**: start with a **core FCA corpus** (FG22/5 as the baseline Consumer Duty guidance, plus outcome-specific materials for Consumer Understanding and Consumer Support) to keep retrieval behaviour predictable and citations defensible during early iterations.
- **Next**: expand the corpus deliberately:
  - add portfolio letters and good practice reports relevant to specific product types
  - introduce index versioning and retrieval benchmarks, and gate corpus changes behind the evaluation loop (`docs/evaluation.md`)

### Vector store: local ChromaDB vs managed vector database

- **Goal**: RAG grounding for FCA citations with low operational overhead in local/dev.
- **Constraints**: keep the system easy to run locally; the document corpus is finite and curated.
- **Options**: Chroma local, pgvector/Postgres, Pinecone/Weaviate, OpenSearch.
- **Trade-offs**:
  - Local Chroma is easy for dev and demos, but not ideal for multi-instance production without durable backing.
  - Managed vector DBs scale better but add cost and operational complexity.
- **Decision**: use **local ChromaDB** for the current stage of the project.
- **Next**: for production/multi-instance deployments, move to **pgvector** (if I already want Postgres) or a managed vector store with explicit index versioning.

### Embeddings: sentence-transformers (all-MiniLM-L6-v2) vs vendor embeddings

- **Goal**: stable, low-cost embeddings for FCA PDF retrieval.
- **Constraints**: avoid coupling retrieval quality to an LLM vendor; keep ingestion predictable.
- **Options**: local sentence-transformers, OpenAI embeddings, Cohere embeddings, etc.
- **Trade-offs**:
  - Local embeddings avoid per-call cost and vendor coupling, but may be lower quality than best-in-class hosted models.
  - Vendor embeddings can be stronger but add cost and dependency.
- **Decision**: use **sentence-transformers** for simplicity and predictable local runs.
- **Next**: if retrieval quality is the limiting factor, evaluate better embedding models and add retrieval benchmarks (`docs/evaluation.md`).

### LLM provider: Groq (cost/latency) vs Claude (quality)

- **Goal**: produce useful, repeatable audits while iterating quickly.
- **Constraints**: inference cost and rate limits dominate; I need predictable runtime.
- **Options**: Groq, Claude, OpenAI, others.
- **Trade-offs**:
  - **Claude often produces better narrative quality and nuanced reasoning** for compliance-style writing.
  - **Groq is typically cheaper/faster**, which matters for iteration loops and throughput.
- **Decision**: use **Groq as the default** for cost/latency, while keeping prompts + schemas provider-agnostic so I can swap providers.
- **Next**: introduce **tiered routing**: use Groq for baseline, and escalate to Claude for “hard” cases (low confidence, complex pages, ambiguous evidence) where quality is worth the cost.

### Sync request vs queue-based processing

- **Goal**: simplest end-to-end UX for early development and demos.
- **Constraints**: audits involve crawling and multiple model calls, so they can be slow and rate-limited.
- **Options**: synchronous `POST /audit`, async jobs with a queue and workers.
- **Trade-offs**:
  - Synchronous is simplest, but under high traffic you’ll hit timeouts and provider rate limits quickly.
  - Queue-based is more reliable and scalable, but adds infra and complexity.
- **Decision**: start **synchronous** for iteration; design schemas and caching so async is a straightforward evolution.
- **Next**: productionise with **queue + workers**, `202 Accepted` job semantics, durable storage, and observability (see `docs/scaling-and-production.md`).

## What to improve next (architecture-level)

See:

- `docs/scaling-and-production.md` for scale/production architecture
- `docs/evaluation.md` for how to measure and improve scoring quality

