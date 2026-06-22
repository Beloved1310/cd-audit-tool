# Accuracy benchmark data

Code lives in `backend/evaluation/`; **datasets live here** at the repo root.

## Two gates (do not mix them)

| Gate | Command | Measures |
|------|---------|----------|
| **Harness** | `python scripts/run_evaluation.py --benchmark evaluation/benchmarks/default.json` | Report shape, evidence density |
| **Accuracy** | `python scripts/run_accuracy.py --max-mae 1.5 --min-rating-agreement 75` | Pipeline scores vs human labels |

Harness passing does **not** mean scores are regulatorily correct.

---

## Add a labelled site (freeze at label time)

### 1. Freeze the crawl

```bash
python scripts/freeze_crawl.py \
  --url https://www.example-bank.co.uk \
  --out evaluation/frozen_crawls/example_bank.json \
  --site-id example_bank
```

Note the `frozen_at` timestamp printed in the saved JSON.

### 2. Copy the label template

```bash
cp evaluation/ground_truth/_template.json evaluation/ground_truth/example_bank.json
```

Edit:

- `site_id` — must match the frozen file stem (`example_bank`)
- `url` — same URL that was crawled
- `frozen_at` — **copy exactly** from `evaluation/frozen_crawls/example_bank.json`
- `labelled_by` — real reviewer name (not `synthetic_*` for expert benchmarks)
- `pipeline_version` — optional; run `python -c "from backend.pipeline.versioning import compute_pipeline_version; print(compute_pipeline_version())"`

### 3. Label from frozen pages only

Open `evaluation/frozen_crawls/example_bank.json` → read `crawl_result.pages[].content`.

For each outcome, score criteria **1–10** (definitions in `backend/pipeline/scorer.py`):

- `awarded`: `1` = met, `0` = not met
- `note`: one-line evidence (quote or page URL from the **frozen** crawl)

Do **not** re-crawl or use the live website while labelling.

### 4. Run accuracy

```bash
python scripts/run_accuracy.py --site example_bank \
  --max-mae 1.5 \
  --min-rating-agreement 75
```

Exit code **1** if thresholds are not met.

---

## RAG ablation (is retrieval load-bearing?)

```bash
python scripts/run_rag_ablation.py --site example_retail_bank --fail-if-decorative
```

Runs the same frozen crawl twice: with FCA retrieval and with a null retriever. Flags **decorative RAG** when outcome scores and citation rates barely change.

---

## Files

| Path | Purpose |
|------|---------|
| `frozen_crawls/*.json` | Immutable crawl snapshot |
| `ground_truth/*.json` | Expert labels (skip `_template.json`) |
| `ground_truth/_template.json` | Blank 40-criterion schema |
| `benchmarks/default.json` | Structural harness manifest |

## Synthetic vs expert

| `labelled_by` | Use |
|---------------|-----|
| `synthetic_fixture_v1` | CI / math validation only |
| Real name | Expert benchmark (`--require-expert-labels`) |
