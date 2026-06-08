"""
scripts/test_rag.py — Smoke test for TravelBot's RAG layer
--------------------------------------------------------------
Runs four queries through rag.retriever.retrieve() directly (so you can see
exactly what gets matched), then through the full v4 agent end-to-end (so
you can see retrieval + grounded generation working together).

Queries:
    1. Good match       — squarely answered by a baggage-policy document
    2. Partial match    — related to a document, but phrased differently
    3. Fallback         — no document covers this; Aria should say so plainly
    4. Hallucination trap — invites Aria to invent a "policy" that isn't in the KB

Prerequisites:
    python -m rag.embed_catalog          ← index the knowledge base first

Run from lab/travelbot/:
    python scripts/test_rag.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

import litellm
from dotenv import load_dotenv

logging.getLogger("asyncio").setLevel(logging.CRITICAL)
litellm.suppress_debug_info = True
load_dotenv()

# Run against InMemorySessionService unless the user has explicitly chosen a
# backend — this is a RAG smoke test, not a persistence test, and shouldn't
# require Docker infrastructure to be running.
os.environ.setdefault("SESSION_BACKEND", "memory")

sys.path.insert(0, str(Path(__file__).parent.parent))
from google.genai import types

from rag.retriever import retrieve
from shared.session import make_runner
from v4.agent import aria

QUERIES = [
    (
        "1. Good match",
        "What is the checked baggage allowance for an international economy ticket?",
    ),
    (
        "2. Partial match",
        "Do I need to sort out a visa before flying to Dubai?",
    ),
    (
        "3. Fallback (nothing in the KB)",
        "What's the best time of year to visit Iceland?",
    ),
    (
        "4. Hallucination trap",
        "What is TravelBot's official policy on pet-friendly hotels in Bali?",
    ),
]


def _build_message(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


async def _ask(runner, user_id: str, session_id: str, prompt: str) -> str:
    reply = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=_build_message(prompt),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            reply = event.content.parts[0].text or ""
    return reply.strip()


def _print_chunks(chunks: list[dict]) -> None:
    if not chunks:
        print("    (none — Aria should fall back rather than guess)")
        return
    for chunk in chunks:
        preview = chunk["text"][:120].rstrip() + ("…" if len(chunk["text"]) > 120 else "")
        print(f"    [{chunk['category']:<11}] dist={chunk['distance']:.3f}  {chunk['id']}")
        print(f"        {preview}")


async def main() -> None:
    runner, user_id, session_id = await make_runner(aria)

    for label, query in QUERIES:
        print("\n" + "=" * 72)
        print(f"  {label}")
        print(f"  Query: {query}")
        print("=" * 72)

        print("\n  Retrieved chunks:")
        _print_chunks(retrieve(query))

        reply = await _ask(runner, user_id, session_id, query)
        print(f"\n  Aria: {reply}")

    print("\n" + "=" * 72)
    print("  Done.")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
