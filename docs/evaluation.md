# Evaluation and quality

The goal is **auditable, stable, actionable** outputs.

## What “good” looks like

For a given target site, a good report:

- uses verbatim evidence that supports the score/finding
- cites only retrieved FCA sources
- is consistent across runs on unchanged content
- makes insufficient-data and low-confidence states explicit
- provides specific, implementable recommendations

## Evaluation dimensions

### Grounding accuracy

Checks:

- evidence supports awarded points
- page URLs are correct
- FCA references are present and traceable

### Scoring consistency

Run-to-run checks on a fixed corpus:

- score variance per outcome
- variance in which criteria are marked met/not met
- variance in the severity distribution of findings

### Coverage

Checks:

- are key page types found (product pages, pricing, complaints, accessibility)?
- do I exit as insufficient data when I should?
- do I miss evidence due to crawl discovery gaps?

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

Current tests focus on URL safety, injection mitigation, cache safety, and request ID propagation.

Next additions that increase confidence:

- golden-file tests for schema stability (report JSON shape)
- deterministic replay tests using stored crawl outputs (so tests don’t depend on live websites)
- retrieval tests that assert FCA chunks are returned for known queries

