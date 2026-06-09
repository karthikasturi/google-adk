"""
kb.py — PDF-backed knowledge base with a configurable vector store
----------------------------------------------------------------------
Concept: Module 6 — Loading real documents, metadata, and swappable
vector databases (in-memory ChromaDB for dev, AWS OpenSearch for prod)

The pipeline, end to end:

    1. Load every PDF in docs/, extract text page by page (pypdf), and
       attach metadata — {"source": filename, "page": N} — so retrieved
       chunks can always be traced back to where they came from.
    2. Embed each page once (OpenRouter's OpenAI embedding endpoint via
       LiteLlm — same provider as the chat model, see agent.py) and
       upsert into the configured vector backend.
    3. Embed the incoming query the same way and ask the backend for the
       top_k nearest chunks by vector distance, metadata included.

VECTOR_BACKEND env var selects where the vectors live — the single swap
point, same idea as Day 04's SESSION_BACKEND for session storage:

    memory                 → ChromaDB EphemeralClient, in-process, nothing
                             to set up (default — what the scripted demo
                             runs against)
    opensearch             → AWS OpenSearch k-NN index on a managed domain
    opensearch-serverless  → AWS OpenSearch Serverless k-NN collection

Both OpenSearch options need OPENSEARCH_HOST, an AWS region, and credentials
the default boto3 chain can find — see .env.example and README.md for a full
walkthrough of provisioning a Serverless collection from scratch.

Whichever backend is active, semantic_search() returns the same shape, so
agent.py and the demo scenarios don't change at all when you swap backends.
"""

import os
from pathlib import Path
from typing import Any

import litellm
from dotenv import load_dotenv
from pypdf import PdfReader

from backends import MemoryBackend, OpenSearchBackend

load_dotenv()
litellm.suppress_debug_info = True

EMBEDDING_MODEL = "openrouter/openai/text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
COLLECTION_NAME = "day06_travel_docs"
DOCS_DIR = Path(__file__).parent / "docs"


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts via OpenRouter's OpenAI-compatible /embeddings endpoint."""
    response = litellm.embedding(
        model=EMBEDDING_MODEL,
        input=texts,
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )
    return [item["embedding"] for item in response.data]


# ── PDF loading ─────────────────────────────────────────────────────────────

def load_pdf_chunks(docs_dir: Path = DOCS_DIR) -> list[dict[str, Any]]:
    """
    Read every *.pdf in docs_dir and return one chunk per non-empty page.

    Keeping "one page = one chunk" is the simplest possible splitting
    strategy — good enough for short reference documents like these, and
    it keeps the metadata easy to reason about: every chunk can point back
    to an exact (source file, page number). A production pipeline would
    likely also split long pages into smaller overlapping windows.

    Each chunk is {"id", "text", "metadata": {"source", "page"}}.
    """
    chunks = []
    for pdf_path in sorted(docs_dir.glob("*.pdf")):
        reader = PdfReader(str(pdf_path))
        for page_num, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            chunks.append({
                "id": f"{pdf_path.stem}-p{page_num}",
                "text": text,
                "metadata": {"source": pdf_path.name, "page": page_num},
            })
    return chunks


# ── Backend selection & indexing ────────────────────────────────────────────
# Opened once per process — building the index means embedding every chunk,
# so it's worth caching the backend as a singleton (same pattern as Day 05's
# _get_collection).
_backend = None


def get_backend():
    """
    Return the (lazily indexed) configured vector backend, loaded with
    every PDF chunk under docs/.

    VECTOR_BACKEND chooses the implementation; everything else about
    indexing — load, embed, upsert — is identical either way.

        memory                → MemoryBackend (ChromaDB, default)
        opensearch            → OpenSearchBackend, managed domain
        opensearch-serverless → OpenSearchBackend, Serverless collection
                                (same class — only the SigV4 service name
                                and a couple of API quirks differ; see
                                backends.OpenSearchBackend)
    """
    global _backend
    if _backend is not None:
        return _backend

    kind = os.getenv("VECTOR_BACKEND", "memory").strip().lower()
    if kind in ("opensearch", "opensearch-serverless"):
        backend = OpenSearchBackend(
            host=os.environ["OPENSEARCH_HOST"],
            region=os.getenv("AWS_REGION", "us-east-1"),
            index_name=os.getenv("OPENSEARCH_INDEX", COLLECTION_NAME),
            dimension=EMBEDDING_DIMENSION,
            serverless=(kind == "opensearch-serverless"),
        )
    else:
        backend = MemoryBackend(collection_name=COLLECTION_NAME)

    # Re-index on every startup, same as Day 05's _get_collection — upsert is
    # idempotent (chunk IDs are deterministic, so re-running just overwrites),
    # and it keeps the backend's contents guaranteed to match what's in docs/
    # right now rather than whatever was indexed last time.
    chunks = load_pdf_chunks()
    if chunks:
        backend.upsert(
            ids=[c["id"] for c in chunks],
            texts=[c["text"] for c in chunks],
            embeddings=embed([c["text"] for c in chunks]),
            metadatas=[c["metadata"] for c in chunks],
        )

    _backend = backend
    return _backend


def semantic_search(query: str, top_k: int = 3) -> list[dict]:
    """
    Return the top_k chunks whose embeddings are closest — by vector
    distance, as judged by the configured backend — to the query's
    embedding.

    Each result is a dict: {"id", "text", "metadata", "score"} where
    metadata carries {"source", "page"} and score is a similarity in
    (0, 1] (higher = closer match), so callers don't need to know which
    backend or distance metric is in use. Returns an empty list for an
    empty query.
    """
    if not query or not query.strip():
        return []

    backend = get_backend()
    return backend.query(embed([query.strip()])[0], top_k=top_k)
