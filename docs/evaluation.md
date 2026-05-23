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

## Implemented harness (offline)

The repo includes an **offline** quality harness (no Groq, no crawl):

- **`backend/evaluation/metrics.py`** — `compute_report_quality_metrics(report)` checks four outcomes present, overall score vs mean of outcomes, rating vs score bands, score ranges, and **evidence density** (criteria with proof when not fully met; findings with verbatim evidence and FCA reference; dark patterns / vulnerability gaps).
- **`backend/evaluation/schemas.py`** — `ReportQualityMetrics` plus a single **`harness_score_0_100`** for CI gates.
- **`backend/evaluation/benchmark.py`** — load `evaluation/benchmarks/*.json` manifests and fail if any case is below `min_harness_score` or has structural violations.
- **`tests/fixtures/sample_audit_report.json`** — synthetic complete `AuditReport` for golden-style checks.
- **`tests/test_evaluation_metrics.py`** — asserts the sample fixture passes and that score mismatches are detected.
- **`scripts/run_evaluation.py`** — from repo root:  
  `python scripts/run_evaluation.py` (default fixture),  
  `python scripts/run_evaluation.py --report path/to/report.json`,  
  `python scripts/run_evaluation.py --benchmark evaluation/benchmarks/default.json` (exit code 1 on failure).

This measures **consistency and grounding density**, not regulatory truth vs a human panel. Add more rows to `evaluation/benchmarks/default.json` pointing at frozen real reports as you capture them.

## Scoring accuracy (pipeline vs expert labels)

**`backend/evaluation/accuracy.py`** compares a COMPLETE `AuditReport` to a `GroundTruthLabel` JSON file:

- Outcome-level MAE and RED/AMBER/GREEN agreement
- Per-criterion agreement on IDs **1–10** from `backend/pipeline/scorer.py`

The live pipeline and ground truth now share the **same fixed checklist**: prompts inject `{scoring_criteria}` from `format_criteria_for_prompt()`, and nodes call `normalize_outcome_criteria()` so every outcome has ten rows for comparison.

| Script / test | Purpose |
|---------------|---------|
| `scripts/run_accuracy.py` | Live Groq run on frozen crawls vs labels |
| `scripts/freeze_crawl.py` | Capture crawl JSON for labelling |
| `tests/test_accuracy_offline_integration.py` | CI: perfect-agreement path using `audit_report_from_ground_truth()` |
| `tests/test_accuracy_integration.py` | Optional live run (`GROQ_API_KEY`) |
| `tests/test_criteria_alignment.py` | Prompts contain checklist placeholder; ten criteria per outcome |

**Harness vs accuracy:** `run_evaluation.py --benchmark` gates structural quality; accuracy gates require expert labels under `evaluation/ground_truth/`. The bundled `example_retail_bank` label is `synthetic_fixture_v1` — use it to validate the math, then add real expert-labelled sites for credible accuracy numbers.

## Testing strategy (today and next)

Current tests cover URL safety, injection mitigation, cache safety, request ID propagation, **evaluation metrics** on frozen reports, **retrieval quality**, **criteria alignment**, and **offline accuracy**.

Next steps for production-grade accuracy:

- Add more `(frozen_crawl, ground_truth)` pairs with human `labelled_by` metadata
- Set MAE / rating-agreement thresholds in CI once a stable labelled set exists
- Run `python scripts/run_accuracy.py` after prompt or corpus changes

