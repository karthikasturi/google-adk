"""
rag/embed_catalog.py — Build the local travel knowledge base
---------------------------------------------------------------
Concept: RAG — Retrieval-Augmented Generation

Defines the seed documents for TravelBot's knowledge base (destination
guides, visa FAQs, baggage policies), embeds them via OpenRouter's OpenAI
embedding endpoint (using the same LiteLlm + OpenRouter setup as the chat
model — see shared/models.py), and stores them in a local persistent
ChromaDB collection so v3's agent can ground its answers in retrieved context.

Run once (or whenever DOCUMENTS changes) from lab/travelbot/:
    python -m rag.embed_catalog

Retrieval at answer time lives in rag/retriever.py.
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


def _embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts via OpenRouter's OpenAI-compatible /embeddings endpoint."""
    response = litellm.embedding(
        model=settings.rag_embedding_model,
        input=texts,
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )
    return [item["embedding"] for item in response.data]

# ── Knowledge base documents ────────────────────────────────────────────────
# Each entry: id (stable, used for upsert), text (what gets embedded and
# returned to the agent), category (destination / visa / baggage).
DOCUMENTS: list[dict[str, str]] = [
    # ── Destination guides ──────────────────────────────────────────────────
    {
        "id": "dest-bali",
        "category": "destination",
        "text": (
            "Bali, Indonesia is known for its beaches, rice terraces, and Hindu "
            "temples. The best time to visit is May to September, during the dry "
            "season. Seminyak is popular for nightlife, Ubud for culture and "
            "nature, and Nusa Dua for resorts. The local currency is the "
            "Indonesian Rupiah (IDR); bargaining is common in markets but not in "
            "shops or malls."
        ),
    },
    {
        "id": "dest-paris",
        "category": "destination",
        "text": (
            "Paris, France is famous for the Eiffel Tower, the Louvre, and "
            "Notre-Dame Cathedral. The Metro is the easiest way to get around, "
            "and a Navigo Easy card covers buses and trains. Many museums are "
            "free on the first Sunday of the month. Tipping is not expected — a "
            "service charge is included in restaurant bills by law."
        ),
    },
    {
        "id": "dest-dubai",
        "category": "destination",
        "text": (
            "Dubai, UAE blends modern landmarks like the Burj Khalifa with "
            "traditional souks and desert safaris. The Dubai Metro is "
            "air-conditioned and affordable, and Friday is part of the local "
            "weekend. Dress modestly in malls and public spaces — alcohol is "
            "served only in licensed hotels, bars, and restaurants."
        ),
    },
    {
        "id": "dest-tokyo",
        "category": "destination",
        "text": (
            "Tokyo, Japan mixes ultramodern districts like Shibuya and Shinjuku "
            "with historic neighbourhoods like Asakusa. The JR Yamanote loop "
            "line connects most major districts, and a Suica or Pasmo IC card "
            "works on trains, buses, and at convenience stores. Cash is still "
            "widely used, so carry yen for smaller shops and food stalls."
        ),
    },
    {
        "id": "dest-singapore",
        "category": "destination",
        "text": (
            "Singapore is a compact city-state known for Gardens by the Bay, "
            "Marina Bay Sands, and its hawker-centre food culture. The MRT "
            "subway is clean, fast, and covers the whole island. Importing "
            "chewing gum is restricted, and littering or jaywalking carry real "
            "fines, so follow posted rules carefully."
        ),
    },
    # ── Visa FAQs ───────────────────────────────────────────────────────────
    {
        "id": "visa-uk-indian-passport",
        "category": "visa",
        "text": (
            "Indian passport holders generally need a visa to visit the United "
            "Kingdom for tourism. Standard visitor visas are usually valid for "
            "six months, are applied for online before travel, and require "
            "biometrics at a visa application centre. Processing typically "
            "takes about three weeks, so apply well in advance of the trip."
        ),
    },
    {
        "id": "visa-us-esta",
        "category": "visa",
        "text": (
            "Travellers from Visa Waiver Program countries can visit the United "
            "States for short tourist or business trips using an approved ESTA "
            "(Electronic System for Travel Authorization) instead of a visa. "
            "ESTA approval is generally valid for two years and allows stays of "
            "up to 90 days per visit — apply online at least 72 hours before departure."
        ),
    },
    {
        "id": "visa-uae-on-arrival",
        "category": "visa",
        "text": (
            "Citizens of many countries — including the UK, the US, and EU "
            "member states — can get a visa on arrival in the United Arab "
            "Emirates, usually valid for 30 to 90 days depending on nationality. "
            "Travellers without visa-on-arrival access should apply for an "
            "e-visa online before departure."
        ),
    },
    {
        "id": "visa-schengen-short-stay",
        "category": "visa",
        "text": (
            "A Schengen short-stay visa allows visits of up to 90 days within "
            "any 180-day period across the Schengen member countries, for "
            "tourism, business, or family visits. Applications go to the "
            "consulate of the main destination country, and proof of "
            "accommodation, funds, and travel insurance is usually required."
        ),
    },
    # ── Baggage policy ──────────────────────────────────────────────────────
    {
        "id": "baggage-checked-economy",
        "category": "baggage",
        "text": (
            "On most international economy fares, passengers are allowed one "
            "checked bag up to 23 kg (50 lb), with maximum linear dimensions "
            "(length + width + height) of around 158 cm (62 in). Bags over the "
            "weight limit are charged an excess-baggage fee per kilogram, which "
            "varies by airline and route."
        ),
    },
    {
        "id": "baggage-carry-on",
        "category": "baggage",
        "text": (
            "Carry-on baggage is typically limited to one cabin bag plus one "
            "personal item, such as a laptop bag or handbag. The cabin bag "
            "should generally not exceed about 56 x 36 x 23 cm and 7-10 kg. "
            "Liquids in carry-on bags must be in containers of 100 ml or less, "
            "placed together in a single transparent resealable bag."
        ),
    },
    {
        "id": "baggage-special-items",
        "category": "baggage",
        "text": (
            "Sports equipment, musical instruments, and other oversized items — "
            "such as surfboards, bicycles, or golf bags — usually need to be "
            "registered with the airline in advance and may incur additional "
            "handling fees even when they fit within the standard weight "
            "allowance. Fragile items should be packed in hard cases."
        ),
    },
]


def _get_collection():
    client = chromadb.PersistentClient(path=str(settings.rag_persist_path))
    return client.get_or_create_collection(name=settings.rag_collection_name)


def index_catalog() -> None:
    """Embed every document in DOCUMENTS and upsert it into the travel_kb collection."""
    collection = _get_collection()

    embeddings = _embed([doc["text"] for doc in DOCUMENTS])

    collection.upsert(
        ids=[doc["id"] for doc in DOCUMENTS],
        documents=[doc["text"] for doc in DOCUMENTS],
        metadatas=[{"category": doc["category"]} for doc in DOCUMENTS],
        embeddings=embeddings,
    )

    print(
        f"Indexed {len(DOCUMENTS)} documents into ChromaDB collection "
        f"'{settings.rag_collection_name}' at {settings.rag_persist_path} "
        f"(model: {settings.rag_embedding_model})."
    )


if __name__ == "__main__":
    index_catalog()
