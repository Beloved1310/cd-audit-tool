"""CLI: run a live crawl and save the result to disk for accuracy benchmarking.

Usage:
    python scripts/freeze_crawl.py --url https://example-bank.co.uk \\
        --out evaluation/frozen_crawls/example-bank.json \\
        [--site-id example-bank]

The saved file can then be:
  1. Handed to a human expert to label (evaluation/ground_truth/<site_id>.json)
  2. Replayed against the pipeline without re-crawling (scripts/run_accuracy.py)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on the path when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.crawler.site_crawler import crawl_website
from backend.evaluation.frozen_crawl import save_frozen_crawl


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze a live crawl for accuracy benchmarking.")
    parser.add_argument("--url", required=True, help="URL to crawl.")
    parser.add_argument(
        "--out",
        required=True,
        help="Output path for the frozen crawl JSON (e.g. evaluation/frozen_crawls/example.json).",
    )
    parser.add_argument(
        "--site-id",
        default="",
        help="Short identifier for this site (defaults to output filename stem).",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    site_id = args.site_id or out_path.stem

    print(f"Crawling: {args.url}")
    result = crawl_website(args.url)
    print(
        f"Crawl complete: {len(result.pages)} pages, {result.total_words} words, "
        f"method={result.crawl_method}"
    )

    save_frozen_crawl(result, out_path, site_id=site_id, url=args.url)
    print(f"Frozen crawl saved to: {out_path.resolve()}")
    print()
    print("Next step: create a matching expert label file at:")
    print(f"  evaluation/ground_truth/{site_id}.json")
    print("Use the ground truth schema in backend/evaluation/ground_truth.py as a template.")


if __name__ == "__main__":
    main()
