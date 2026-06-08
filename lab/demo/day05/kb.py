"""
kb.py — Tiny ChromaDB-backed knowledge base for semantic search & RAG
------------------------------------------------------------------------
Concept: Module 5 — Semantic Search and Retrieval-Augmented Generation

The pipeline, end to end, in one short file:

    1. Embed every document once (OpenRouter's OpenAI embedding endpoint
       via LiteLlm — the same provider as the chat model, see agent.py)
       and upsert them into an in-memory ChromaDB collection.
    2. Embed the incoming query the same way.
    3. Ask ChromaDB for the top_k nearest documents by vector distance.

ChromaDB runs here as an *ephemeral*, in-process client — no server, no
files left on disk — which keeps the demo a one-command `python demo.py`
while still showing the real article: a vector database doing the
similarity search, not a hand-rolled loop.

For a persistent, production-shaped version of this same idea — a larger
catalog, on-disk storage, metadata filtering — see the RAG layer in
lab/travelbot/rag/ (embed_catalog.py + retriever.py).
"""

import os

import chromadb
import litellm
from dotenv import load_dotenv

load_dotenv()
litellm.suppress_debug_info = True

EMBEDDING_MODEL = "openrouter/openai/text-embedding-3-small"
COLLECTION_NAME = "day05_travel_kb"

# ── Knowledge base ──────────────────────────────────────────────────────────
# A handful of short travel-tip documents. The last two are TravelBot-specific
# "policies" that no general-purpose model could already know — they're what
# make Scenario 2 in demo.py convincing: when the agent gets these right, it's
# clearly because it retrieved them, not because it was trained on them.
DOCUMENTS: list[dict[str, str]] = [
    {
        "id": "jetlag-tips",
        "text": (
            "To reduce jet lag on long-haul flights, start shifting your sleep "
            "schedule a few days before departure, stay hydrated, avoid alcohol "
            "in flight, and get natural sunlight at your destination as soon as "
            "possible to reset your body clock."
        ),
    },
    {
        "id": "travel-insurance-basics",
        "text": (
            "Travel insurance typically covers trip cancellation, emergency "
            "medical care, and lost or delayed baggage. Compare policies "
            "carefully — coverage limits, exclusions, and claim procedures vary "
            "significantly between providers."
        ),
    },
    {
        "id": "currency-cards-abroad",
        "text": (
            "Notify your bank before traveling internationally so card payments "
            "aren't flagged as suspicious. Carry a small amount of local cash "
            "for emergencies, and avoid exchanging money at airport counters — "
            "their rates are usually the worst available."
        ),
    },
    {
        "id": "power-adapters-voltage",
        "text": (
            "Check your destination's plug shape and voltage before you travel. "
            "A universal travel adapter covers most countries, but high-wattage "
            "devices like hair dryers may also need a separate voltage converter."
        ),
    },
    {
        "id": "esim-roaming-tips",
        "text": (
            "A local prepaid SIM or eSIM is usually far cheaper than your home "
            "carrier's roaming rates. Check that your phone is unlocked and "
            "supports the destination's network bands before you buy one."
        ),
    },
    {
        "id": "packing-light-basics",
        "text": (
            "Pack light by choosing versatile, mix-and-match clothing, rolling "
            "items instead of folding them, and using packing cubes to compress "
            "and organize your bag. Leave a little extra space for souvenirs."
        ),
    },
    {
        "id": "travelbot-cancellation-policy",
        "text": (
            "TravelBot's 24-hour free cancellation policy lets you cancel any "
            "booking made through the TravelBot app at no charge, as long as "
            "you cancel within 24 hours of purchase and the trip departs more "
            "than seven days later."
        ),
    },
    {
        "id": "travelbot-elite-loyalty",
        "text": (
            "TravelBot Elite members earn double loyalty points on weekend "
            "bookings and unlock free seat selection after their fifth completed "
            "trip. Elite status is reviewed annually based on total nights booked."
        ),
    },
]


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts via OpenRouter's OpenAI-compatible /embeddings endpoint."""
    response = litellm.embedding(
        model=EMBEDDING_MODEL,
        input=texts,
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )
    return [item["embedding"] for item in response.data]


# Opened once per process — building the collection means embedding every
# document, so it's worth caching the client/collection as a singleton.
_collection = None


def _get_collection():
    """Return the (lazily indexed) in-memory ChromaDB collection of DOCUMENTS."""
    global _collection
    if _collection is None:
        client = chromadb.EphemeralClient()
        collection = client.get_or_create_collection(name=COLLECTION_NAME)
        collection.upsert(
            ids=[doc["id"] for doc in DOCUMENTS],
            documents=[doc["text"] for doc in DOCUMENTS],
            embeddings=embed([doc["text"] for doc in DOCUMENTS]),
        )
        _collection = collection
    return _collection


def semantic_search(query: str, top_k: int = 3) -> list[dict]:
    """
    Return the top_k documents whose embeddings are closest — by vector
    distance, as judged by ChromaDB — to the query's embedding.

    Each result is a dict: {"id", "text", "score"} where score is a
    similarity in [0, 1] derived from ChromaDB's distance (higher = closer
    match), so callers don't need to know which distance metric is in use.
    Returns an empty list for an empty query.
    """
    if not query or not query.strip():
        return []

    collection = _get_collection()
    result = collection.query(
        query_embeddings=embed([query.strip()]),
        n_results=min(top_k, collection.count()),
    )

    ids = (result.get("ids") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    return [
        {"id": doc_id, "text": text, "score": 1.0 / (1.0 + distance)}
        for doc_id, text, distance in zip(ids, documents, distances)
    ]
