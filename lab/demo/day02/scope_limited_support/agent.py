"""
agent.py — Scope-Limited Support Agent
========================================
Example: examples/scope_limited_support/

Concept:
  The instruction restricts the agent to a defined topic area.
  Requests outside that scope trigger a polite refusal.

  This demonstrates that scope enforcement is a prompt design choice —
  no code changes are needed, only instruction changes.

ADK Web:
  Run from lab/demo/day02/:
      adk web examples/scope_limited_support

  Test with an in-scope question, then try an out-of-scope question
  (e.g., "What is the weather in Paris?") and observe the refusal.
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
root_agent = LlmAgent(
    name="scope_limited_support_agent",
    model=LiteLlm(model=_MODEL),
    instruction=_INSTRUCTION,
    description="An airline support agent scoped to booking and baggage only",
)
