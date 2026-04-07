# Evaluation and quality

The goal of this tool is not just to generate text, but to generate **auditable, stable, actionable** audit outputs.

This page describes how to assess and improve quality over time.

## What “good” looks like

For a given target site, a good report:

- uses **verbatim evidence quotes** that actually support the finding/score
- cites **only retrieved FCA sources** (no invented references)
- produces **consistent scores** across runs when the site content is unchanged
- clearly marks **insufficient data** and low-confidence situations
- provides recommendations that are specific enough to implement

## Evaluation dimensions

### Grounding accuracy

Checks:

- Does each criterion’s evidence quote support the awarded points?
- Are page URLs correct and reachable?
- Are FCA references present and traceable to retrieved chunks?

### Scoring consistency

Run-to-run checks on a fixed corpus:

- score variance per outcome
- variance in which criteria are marked met/not met
- variance in the severity distribution of findings

### Coverage

Checks:

- are key page types found (product pages, pricing, complaints, accessibility)
- do we exit as insufficient data when we should
- do we miss evidence due to crawl discovery gaps

### Error handling

Checks:

- provider rate limits result in a clear “scoring unavailable” state (not silent empty outputs)
- partial failure still compiles a coherent report with explicit caveats

## How to improve quality (practical loop)

1. **Collect a small benchmark set** of representative financial services sites.
2. **Freeze the pipeline version** (criteria + prompts + FCA index) and generate baseline reports.
3. **Review failures**:
   - bad evidence extraction
   - wrong page association
   - missing regulatory context
   - over/under-scoring patterns
4. **Make one change at a time** (crawl config OR prompt OR criteria OR retrieval).
5. **Re-run the benchmark** and compare deltas.

## Testing strategy (today and next)

Today there are unit/integration tests focusing on correctness and safety boundaries (URL validation, injection mitigation, cache safety, request id propagation).

Next additions that increase confidence:

- golden-file tests for schema stability (report JSON shape)
- deterministic replay tests using stored crawl outputs (so tests don’t depend on live websites)
- retrieval tests that assert FCA chunks are returned for known queries

