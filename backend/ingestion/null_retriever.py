"""Empty retriever for RAG ablation (pipeline runs with no FCA chunks)."""

from __future__ import annotations


class NullFcaRetriever:
    """Retriever that always returns no documents."""

    def invoke(self, query: str) -> list:
        return []
