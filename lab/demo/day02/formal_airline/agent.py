"""
agent.py — Formal Airline Advisor
===================================
Example: examples/formal_airline/

Concept:
  The same model answers the same travel question — but with a completely
  different tone because the instruction is different.

  Compare this side-by-side with examples/friendly_travel/ to see how the
  instruction (not the model) controls reply style.

ADK Web:
  Run from lab/demo/day02/:
      adk web examples/formal_airline

  Send the same message you used in friendly_travel and compare the replies.
"""

from pathlib import Path

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

litellm.suppress_debug_info = True
load_dotenv()

# ── Instruction ────────────────────────────────────────────────────────────
# Same file-loading pattern as friendly_travel — only the text inside differs.
_INSTRUCTION = (Path(__file__).parent / "instruction.txt").read_text().strip()

# ── Model ──────────────────────────────────────────────────────────────────
_MODEL = "openrouter/google/gemini-2.5-flash"

# ── Agent ──────────────────────────────────────────────────────────────────
# Note the name differs from friendly_travel_agent — each agent has its own identity.
root_agent = LlmAgent(
    name="formal_airline_agent",
    model=LiteLlm(model=_MODEL),
    instruction=_INSTRUCTION,
    description="A formal, professional airline travel advisor",
)
