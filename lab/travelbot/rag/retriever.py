"""
rag/retriever.py — Query the TravelBot knowledge base
--------------------------------------------------------
Concept: RAG — grounding answers in retrieved context

Embeds an incoming query through OpenRouter's OpenAI embedding endpoint —
the same model and provider used at indexing time (see embed_catalog.py) —
and returns the closest-matching documents from the local 'travel_kb'
ChromaDB collection.

v3.agent calls retrieve() before answering so Aria can ground destination,
visa, and baggage questions in real knowledge-base text instead of guessing.
"""

import logging
import os

import chromadb
import litellm
from dotenv import load_dotenv

from settings import settings

litellm.suppress_debug_info = True
load_dotenv()

log = logging.getLogger(__name__)

# Lazily-opened singleton — opening the persistent collection touches disk,
# so do it once per process.
_collection = None


def _embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts via OpenRouter's OpenAI-compatible /embeddings endpoint."""
    response = litellm.embedding(
        model=settings.rag_embedding_model,
        input=texts,
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )
    return [item["embedding"] for item in response.data]


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(settings.rag_persist_path))
        _collection = client.get_or_create_collection(name=settings.rag_collection_name)
    return _collection


def retrieve(query: str, n_results: int = 3) -> list[dict]:
    """
    Return up to `n_results` knowledge-base entries most relevant to `query`.

    Each result is a dict: {"id", "text", "category", "distance"}
    (lower distance = closer match).

    Returns an empty list if the query is empty, the collection has not been
    indexed yet, or retrieval fails for any reason — callers should treat an
    empty list as "no grounded context available" rather than raising.
    """
    if not query or not query.strip():
        return []

    try:
        collection = _get_collection()
        count = collection.count()
        if count == 0:
            log.warning(
                "'%s' collection is empty — run `python -m rag.embed_catalog` first",
                settings.rag_collection_name,
            )
            return []

        embedding = _embed([query.strip()])
        result = collection.query(
            query_embeddings=embedding,
            n_results=min(n_results, count),
        )
    except Exception as exc:
        log.warning("Knowledge-base retrieval failed: %s", exc)
        return []

    ids = (result.get("ids") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    return [
        {
            "id": doc_id,
            "text": text,
            "category": (metadata or {}).get("category", "unknown"),
            "distance": distance,
        }
        for doc_id, text, metadata, distance in zip(ids, documents, metadatas, distances)
    ]
