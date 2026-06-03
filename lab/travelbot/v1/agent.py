"""
agent.py — TravelBot v1: Basic Travel Assistant
=================================================
Concept: Module 1 — What is an agent?

A single LlmAgent with a well-crafted system prompt.
No tools, no session persistence — just a capable persona.

Run via the TravelBot REPL (coming in a later module) or import directly:
    from v1.agent import aria

Try these prompts:
    "I need help planning a trip to Singapore."
    "What documents do I need to travel to Japan?"
    "Can you write me a Python script?"  ← out-of-scope, should be declined
"""

import sys
from pathlib import Path

import litellm
from dotenv import load_dotenv

litellm.suppress_debug_info = True
load_dotenv()

# Make shared/ importable regardless of cwd
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.models import build_agent

# ── Instruction ────────────────────────────────────────────────────────────
_INSTRUCTION = """
You are Aria, a friendly and knowledgeable AI travel assistant for TravelBot.

Your role is to help travelers plan trips, understand destination requirements,
and make informed decisions about flights, hotels, and itineraries.

Guidelines:
- Be warm, conversational, and encouraging.
- Provide helpful general guidance based on well-known travel knowledge.
- You do not have access to live data — do not invent prices, schedules,
  or real-time availability.
- If asked something outside travel, politely decline and offer travel help.

This is TravelBot v1 — a foundational agent with no external tools yet.
Tool calling and session memory are added in v2.
""".strip()

# ── Agent ──────────────────────────────────────────────────────────────────
aria = build_agent(
    name="aria_v1",
    instruction=_INSTRUCTION,
    description="TravelBot v1 — basic travel assistant (no tools)",
)
