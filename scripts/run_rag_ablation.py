"""CLI: RAG ablation — run frozen crawl with and without FCA retrieval.

Usage:
    python scripts/run_rag_ablation.py --site example_retail_bank
    python scripts/run_rag_ablation.py --site example_retail_bank --fail-if-decorative

Requires GROQ_API_KEY and populated ChromaDB (``python -m backend.ingestion.fca_loader``).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.config import get_settings
from backend.evaluation.frozen_crawl import load_frozen_crawl, run_pipeline_from_frozen
from backend.evaluation.rag_ablation import compare_rag_ablation, format_ablation_report
from backend.ingestion.fca_loader import get_retriever, load_fca_docs, verify_chroma_populated
from backend.ingestion.null_retriever import NullFcaRetriever
from backend.schemas.audit import AuditReport


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG ablation: with vs without FCA retrieval.")
    parser.add_argument(
        "--frozen",
        default="evaluation/frozen_crawls",
        help="Directory of frozen crawl JSON files.",
    )
    parser.add_argument(
        "--site",
        default="example_retail_bank",
        help="site_id stem to replay.",
    )
    parser.add_argument(
        "--min-score-delta",
        type=float,
        default=0.25,
        help="Minimum outcome score MAE to consider RAG non-decorative.",
    )
    parser.add_argument(
        "--min-citation-delta",
        type=float,
        default=0.05,
        help="Minimum citation-rate change to consider RAG non-decorative.",
    )
    parser.add_argument(
        "--fail-if-decorative",
        action="store_true",
        help="Exit 1 when RAG does not materially change scores or citations.",
    )
    args = parser.parse_args()

    ok, msg = verify_chroma_populated()
    if not ok:
        print(f"ERROR: ChromaDB not populated — run fca_loader first. ({msg})")
        sys.exit(1)

    frozen_path = Path(args.frozen) / f"{args.site}.json"
    if not frozen_path.is_file():
        print(f"ERROR: frozen crawl not found: {frozen_path}")
        sys.exit(1)

    settings = get_settings()
    chroma = load_fca_docs(str(settings.fca_docs_dir))
    retriever = get_retriever(chroma, k=settings.rag_retrieval_k)
    null = NullFcaRetriever()

    frozen = load_frozen_crawl(frozen_path)
    crawl = frozen["crawl_result"]
    url = frozen["url"]

    print(f"[{args.site}] Running pipeline WITH FCA retrieval (live LLM)...")
    with_rag = run_pipeline_from_frozen(crawl, retriever, url=url)
    if not isinstance(with_rag, AuditReport):
        print(f"ERROR: with-RAG run early-exited: {with_rag.status}")
        sys.exit(1)

    print(f"[{args.site}] Running pipeline WITHOUT FCA retrieval (null retriever)...")
    without_rag = run_pipeline_from_frozen(crawl, null, url=url)
    if not isinstance(without_rag, AuditReport):
        print(f"ERROR: without-RAG run early-exited: {without_rag.status}")
        sys.exit(1)

    result = compare_rag_ablation(
        site_id=args.site,
        with_rag=with_rag,
        without_rag=without_rag,
        min_score_delta=args.min_score_delta,
        min_citation_delta=args.min_citation_delta,
    )
    print()
    print(format_ablation_report(result))

    if args.fail_if_decorative and result.rag_decorative:
        sys.exit(1)


if __name__ == "__main__":
    main()
