# Scaling and production considerations

This tool is designed to be auditable first. Scaling requires explicit controls for cost, latency, quotas, and retention.

## What happens at scale (expected bottlenecks)

- **Crawling**: outbound crawling is slow and quota-limited; sites vary widely in response time and structure.
- **Model calls**: LLM inference is rate-limited and cost-sensitive; spikes can cause cascading failures.
- **Vector retrieval**: generally fast, but index quality (chunking, metadata) drives answer quality.
- **Caching/storage**: local disk cache is not durable across instances and is not safe as the primary store in multi-instance deployments.

## Production architecture (recommended)

### Queue-based execution

Move `POST /audit` from synchronous execution to an async job model:

1. accept the request and validate the URL
2. enqueue a job (with an idempotency key based on the normalised URL + pipeline version)
3. return `202 Accepted` with a job id
4. worker(s) execute crawl + scoring
5. client polls `GET /audit/jobs/{id}` or uses SSE/webhooks

Rationale:

- protects the API from long-running requests
- makes concurrency and retry policies explicit
- improves user experience under load

### Durable storage

Store reports in durable storage (not local disk):

- **Object storage**: JSON report blobs keyed by hash/version
- **DB**: metadata (url, created_at, status, durations, score summaries, tenant/user)

Add retention and deletion policies (reports can contain verbatim text).

### Cache versioning and invalidation

Cache keys should incorporate:

- normalised URL
- pipeline version (prompts, criteria definitions, scoring logic)
- FCA index version (document set)

This prevents “silent semantic changes” where cached reports no longer match current scoring rules.

### Rate limiting and budgets

Implement layered limits:

- per-IP and per-user request limits
- per-tenant concurrency limits
- cost budgets (max pages crawled, max tokens, max model calls) with explicit “degraded mode”

### Observability

Add structured tracing with:

- request ID propagation end-to-end
- per-stage timings (crawl, retrieval, scoring, compile)
- error taxonomy (crawl failure, insufficient data, rate limit, provider errors)

SLOs to define:

- time to first result
- success rate per provider
- cost per audit percentile (P50/P95)

## Performance and cost controls

Practical knobs:

- lower/raise crawl cap based on plan tier
- outcome-level short-circuiting when evidence is absent
- reuse retrieved FCA chunks across criteria where appropriate
- incremental/streamed compilation so partial results can be surfaced

## Multi-tenancy and security

If deployed for multiple users/teams:

- authentication + authorization (who can access which reports)
- tenant isolation in storage keys
- redaction options (reports include verbatim evidence)
- allowlist/denylist controls for audited domains

## Quality at scale

When usage grows, “quality regressions” become operational incidents.

Add a regression suite, periodic re-evaluation on pipeline/index changes, and drift monitoring on score distributions.

See `docs/evaluation.md`.

