"""
agent.py — TravelBot v4: PostgreSQL Tools + Session Persistence + RAG
======================================================================
Concept: Retrieval-Augmented Generation on top of the v3 production stack

v4 is v3 plus exactly one addition: a local knowledge base (destination
guides, visa FAQs, baggage policies) that grounds Aria's answers to
questions her tools can't handle. Everything from v3 — PostgreSQL-backed
tools, configurable session storage, Redis state cache, durable
conversation history — is untouched; see v3/agent.py for those.

RAG knowledge base (new in v4):
    Before each turn, rag.retriever.retrieve() looks up the most relevant
    destination-guide / visa-FAQ / baggage-policy chunks for the user's
    latest message in the local ChromaDB 'travel_kb' collection, and the
    matches are woven into the instruction for that turn — see
    _build_instruction() below. Index the catalog first:
        python -m rag.embed_catalog

Import and use:
    from v4.agent import aria
    runner, user_id, session_id = await make_runner(aria)

Try these prompts in sequence (one session):
    "Check booking TB-1001 for me."
    "What's the passenger name?"        ← follow-up, no ID repeated
    "Find flights from Mumbai to London."
    "Cancel booking TB-1002."
    "What's the baggage allowance for an economy ticket?"   ← RAG-grounded
    "Do I need a visa to visit Dubai?"                       ← RAG-grounded
"""

import sys
from pathlib import Path

import litellm
from dotenv import load_dotenv

litellm.suppress_debug_info = True
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))
from google.adk.agents.readonly_context import ReadonlyContext

from rag.retriever import retrieve
from settings import settings
from shared.models import build_agent
from shared.tools import TOOLS_V3

# ── Base instruction ───────────────────────────────────────────────────────
# Identical to v3's, plus a knowledge-base capability line and grounding
# rules for the new RAG-backed topics.
_BASE_INSTRUCTION = """
You are Aria, a professional travel assistant for TravelBot.

Your capabilities (v4 — production persistence + knowledge base):
- Look up any booking by ID using get_booking_status.
- Cancel a confirmed booking using cancel_booking.
- Search for available flights using search_flights.
- Check flight status using get_flight_status.
- Search for hotels using search_hotels.
- Save the traveler's name using save_traveler_name.
- Return a structured trip summary using get_trip_summary.
- Answer destination-guide, visa, and baggage-policy questions using the
  "Retrieved knowledge base context" provided below your instructions.

Guidelines:
- Always call the appropriate tool — do NOT guess booking details or flights.
  All data comes from a live PostgreSQL database.
- Once a booking ID is saved in the session, refer to it as "your booking"
  in follow-up questions without asking the user to repeat it.
- If the user says "cancel my booking" and a booking ID is in context,
  call cancel_booking with booking_id="current".
- If a tool returns an error, relay the message clearly and helpfully.
  Do not expose technical details or stack traces.
- Call save_traveler_name as soon as the user shares their name.
- Use the traveler's name in every reply once it is known.
- Keep responses concise, warm, and professional.
- If asked about something outside travel, politely decline and offer
  travel assistance instead.

Knowledge base grounding rules (destination / visa / baggage questions):
- Answer ONLY from the "Retrieved knowledge base context" section below —
  never fall back on general or remembered knowledge for these topics, even
  if you believe you know the answer. Treat the retrieved text as the single
  source of truth and do not add facts it does not contain.
- If that section says no relevant context was found, tell the user plainly
  that you don't have grounded information on that topic — do not guess or
  invent an answer — and offer to help with what you can do instead
  (bookings, flights, hotels).

This is TravelBot v4 — tools query a live database, sessions persist across
process restarts via PostgreSQL or Redis, and destination/visa/baggage
questions are grounded in a local ChromaDB knowledge base.
""".strip()


# ── Dynamic, retrieval-augmented instruction ───────────────────────────────

def _format_context(chunks: list[dict]) -> str:
    """Render retrieved chunks (or their absence) as an instruction section."""
    if not chunks:
        return (
            "Retrieved knowledge base context: NONE FOUND for this question.\n"
            "Follow the fallback rule above — say plainly that you don't have "
            "grounded information on this topic rather than guessing."
        )
    lines = ["Retrieved knowledge base context (ground your answer in this only):"]
    for chunk in chunks:
        lines.append(f"- [{chunk['category']}] {chunk['text']}")
    return "\n".join(lines)


def _build_instruction(ctx: ReadonlyContext) -> str:
    """
    InstructionProvider: runs once per turn, before the model is called.

    Pulls the latest user message out of the invocation context, retrieves
    the closest knowledge-base chunks for it, and appends them — plus the
    grounding/fallback guidance — to the base instruction so the model
    answers destination/visa/baggage questions from real retrieved text
    rather than its own memory. This is the only structural change from
    v3, where the instruction was a plain string.
    """
    query = ""
    if ctx.user_content and ctx.user_content.parts:
        query = "".join(part.text or "" for part in ctx.user_content.parts if part.text)

    chunks = retrieve(query, n_results=settings.rag_top_k) if query.strip() else []
    return f"{_BASE_INSTRUCTION}\n\n{_format_context(chunks)}"


# ── Agent ──────────────────────────────────────────────────────────────────
aria = build_agent(
    name="aria_v4",
    instruction=_build_instruction,
    description=(
        "TravelBot v4 — booking lookup, cancellation, flight search, "
        "persistent session state backed by PostgreSQL + optional Redis cache, "
        "and a RAG-grounded knowledge base for destination/visa/baggage questions."
    ),
    tools=TOOLS_V3,
)
