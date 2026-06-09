"""
agent.py — Day 06: PDF-grounded RAG with metadata citations
===============================================================
Concept: Retrieval-Augmented Generation over real documents

Two agents share one persona — the only difference is retrieval:

    plain_agent  — answers from the model's own training data only
    root_agent   — runs kb.semantic_search() for every message, grounds
                   its answer in the top-k matching PDF pages, and is
                   told to cite each one by source filename + page number

Putting the same question to both (see demo.py Scenario 2) is the
clearest way to *see* what RAG buys you: grounded, checkable, *citable*
answers instead of fluent guesses. The citation is only possible because
kb.py carries {"source", "page"} metadata all the way from the PDF
through embedding, indexing, and retrieval — see kb.load_pdf_chunks().

ADK Web:
    adk web .          ← discovers root_agent automatically
"""

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.lite_llm import LiteLlm

litellm.suppress_debug_info = True
load_dotenv()

from kb import semantic_search

_MODEL = "openrouter/google/gemini-2.5-flash"
_TOP_K = 3

_PERSONA = """
You are Aria, a concise and friendly travel assistant.
Keep answers short, warm, and to the point.
""".strip()

# ── Plain agent — no retrieval, for comparison only ─────────────────────────
plain_agent = LlmAgent(
    name="aria_plain",
    model=LiteLlm(model=_MODEL),
    instruction=_PERSONA,
    description="Aria without retrieval — answers from model knowledge alone.",
)


# ── RAG-grounded agent ───────────────────────────────────────────────────────
_GROUNDING_RULES = """
Grounding rules:
- Answer ONLY using the "Retrieved context" section below — never fall back
  on general or remembered knowledge for it, even if you believe you know
  the answer. Treat the retrieved text as the single source of truth.
- Every retrieved chunk is tagged with its source document and page number.
  When you use a chunk, cite it inline like "(tokyo-destination-guide.pdf,
  p.1)" so the user can verify the claim against the original PDF.
- If that section says nothing relevant was found, say so plainly — for
  example "I don't have grounded information on that" — instead of
  guessing or inventing an answer.
""".strip()


def _format_context(results: list[dict]) -> str:
    """Render retrieved chunks — with their source/page metadata — as an instruction section."""
    if not results:
        return (
            "Retrieved context: NOTHING RELEVANT FOUND.\n"
            "Follow the fallback rule above — say plainly that you don't have "
            "grounded information on this topic."
        )
    lines = ["Retrieved context (ground your answer in this only, cite the source for each):"]
    for r in results:
        meta = r["metadata"]
        citation = f"{meta.get('source', 'unknown')}, p.{meta.get('page', '?')}"
        lines.append(f"- (similarity={r['score']:.2f}, source={citation}) {r['text']}")
    return "\n".join(lines)


def _build_instruction(ctx: ReadonlyContext) -> str:
    """
    InstructionProvider: runs once per turn, before the model is called.

    Pulls the latest user message out of the invocation context, retrieves
    the closest PDF-page chunks for it — each carrying {"source", "page"}
    metadata — and appends them, plus the grounding/citation rules, to the
    persona. The model only ever sees what was retrieved *for this turn*,
    never the raw documents.
    """
    query = ""
    if ctx.user_content and ctx.user_content.parts:
        query = "".join(part.text or "" for part in ctx.user_content.parts if part.text)

    results = semantic_search(query, top_k=_TOP_K) if query.strip() else []
    return f"{_PERSONA}\n\n{_GROUNDING_RULES}\n\n{_format_context(results)}"


root_agent = LlmAgent(
    name="aria_rag",
    model=LiteLlm(model=_MODEL),
    instruction=_build_instruction,
    description=(
        "Aria with PDF-grounded RAG — retrieves the top-k matching pages from "
        "a PDF knowledge base for every message, grounds her answer in them, "
        "and cites the source document and page number."
    ),
)
