"""
demo.py — Day 06: PDF-Grounded RAG with a Configurable Vector Backend
========================================================================
Google ADK · LiteLLM · OpenRouter · OpenAI embeddings · ChromaDB / AWS OpenSearch

Runs four scripted scenarios that build on Day 05's RAG story with two
production-shaped upgrades — real PDF documents (with page-level metadata)
and a swappable vector backend (in-memory ChromaDB or AWS OpenSearch) — and
then drops into a free REPL with the RAG agent. Type  q  to quit.

Run:
    cp .env.example .env          # fill in OPENROUTER_API_KEY
    python demo.py                # run all scenarios (VECTOR_BACKEND=memory)
    python demo.py --repl         # skip scenarios, go straight to REPL

Try AWS OpenSearch instead — managed domain or Serverless collection,
see README.md for how to provision either (needs AWS creds):
    VECTOR_BACKEND=opensearch             OPENSEARCH_HOST=... AWS_REGION=... python demo.py
    VECTOR_BACKEND=opensearch-serverless  OPENSEARCH_HOST=... AWS_REGION=... python demo.py
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

log = logging.getLogger("day06")
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

from agent import plain_agent, root_agent
from kb import DOCS_DIR, load_pdf_chunks, semantic_search
from session import make_runner

# ── Scenario guide ─────────────────────────────────────────────────────────
_GUIDE = """
  SCENARIO GUIDE — Day 06: PDF RAG & Configurable Vector Backends
  ──────────────────────────────────────────────────────────────────────
  1  PDF ingestion + search   Load PDFs, embed pages, search with metadata
  2  Grounded vs ungrounded   Same question to plain_agent vs RAG root_agent
  3  Citations                Answers point back to (source.pdf, page N)
  4  Honest fallback          A question the documents can't answer
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
    for rank, r in enumerate(semantic_search(query, top_k=3), start=1):
        meta = r["metadata"]
        snippet = textwrap.shorten(r["text"], width=78, placeholder="…")
        print(
            f"    {rank}. score={r['score']:.3f}  "
            f"[{meta.get('source')} p.{meta.get('page')}]  {snippet}"
        )


async def scenario_1_pdf_ingestion_and_search() -> None:
    _sep()
    print("  Scenario 1 — PDF ingestion + semantic search (with metadata)")
    _sep()
    backend = os.getenv("VECTOR_BACKEND", "memory").strip().lower()
    chunks = load_pdf_chunks()
    print(f"\n  Vector backend : {backend}  (memory | opensearch | opensearch-serverless — see README.md)")
    print(f"  PDFs in {DOCS_DIR.name}/:")
    for path in sorted(DOCS_DIR.glob("*.pdf")):
        pages = sum(1 for c in chunks if c["metadata"]["source"] == path.name)
        print(f"    - {path.name}  ({pages} page(s) indexed)")
    print(
        "\n  Each PDF page was extracted with pypdf, embedded once, and upserted\n"
        "  into the backend together with {\"source\": filename, \"page\": N}\n"
        "  metadata (kb.load_pdf_chunks). Queries are embedded the same way and\n"
        "  matched by vector distance — the metadata travels with every result,\n"
        "  so we always know exactly which document and page a match came from."
    )
    _show_search("How do I get around the city using the trains?")
    _show_search("What paperwork do I need before an international trip?")
    print()


