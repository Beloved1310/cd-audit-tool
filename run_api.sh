#!/usr/bin/env bash
# Run the FastAPI app with correct PYTHONPATH (repo root).
# Usage: from anywhere:  ./run_api.sh   or   bash run_api.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$ROOT"
cd "$ROOT"
exec python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
