# Consumer Duty Sludge Audit Tool

## What It Does

This tool accepts a UK financial services website URL and generates a structured audit against the FCA Consumer Duty. It is aimed at compliance teams, product managers, and engineers who want a quick, repeatable way to review customer-facing web content against PRIN 2A expectations.

It produces outcome-level scores and evidence for all four Consumer Duty outcomes: Products & Services (PRIN 2A.2), Price & Value (PRIN 2A.3), Consumer Understanding (PRIN 2A.4), and Consumer Support (PRIN 2A.5). Products & Services and Price & Value are scored from public website evidence only and should be treated as partial where internal firm data is required.

## Design notes (architecture, trade-offs, scale)

If you’re assessing engineering depth (why it’s built this way, trade-offs, improvements, scale), start here:

- `docs/features.md`
- `docs/architecture.md`
- `docs/tradeoffs-and-limitations.md`
- `docs/scaling-and-production.md`
- `docs/evaluation.md`

## How It Works

The backend crawls the site using FireCrawl and extracts clean markdown text from up to 15 pages. A validation gate requires at least 3 pages and 2000 words, otherwise the pipeline returns an INSUFFICIENT_DATA report.

FCA PDFs are ingested into a local ChromaDB index using HuggingFace sentence-transformers embeddings (all-MiniLM-L6-v2). During scoring, the retriever fetches relevant chunks for each outcome and passes their citation labels into the prompt.

LangGraph orchestrates the workflow as a state machine with typed state. Nodes handle crawling, validation, outcome evaluation, dark pattern detection, vulnerability gap checking, and compilation. The graph takes an early exit when crawl validation fails to avoid unnecessary model calls.

Scoring is criteria based. Each outcome has five criteria worth two points each. The model scores each criterion against evidence and the total score is computed as the sum of criterion points. This is more reliable than holistic scoring because it reduces run-to-run variance and makes the result easier to audit.

Citations are grounded in retrieved chunks, not model memory. Prompts instruct the model to cite only from the provided `fca_sources` list so references can be traced to the retrieved FCA documents.

Each outcome includes a confidence level, HIGH, MEDIUM, or LOW, derived from crawl depth and the amount of text analysed. Reports are cached as JSON under `audit_cache/` using a URL hash, and the cache can be cleared via `DELETE /audit/cache`.

## Prerequisites

- Python 3.11+
- Node.js 18+
- Groq API key
- FireCrawl API key

## Setup

Backend:
  python -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  cp .env.example .env
  # Add your GROQ_API_KEY and FIRECRAWL_API_KEY to .env

Optional (recommended) for cleaner local logs:
  Add these to your local `.env` to disable Chroma telemetry errors and HuggingFace tokeniser fork warnings:
  ANONYMIZED_TELEMETRY=false
  TOKENIZERS_PARALLELISM=false

Frontend:
  cd frontend
  npm install

## Load FCA Documents

Place FCA PDFs in `fca_docs/` then run:
  python -m backend.ingestion.fca_loader

FG22/5 is the minimum recommended document. For better grounding, add the relevant Consumer Duty good practice reports and any FCA portfolio letters that apply to the product type.

## Run

Terminal 1:
  uvicorn backend.main:app --reload --port 8000

Terminal 2:
  cd frontend && npm run dev

Open http://localhost:3000

## Run an Audit via API

  curl -X POST http://localhost:8000/audit \
    -H "Content-Type: application/json" \
    -d '{"url": "https://www.example-firm.co.uk"}'

## Security Notes

The backend includes SSRF protection on submitted URLs, prompt injection mitigation for crawled content, cache path safety checks, basic rate limiting for `POST /audit`, and standard security headers. For production use you would add authentication, audit logging, and durable storage for both evidence and reports.

## Tests

This repository includes a small `unittest` suite that covers SSRF validation, prompt injection sanitisation, cache safety, and an integration check that `X-Request-ID` is present on both 200 and 422 API responses.

Run:
  python -m unittest discover -s tests -p "test_*.py" -q
