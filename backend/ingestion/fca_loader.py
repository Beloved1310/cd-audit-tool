"""Load FCA PDFs into a persistent ChromaDB index (local HuggingFace embeddings)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.vectorstores import VectorStoreRetriever

from backend.config import get_settings

COLLECTION_NAME = "fca_guidance"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
CORPUS_MANIFEST_FILENAME = ".fca_corpus_manifest.json"


def _persist_dir() -> str:
    return str(get_settings().chroma_persist_dir)


def _embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
    )


def _normalized_stem(filename: str) -> str:
    """Lowercase stem with only alphanumerics (fg22-5 → fg225, PS22_9_ → ps229)."""
    stem = Path(filename).stem.lower()
    return "".join(c for c in stem if c.isalnum())


def _citation_label(filename: str) -> str:
    """Map PDF filename to a short citation label for prompts and metadata."""
    low = filename.lower()
    norm = _normalized_stem(filename)
    if low == "fg22-5.pdf" or norm in {"fg225", "fg22"}:
        return "FG22/5"
    # ps22-9.pdf, PS22_9_ A new Consumer Duty.pdf, etc.
    if low == "ps22-9.pdf" or norm.startswith("ps229") or norm == "ps229":
        return "PS22/9"
    if "understanding" in low:
        return "Consumer Understanding Good Practice"
    if "support" in low:
        return "Consumer Support Good Practice"
    if "vulnerable" in low:
        return "FCA Vulnerable Customers Guidance"
    return Path(filename).stem.replace("-", " ")


def corpus_manifest(docs_dir: str | Path) -> dict:
    """Fingerprint of every PDF in ``docs_dir`` (used for drift detection and versioning)."""
    folder = Path(docs_dir).resolve()
    files: list[dict[str, str | int]] = []
    for pdf_path in sorted(folder.glob("*.pdf")):
        data = pdf_path.read_bytes()
        files.append(
            {
                "name": pdf_path.name,
                "size": pdf_path.stat().st_size,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return {"pdf_count": len(files), "files": files}


def corpus_manifest_digest(docs_dir: str | Path) -> str:
    """Stable SHA-256 hex digest of the on-disk FCA PDF set."""
    payload = json.dumps(corpus_manifest(docs_dir), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _manifest_path() -> Path:
    return Path(_persist_dir()) / CORPUS_MANIFEST_FILENAME


def _write_corpus_manifest(docs_dir: Path) -> None:
    path = _manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(corpus_manifest(docs_dir), indent=2), encoding="utf-8")


def _stored_manifest_matches(docs_dir: Path) -> bool:
    path = _manifest_path()
    if not path.is_file():
        return False
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return stored == corpus_manifest(docs_dir)


def _human_page_number(metadata: dict) -> int:
    """PyPDFLoader typically uses 0-based page; expose 1-based page for citations."""
    p = metadata.get("page")
    if p is None:
        return 1
    try:
        n = int(p)
    except (TypeError, ValueError):
        return 1
    return n + 1


def _delete_collection() -> None:
    """Remove the persisted ``fca_guidance`` collection so a full re-ingest can run."""
    persist = _persist_dir()
    if not os.path.isdir(persist):
        return
    emb = _embeddings()
    try:
        Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=emb,
            persist_directory=persist,
        ).delete_collection()
    except Exception:  
        pass


def _collection_has_documents(chroma: Chroma) -> bool:
    try:
        coll = getattr(chroma, "_collection", None)
        if coll is not None and hasattr(coll, "count"):
            return int(coll.count()) > 0
        data = chroma.get(include=[])
        return len(data.get("ids") or []) > 0
    except Exception:  # noqa: BLE001
        return False


def load_fca_docs(docs_dir: str) -> Chroma:
    """
    Read all PDFs from ``docs_dir``, chunk, embed locally, and persist to Chroma.

    If the ``fca_guidance`` collection already exists and contains documents,
    re-ingestion is skipped and the existing store is returned.
    """
    folder = Path(docs_dir).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    persist = _persist_dir()
    os.makedirs(persist, exist_ok=True)

    emb = _embeddings()
    chroma = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=emb,
        persist_directory=persist,
    )

    if _collection_has_documents(chroma):
        if not _stored_manifest_matches(folder):
            print(
                f"Collection '{COLLECTION_NAME}' exists but fca_docs/ changed "
                f"(missing or new PDFs). Re-run with --reset to include all documents:\n"
                f"  python -m backend.ingestion.fca_loader --reset",
                file=sys.stderr,
            )
        else:
            print(
                f"Collection '{COLLECTION_NAME}' already has documents; skipping re-ingestion.",
            )
        return chroma

    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        print(f"No PDF files found in {folder}; nothing to ingest.")
        return chroma

    label_for = {p.name: _citation_label(p.name) for p in pdfs}
    all_chunks: list[Document] = []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    for pdf_path in pdfs:
        cite_label = label_for[pdf_path.name]
        loader = PyPDFLoader(str(pdf_path))
        page_docs = loader.load()
        prepared: list[Document] = []
        for d in page_docs:
            meta = dict(d.metadata or {})
            meta["source"] = pdf_path.name
            human_page = _human_page_number(meta)
            meta["page"] = human_page
            meta["citation"] = f"{cite_label}, p.{human_page}"
            d.metadata = meta
            prepared.append(d)

        file_splits = splitter.split_documents(prepared)
        chunk_index = 0
        for d in file_splits:
            chunk_index += 1
            m = dict(d.metadata)
            m["chunk_index"] = chunk_index
            d.metadata = m
            all_chunks.append(d)

    Chroma.from_documents(
        documents=all_chunks,
        embedding=emb,
        persist_directory=persist,
        collection_name=COLLECTION_NAME,
    )

    _write_corpus_manifest(folder)
    print(
        f"Ingestion summary: PDFs processed={len(pdfs)}, total chunks created={len(all_chunks)}",
    )
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=emb,
        persist_directory=persist,
    )


def get_retriever(chroma: Chroma, k: int = 5) -> VectorStoreRetriever:
    """Top-``k`` similarity retriever returning full :class:`~langchain_core.documents.Document` objects."""
    return chroma.as_retriever(search_kwargs={"k": k})


def merge_retrieved_docs(
    retriever: VectorStoreRetriever,
    *queries: str,
    k_each: int = 4,
    max_docs: int = 8,
) -> list[Document]:
    """Run multiple queries and return deduplicated chunks (by citation), preserving order."""
    seen: set[str] = set()
    out: list[Document] = []
    for query in queries:
        for doc in retriever.invoke(query)[:k_each]:
            citation = (doc.metadata or {}).get("citation")
            key = citation if isinstance(citation, str) and citation.strip() else doc.page_content[:80]
            if key in seen:
                continue
            seen.add(key)
            out.append(doc)
            if len(out) >= max_docs:
                return out
    return out


def get_sources_from_docs(docs: list[Document]) -> list[str]:
    """Deduplicated ``citation`` strings from chunk metadata (verified prompt sources)."""
    seen: set[str] = set()
    out: list[str] = []
    for d in docs:
        c = (d.metadata or {}).get("citation")
        if isinstance(c, str) and c.strip() and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def verify_chroma_populated(min_chunks: int = 1) -> tuple[bool, str]:
    """Return ``(ok, detail)`` for health checks and CLI verify."""
    persist = _persist_dir()
    if not os.path.isdir(persist):
        return False, f"Chroma persist directory missing: {persist}"
    try:
        emb = _embeddings()
        chroma = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=emb,
            persist_directory=persist,
        )
        coll = getattr(chroma, "_collection", None)
        if coll is not None and hasattr(coll, "count"):
            count = int(coll.count())
        else:
            data = chroma.get(include=[])
            count = len(data.get("ids") or [])
    except Exception as e:  # noqa: BLE001
        return False, f"Chroma error: {e}"
    if count < min_chunks:
        return (
            False,
            f"Chroma collection '{COLLECTION_NAME}' has {count} chunks; need >= {min_chunks}. Run ingestion.",
        )
    return True, f"Chroma OK: {count} chunks in '{COLLECTION_NAME}'"


def retrieve_for_query(query: str, k: int = 6) -> list[dict]:
    """
    Similarity search for pipeline prompts.

    Each item: ``source_id``, ``text``, ``metadata``, ``document_label`` (citation string).
    """
    docs_dir = str(get_settings().fca_docs_dir)
    chroma = load_fca_docs(docs_dir)
    retriever = get_retriever(chroma, k=k)
    docs = retriever.invoke(query)
    out: list[dict] = []
    for i, d in enumerate(docs):
        meta = dict(d.metadata or {})
        label = meta.get("citation") or meta.get("source") or "FCA document"
        out.append(
            {
                "source_id": f"fca_chunk_{i}",
                "text": d.page_content,
                "metadata": meta,
                "document_label": label,
            }
        )
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FCA PDF → Chroma (fca_guidance)")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only check that the collection has chunks (no ingestion).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the existing collection on disk, then re-ingest all PDFs.",
    )
    args = parser.parse_args()

    if args.verify_only:
        ok, msg = verify_chroma_populated()
        print(msg)
        sys.exit(0 if ok else 1)

    docs_dir = str(get_settings().fca_docs_dir)
    print(f"FCA docs directory: {Path(docs_dir).resolve()}")
    print(f"Chroma persist: {Path(_persist_dir()).resolve()}")
    print(f"Collection: {COLLECTION_NAME}")
    if args.reset:
        print("Removing existing collection (--reset)…")
        _delete_collection()
    print("Loading / ingesting…")
    load_fca_docs(docs_dir)
    ok, msg = verify_chroma_populated()
    print(msg)
    if ok:
        print("Collection is ready for retrieval.")
    sys.exit(0 if ok else 1)
