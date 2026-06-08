"""
demo.py — Day 05: Semantic Search & Retrieval-Augmented Generation
====================================================================
Google ADK · LiteLLM · OpenRouter · OpenAI embeddings (via OpenRouter)

Runs three scripted scenarios that build up the RAG story step by step —
embedding + ChromaDB vector search, then grounded vs. ungrounded answers,
then honest fallback — and then drops into a free REPL with the RAG agent.
Type  q  to quit.

Run:
    cp .env.example .env          # fill in OPENROUTER_API_KEY
    python demo.py                # run all scenarios
    python demo.py --repl         # skip scenarios, go straight to REPL
"""

import asyncio
import logging
import os
import sys
import textwrap

from dotenv import load_dotenv
from google.genai import types

load_dotenv()

# ── Silence LiteLLM noise (same as previous days) ──────────────────────────
logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False

log = logging.getLogger("day05")
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

from agent import plain_agent, root_agent
from kb import semantic_search
from session import make_runner

# ── Scenario guide ─────────────────────────────────────────────────────────
_GUIDE = """
  SCENARIO GUIDE — Day 05: Semantic Search & RAG
  ──────────────────────────────────────────────────────────────────────
  1  Semantic search       Raw top-k vector search over an embedded ChromaDB collection
  2  Grounded vs ungrounded  Same question to plain_agent vs RAG root_agent
  3  Honest fallback       A question the knowledge base can't answer
  ──────────────────────────────────────────────────────────────────────
"""

# ── Console helpers ────────────────────────────────────────────────────────

def _wrap(text: str, width: int = 74) -> str:
    prefix = "    "
    return textwrap.fill(text, width=width, initial_indent=prefix, subsequent_indent=prefix)


def _sep(char: str = "─", width: int = 70) -> None:
    print(f"  {char * width}")


def _build_message(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


# ── ADK ask helper ─────────────────────────────────────────────────────────

async def _ask(runner, user_id: str, session_id: str, prompt: str) -> str:
    reply = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=_build_message(prompt),
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                reply = event.content.parts[0].text or ""
    return reply.strip()


# ── Scripted scenarios ─────────────────────────────────────────────────────

def _show_search(query: str) -> None:
    print(f"\n  Query: \"{query}\"")
    results = semantic_search(query, top_k=3)
    for rank, r in enumerate(results, start=1):
        snippet = textwrap.shorten(r["text"], width=88, placeholder="…")
        print(f"    {rank}. score={r['score']:.3f}  [{r['id']}]  {snippet}")


async def scenario_1_semantic_search() -> None:
    _sep()
    print("  Scenario 1 — Semantic search in action (embedding + ChromaDB vector search)")
    _sep()
    print(
        "\n  Every document was embedded once and indexed into an in-memory\n"
        "  ChromaDB collection at startup (kb._get_collection). For each query\n"
        "  below we embed the query the same way and let ChromaDB return the\n"
        "  nearest documents by vector distance — no keyword matching, just\n"
        "  vector closeness."
    )
    _show_search("How do I avoid getting sick from the long flight?")
    _show_search("What do I get for booking lots of weekend trips?")
    print()


async def scenario_2_grounded_vs_ungrounded(
    plain_runner, plain_user, plain_session,
    rag_runner, rag_user, rag_session,
) -> None:
    _sep()
    print("  Scenario 2 — Grounded vs ungrounded (same question, two agents)")
    _sep()
    prompt = "What's TravelBot's cancellation policy, and how do Elite members benefit?"
    print(f"\n  You: {prompt}\n")

    plain_reply = await _ask(plain_runner, plain_user, plain_session, prompt)
    print("  [aria_plain — no retrieval, answers from model memory]")
    print(_wrap(plain_reply))

    rag_reply = await _ask(rag_runner, rag_user, rag_session, prompt)
    print("\n  [aria_rag — retrieves matching KB chunks, answers grounded in them]")
    print(_wrap(rag_reply))
    print(
        "\n  Notice: TravelBot's cancellation and loyalty policies are fictional —\n"
        "  they only exist in kb.py. The plain agent has to guess or hedge; the\n"
        "  RAG agent answers correctly because it actually retrieved the text.\n"
    )


async def scenario_3_honest_fallback(runner, user_id: str, session_id: str) -> None:
    _sep()
    print("  Scenario 3 — Honest fallback (a question the knowledge base can't answer)")
    _sep()
    prompt = "What's TravelBot's policy on bringing musical instruments as carry-on?"
    reply = await _ask(runner, user_id, session_id, prompt)
    print(f"\n  You: {prompt}\n")
    print("  [aria_rag]")
    print(_wrap(reply))
    print(
        "\n  Notice: nothing in kb.py covers this, so retrieval comes back empty.\n"
        "  The grounding rules in agent.py tell the model to admit that plainly\n"
        "  rather than invent a policy that sounds plausible.\n"
    )


# ── Free REPL ──────────────────────────────────────────────────────────────

async def run_repl(runner, user_id: str, session_id: str) -> None:
    """Drop into a free-form conversation REPL with the RAG agent."""
    _sep("═")
    print("  Free REPL — talking to aria_rag. Type any prompt or  q  to quit.")
    _sep("═")

    while True:
        try:
            prompt = input("  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if prompt.lower() == "q":
            break
        if not prompt:
            continue

        reply = await _ask(runner, user_id, session_id, prompt)
        print(f"\n  [aria_rag]\n{_wrap(reply)}\n")

    print("  ── session ended ──\n")


# ── Main ───────────────────────────────────────────────────────────────────

async def main() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "\n[ERROR] OPENROUTER_API_KEY is not set.\n"
            "  Copy .env.example → .env and fill in your key.\n"
        )
        return

    print("""
+======================================================================+
|   DAY 05 — Semantic Search & Retrieval-Augmented Generation         |
|   Google ADK · LiteLLM · OpenRouter · OpenAI embeddings             |
+======================================================================+""")
    print(_GUIDE)

    repl_only = "--repl" in sys.argv

    rag_runner, rag_user, rag_session = await make_runner(root_agent)
    print(f"  user_id:    {rag_user}")
    print(f"  session_id: {rag_session}\n")

    if not repl_only:
        try:
            await scenario_1_semantic_search()

            plain_runner, plain_user, plain_session = await make_runner(plain_agent)
            await scenario_2_grounded_vs_ungrounded(
                plain_runner, plain_user, plain_session,
                rag_runner, rag_user, rag_session,
            )

            await scenario_3_honest_fallback(rag_runner, rag_user, rag_session)
        except KeyboardInterrupt:
            print("\n  Scenarios interrupted.\n")

        cont = input("  Continue to free REPL? [y/N]: ").strip().lower()
        if cont != "y":
            return

    await run_repl(rag_runner, rag_user, rag_session)


if __name__ == "__main__":
    asyncio.run(main())
