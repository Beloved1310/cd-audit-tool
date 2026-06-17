"""BM25 + dense vector retrieval fused with reciprocal rank fusion (RRF)."""

from __future__ import annotations

import logging
from typing import Any

from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from backend.config import get_settings

logger = logging.getLogger(__name__)


def _doc_dedupe_key(doc: Document) -> str:
    citation = (doc.metadata or {}).get("citation")
    if isinstance(citation, str) and citation.strip():
        return citation.strip()
    return doc.page_content[:120]


def reciprocal_rank_fusion(
    ranked_lists: list[list[Document]],
    *,
    max_docs: int,
    rrf_k: int = 60,
) -> list[Document]:
    """Merge ranked document lists with standard RRF scoring."""
    scores: dict[str, float] = {}
    by_key: dict[str, Document] = {}
    for docs in ranked_lists:
        for rank, doc in enumerate(docs):
            key = _doc_dedupe_key(doc)
            scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)
            by_key[key] = doc
    ordered = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    return [by_key[k] for k in ordered[:max_docs]]


def load_all_chroma_documents(chroma: Chroma) -> list[Document]:
    """Load every chunk from Chroma for the in-memory BM25 index."""
    data = chroma.get(include=["documents", "metadatas"])
    texts = data.get("documents") or []
    metas = data.get("metadatas") or []
    docs: list[Document] = []
    for text, meta in zip(texts, metas):
        if not (text or "").strip():
            continue
        docs.append(Document(page_content=text, metadata=dict(meta or {})))
    return docs


class HybridFcaRetriever:
    """Fuse BM25 keyword hits with Chroma vector similarity via RRF."""

    def __init__(
        self,
        *,
        vector_retriever: Any,
        bm25_retriever: BM25Retriever,
        k: int,
        candidate_k: int,
        rrf_k: int,
    ) -> None:
        self._vector = vector_retriever
        self._bm25 = bm25_retriever
        self._k = k
        self._candidate_k = candidate_k
        self._rrf_k = rrf_k

    def invoke(self, query: str) -> list[Document]:
        vector_docs = self._vector.invoke(query)
        bm25_docs = self._bm25.invoke(query)
        return reciprocal_rank_fusion(
            [vector_docs[: self._candidate_k], bm25_docs[: self._candidate_k]],
            max_docs=self._k,
            rrf_k=self._rrf_k,
        )


def build_hybrid_retriever(chroma: Chroma, *, k: int) -> HybridFcaRetriever | Any:
    """Build hybrid retriever or fall back to vector-only when BM25 cannot run."""
    settings = get_settings()
    candidate_k = min(max(k * 2, k), settings.rag_hybrid_candidate_k)
    vector = chroma.as_retriever(search_kwargs={"k": candidate_k})

    docs = load_all_chroma_documents(chroma)
    if not docs:
        logger.warning("Chroma empty — hybrid retriever falling back to vector-only")
        return chroma.as_retriever(search_kwargs={"k": k})

    bm25 = BM25Retriever.from_documents(docs)
    bm25.k = candidate_k
    logger.info(
        "Hybrid retriever ready: %s chunks, k=%s, candidate_k=%s",
        len(docs),
        k,
        candidate_k,
    )
    return HybridFcaRetriever(
        vector_retriever=vector,
        bm25_retriever=bm25,
        k=k,
        candidate_k=candidate_k,
        rrf_k=settings.rag_hybrid_rrf_k,
    )
