# Trade-offs and limitations

This document makes the design choices explicit:

- what I optimised for
- what I traded off
- where the edge cases are

## Evidence scope limitations

### Public website only

The system audits **publicly accessible pages**. It does not (today):

- authenticate into customer portals
- evaluate post-login journeys
- ingest internal firm data (product governance packs, complaints MI, call recordings, etc.)

Impact:

- “Products & Services” and “Price & Value” are **partial** if key evidence is internal.
- absence of evidence in the crawl is not evidence of absence in the firm.

## Crawl strategy trade-offs

### Bounded crawl (cap on pages)

The crawler extracts text from **up to a bounded number of pages** (documented in `README.md`).

- **Pro**: predictable runtime and cost; reduces “infinite site” risk.
- **Con**: may miss relevant pages (pricing, complaints, accessibility) if not discovered.

Edge cases:

- SPAs where content loads behind scripts that the crawler can’t execute well.
- important evidence in PDFs or assets not linked in the top crawl graph.
- region-gated or cookie-wall-gated pages.

### Validation gate (min pages/words)

The pipeline returns `INSUFFICIENT_DATA` when the crawl is too shallow.

- **Pro**: prevents a false sense of precision.
- **Con**: can reject small-but-informative sites (e.g. a single-page microsite) even if it includes key compliance disclosures.

## Scoring trade-offs

### Checklist scoring vs holistic judgement

I use criteria checklists per outcome, then sum to 0–10.

- **Pro**: auditable, comparatively stable, and actionable.
- **Con**: can miss nuanced harms that don’t map cleanly to a single criterion; can overfit to “what the checklist asks for”.

### Verbatim evidence requirement

I require exact quotes from crawled pages.

- **Pro**: forces grounding; makes review easier.
- **Con**: the model may under-specify issues where the harm is primarily visual (hierarchy, contrast, prominence) rather than textual.

## Retrieval/citation trade-offs

### RAG grounding for FCA references

Citations are restricted to retrieved chunks.

- **Pro**: reduces hallucinated citations; improves traceability.
- **Con**: if the FCA index is incomplete or retrieval misses a relevant chunk, the report may fall back to generic references even when FCA guidance exists.

Operational implication:

- keeping the FCA document set current and well chunked is part of the system’s quality assurance.

### FCA corpus completeness

The FCA index is deliberately curated. If only a core subset of FCA documents is ingested, then:

- the system will preferentially cite from that subset, even where other FCA publications would provide stronger or more specific grounding for a particular product type
- expanding the corpus must be treated as a quality change (it can shift retrieval behaviour and therefore the citations and findings)

The rationale for starting with a minimal corpus, and the plan for expanding it safely, is documented in `docs/architecture.md`.

## Caching trade-offs

Reports are cached by URL hash.

- **Pro**: fast repeat access; cheaper iteration; supports deep links to prior reports.
- **Con**: results can become stale as the target site changes; cache invalidation becomes a product choice.

## Security / abuse limitations

The backend includes SSRF protection and prompt-injection mitigation, but production hardening still matters:

- authentication and authorization (who can run audits / see reports)
- audit logging (who ran what, when)
- stricter rate limiting and abuse detection
- data retention policies (reports contain copied page text snippets)

## “At scale” limitations (today)

Without additional infrastructure (queueing, durable storage, observability), high concurrency will stress:

- the crawler provider quotas / rate limits
- the model provider quotas / rate limits
- local disk cache contention and eviction strategy

For a concrete production path, see `docs/scaling-and-production.md`.

