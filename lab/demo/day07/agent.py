"""
agent.py — Day 07 TravelBot: LiteLLM routing and fallback
==========================================================
Concept: Route queries to the right model group without changing agent code.

Two ADK agents share the same Aria persona:
  faq_agent      — backed by the fast-faq model group (FAQ, policy questions)
  planning_agent — backed by the deep-planning model group (complex itineraries)

The routing decision (which agent to call) lives entirely in demo.py via
routing.classify_query() — the agents themselves are unaware of it.
root_agent defaults to planning_agent for  adk web .
"""

import logging
import os

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

# ── Silence noisy loggers (same pattern as previous days) ─────────────────
logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False

litellm.suppress_debug_info = True
load_dotenv()

from routing import DEEP_MODEL, FAST_MODEL

_PERSONA = """
You are Aria, TravelBot's friendly and knowledgeable travel assistant.
Keep answers concise and warm. For policy questions, be direct and factual.
For itinerary requests, organise your answer with clear sections or bullet points.
""".strip()

# fast-faq route — cheaper, lower-latency model for FAQ queries
faq_agent = LlmAgent(
    name="aria_faq",
    model=LiteLlm(model=FAST_MODEL),
    instruction=_PERSONA,
    description="Aria on the fast-faq route — policy questions and quick answers.",
)

# deep-planning route — stronger model for complex itinerary planning
planning_agent = LlmAgent(
    name="aria_planning",
    model=LiteLlm(model=DEEP_MODEL),
    instruction=_PERSONA,
    description="Aria on the deep-planning route — multi-day itineraries and complex plans.",
)

# Default for  adk web .
root_agent = planning_agent
