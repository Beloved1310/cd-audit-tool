"""Load ``.env`` and disable Chroma telemetry before ``chromadb`` is imported."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Chroma uses PostHog at import/query time; posthog>=3 breaks capture() (harmless but noisy).
if os.environ.get("ANONYMIZED_TELEMETRY", "").strip().lower() in ("", "false", "0", "no"):
    os.environ["ANONYMIZED_TELEMETRY"] = "False"
