"""
agent.py — Multi-Turn Session Memory Demo
==========================================
Example: examples/session_memory/

Concept:
  ADK's InMemorySessionService keeps the full conversation history for the
  duration of a session.  The agent receives all prior turns in its context
  window, so follow-up questions can reference earlier information.

  This example shows that multi-turn memory is not a special feature —
  it is the default behaviour of the session service combined with an
  instruction that tells the agent to use prior context deliberately.

ADK Web:
  Run from lab/demo/day02/:
      adk web examples/session_memory

  Send Turn 1 with destination, dates, and group size.
  Send Turn 2 with a follow-up that only makes sense given Turn 1.
  Observe that the agent references the earlier context in its reply.

  Check the "Session" panel in ADK Web to see the full turn-by-turn history.
"""

from pathlib import Path

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

litellm.suppress_debug_info = True
load_dotenv()

# ── Instruction ────────────────────────────────────────────────────────────
_INSTRUCTION = (Path(__file__).parent / "instruction.txt").read_text().strip()

# ── Model ──────────────────────────────────────────────────────────────────
_MODEL = "openrouter/google/gemini-2.5-flash"

# ── Agent ──────────────────────────────────────────────────────────────────
# InMemorySessionService is used by ADK Web automatically — no extra setup
# needed here.  The session history is maintained for the life of the server.
root_agent = LlmAgent(
    name="session_memory_agent",
    model=LiteLlm(model=_MODEL),
    instruction=_INSTRUCTION,
    description="A travel assistant that uses session context across turns",
)