async def scenario_2_grounded_vs_ungrounded(
    plain_runner, plain_user, plain_session,
    rag_runner, rag_user, rag_session,
) -> None:
    _sep()
    print("  Scenario 2 — Grounded vs ungrounded (same question, two agents)")
    _sep()
    prompt = "How many checked bags do I get in business class, and what's the weight limit?"
    print(f"\n  You: {prompt}\n")

    plain_reply = await _ask(plain_runner, plain_user, plain_session, prompt)
    print("  [aria_plain — no retrieval, answers from model memory]")
    print(_wrap(plain_reply))

    rag_reply = await _ask(rag_runner, rag_user, rag_session, prompt)
    print("\n  [aria_rag — retrieves matching PDF pages, answers grounded in them]")
    print(_wrap(rag_reply))
    print(
        "\n  Notice: this baggage policy is fictional — it only exists in\n"
        "  docs/baggage-allowance-policy.pdf. The plain agent has to guess or\n"
        "  hedge; the RAG agent answers correctly because it actually retrieved\n"
        "  the page — and, as Scenario 3 shows, can point you straight to it.\n"
    )


async def scenario_3_citations(runner, user_id: str, session_id: str) -> None:
    _sep()
    print("  Scenario 3 — Citations (answers point back to source + page)")
    _sep()
    prompt = "Which neighborhood in Tokyo would you recommend for a first-time visitor, and why?"
    reply = await _ask(runner, user_id, session_id, prompt)
    print(f"\n  You: {prompt}\n")
    print("  [aria_rag]")
    print(_wrap(reply))
    print(
        "\n  Notice: the reply names the PDF and page it came from, e.g.\n"
        "  \"(tokyo-destination-guide.pdf, p.2)\". That's only possible because\n"
        "  the {\"source\", \"page\"} metadata survived the whole round trip —\n"
        "  PDF → chunk → embedding → vector backend → retrieval → instruction —\n"
        "  and agent.py's grounding rules tell the model to surface it.\n"
    )


async def scenario_4_honest_fallback(runner, user_id: str, session_id: str) -> None:
    _sep()
    print("  Scenario 4 — Honest fallback (a question the documents can't answer)")
    _sep()
    prompt = "What's the best street food to try near Senso-ji temple?"
    reply = await _ask(runner, user_id, session_id, prompt)
    print(f"\n  You: {prompt}\n")
    print("  [aria_rag]")
    print(_wrap(reply))
    print(
        "\n  Notice: none of the three PDFs cover food recommendations, so\n"
        "  retrieval comes back empty (or with low-relevance matches). The\n"
        "  grounding rules in agent.py tell the model to admit that plainly\n"
        "  rather than invent something that sounds plausible.\n"
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
|   DAY 06 — PDF-Grounded RAG & Configurable Vector Backends          |
|   Google ADK · LiteLLM · OpenRouter · ChromaDB / AWS OpenSearch      |
+======================================================================+""")
    print(_GUIDE)

    if os.getenv("VECTOR_BACKEND", "memory").strip().lower() == "opensearch-serverless":
        print(
            "  NOTE: VECTOR_BACKEND=opensearch-serverless — the first PDF search\n"
            "  below will trigger a one-time index rebuild against your live\n"
            "  collection. AWS Serverless's indexing-to-search visibility lag can\n"
            "  run into MINUTES (not a hang!) — see README.md's \"No explicit\n"
            "  refresh\" section for measured numbers.\n"
        )

    repl_only = "--repl" in sys.argv

    rag_runner, rag_user, rag_session = await make_runner(root_agent)
    print(f"  user_id:    {rag_user}")
    print(f"  session_id: {rag_session}\n")

    if not repl_only:
        try:
            await scenario_1_pdf_ingestion_and_search()

            plain_runner, plain_user, plain_session = await make_runner(plain_agent)
            await scenario_2_grounded_vs_ungrounded(
                plain_runner, plain_user, plain_session,
                rag_runner, rag_user, rag_session,
            )

            await scenario_3_citations(rag_runner, rag_user, rag_session)
            await scenario_4_honest_fallback(rag_runner, rag_user, rag_session)
        except KeyboardInterrupt:
            print("\n  Scenarios interrupted.\n")

        cont = input("  Continue to free REPL? [y/N]: ").strip().lower()
        if cont != "y":
            return

    await run_repl(rag_runner, rag_user, rag_session)


if __name__ == "__main__":
    asyncio.run(main())
