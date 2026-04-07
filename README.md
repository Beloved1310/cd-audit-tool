# Consumer Duty Sludge Audit Tool

## What It Does

This tool accepts a UK financial services website URL and generates a structured audit against the FCA Consumer Duty. It is aimed at compliance teams, product managers, and engineers who want a quick, repeatable way to review customer-facing web content against PRIN 2A expectations.

It produces outcome-level scores and evidence for all four Consumer Duty outcomes: Products & Services (PRIN 2A.2), Price & Value (PRIN 2A.3), Consumer Understanding (PRIN 2A.4), and Consumer Support (PRIN 2A.5). Products & Services and Price & Value are scored from public website evidence only and should be treated as partial where internal firm data is required.

## Design notes (architecture, trade-offs, scale)

why it is built this way, trade-offs, improvements, scale: start here:

- `docs/features.md`
- `docs/architecture.md`
- `docs/tradeoffs-and-limitations.md`
- `docs/scaling-and-production.md`
- `docs/evaluation.md`

## How It Works

The backend crawls the site using FireCrawl and extracts clean markdown text from up to 15 pages. A validation gate requires at least 3 pages and 2,000 words; otherwise the pipeline returns an `INSUFFICIENT_DATA` report.

FCA PDFs are ingested into a local ChromaDB index using HuggingFace sentence-transformers embeddings (all-MiniLM-L6-v2). During scoring, the retriever fetches relevant chunks for each outcome and passes their citation labels into the prompt.

LangGraph orchestrates the workflow as a state machine with typed state. Nodes handle crawling, validation, outcome evaluation, dark pattern detection, vulnerability gap checking, and compilation. The graph takes an early exit when crawl validation fails to avoid unnecessary model calls.

Scoring is criteria-based. Each outcome has five criteria worth two points each. The model scores each criterion against evidence and the total score is computed as the sum of criterion points. This is more reliable than holistic scoring because it reduces run-to-run variance and makes the result easier to audit.

Citations are grounded in retrieved chunks, not model memory. Prompts instruct the model to cite only from the provided `fca_sources` list so references can be traced to the retrieved FCA documents.

Each outcome includes a confidence level, HIGH, MEDIUM, or LOW, derived from crawl depth and the amount of text analysed. Reports are cached on disk under `audit_cache/` using a versioned key that includes a canonicalised URL and `pipeline_version`.

## Prerequisites

- Python 3.11+
- Node.js 18+
- Groq API key
- FireCrawl API key

## Setup

### Backend

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `GROQ_API_KEY` and `FIRECRAWL_API_KEY` in `.env`.

Optional (recommended) for cleaner local logs:
add these to `.env` to suppress Chroma telemetry errors and HuggingFace tokeniser fork warnings:

```bash
ANONYMIZED_TELEMETRY=false
TOKENIZERS_PARALLELISM=false
```

Optional settings:

```bash
# Identifies outbound HTTP requests in logs.
USER_AGENT="cd-audit-tool/0.1 (local)"

# Crawl/memory limits
CRAWL_PAGE_LIMIT=15
MAX_PAGE_CHARS=40000
MAX_TOTAL_WORDS=60000
```

### Frontend

```bash
cd frontend
npm install
```

## Load FCA Documents

Place FCA PDFs in `fca_docs/` then run:

```bash
python -m backend.ingestion.fca_loader
```

This repository includes a small FCA PDF corpus under `fca_docs/` to support offline reproducibility. You can add, remove, or replace documents to suit the product type (for example relevant good practice reports and portfolio letters); if you change the document set, re-run ingestion to rebuild the index.

FG22/5 is the minimum recommended document. For better grounding, add the relevant Consumer Duty good practice reports and any FCA portfolio letters that apply to the product type.

## Run

In one terminal:

```bash
uvicorn backend.main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000`.

## Run an Audit via API

```bash
curl -X POST http://localhost:8000/audit \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.example-firm.co.uk"}'
```

## Pagination endpoints (large reports)

For large reports, the API exposes paginated endpoints backed by the cached report:

- `GET /audit/report/findings?url=…&outcome=…&page=1&page_size=10`
- `GET /audit/report/dark-patterns?url=…&page=1&page_size=10`
- `GET /audit/report/vulnerability-gaps?url=…&page=1&page_size=10`

## Additional caches

In addition to per-URL audit reports, the backend caches derived results under `audit_cache/`:

- `audit_cache/compare/`: cached comparison reports (idempotent on canonicalised URL pair + pipeline version)
- `audit_cache/journey/`: cached journey reports (idempotent on canonicalised step URLs + pipeline version)

## Security Notes

The backend includes SSRF protection on submitted URLs, prompt injection mitigation for crawled content, cache path safety checks, basic rate limiting for `POST /audit`, and standard security headers. For production use you would add authentication, audit logging, and durable storage for both evidence and reports.

## Tests

This repository includes a small `unittest` suite that covers SSRF validation, prompt injection sanitisation, cache safety, and an integration check that `X-Request-ID` is present on both 200 and 422 API responses.

Run:

```bash
python -m unittest discover -s tests -p "test_*.py" -q
```
