"""
agent.py — Unknown-Data / Honest Fallback Demo
================================================
Example: examples/unknown_data/

Concept:
  Without explicit guardrails in the instruction, a model may hallucinate
  specific prices, schedules, or availability data.

  This instruction forces the agent to acknowledge when it lacks live data
  instead of fabricating a plausible-sounding answer.

ADK Web:
  Run from lab/demo/day02/:
      adk web examples/unknown_data

  Ask for a live price or today's flight schedule and observe the refusal.
  Then compare this with a model that has no such guardrail — the difference
  is stark and is purely driven by the instruction.
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
    name="unknown_data_agent",
    model=LiteLlm(model=_MODEL),
    instruction=_INSTRUCTION,
    description="A travel assistant that refuses to fabricate live data",
)
