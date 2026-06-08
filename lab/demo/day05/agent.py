"""
agent.py — Day 05: Semantic Search & RAG agents
==================================================
Concept: Retrieval-Augmented Generation

Two agents share one persona — the only difference is retrieval:

    plain_agent  — answers from the model's own training data only
    root_agent   — runs kb.semantic_search() for every message and
                   grounds its answer in the top-k matching chunks

Putting the same question to both (see demo.py Scenario 2) is the clearest
way to *see* what RAG buys you: grounded, checkable answers instead of
fluent guesses.

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
- If that section says nothing relevant was found, say so plainly — for
  example "I don't have grounded information on that" — instead of
  guessing or inventing an answer.
""".strip()


def _format_context(results: list[dict]) -> str:
    """Render retrieved chunks (or their absence) as an instruction section."""
    if not results:
        return (
            "Retrieved context: NOTHING RELEVANT FOUND.\n"
            "Follow the fallback rule above — say plainly that you don't have "
            "grounded information on this topic."
        )
    lines = ["Retrieved context (ground your answer in this only):"]
    for r in results:
        lines.append(f"- (similarity={r['score']:.2f}) {r['text']}")
    return "\n".join(lines)


def _build_instruction(ctx: ReadonlyContext) -> str:
    """
    InstructionProvider: runs once per turn, before the model is called.

    Pulls the latest user message out of the invocation context, retrieves
    the closest knowledge-base chunks for it, and appends them — plus the
    grounding rules — to the persona, so the model answers from real
    retrieved text rather than its own memory.
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
        "Aria with RAG — retrieves the top-k matching knowledge-base chunks "
        "for every message and grounds her answer in them."
    ),
)
