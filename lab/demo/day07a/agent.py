"""
agent.py — Day 07a TravelBot: routing via a standalone LiteLLM gateway
========================================================================
Concept: Route queries to the right model group without changing agent code
— and without the routing rules living in this process at all.

Two ADK agents share the same Aria persona:
  faq_agent      — backed by the fast-faq model group (FAQ, policy questions)
  planning_agent — backed by the deep-planning model group (complex itineraries)

Both agents point their LiteLlm model at the LiteLLM proxy container
(see docker-compose.yml + litellm_config.yaml) instead of an OpenRouter model
string directly. The proxy resolves "fast-faq"/"deep-planning" to whichever
real model + fallback chain the config says — this process only ever sees
the group name.

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

from routing import DEEP_PLANNING_GROUP, FAST_FAQ_GROUP, PROXY_API_KEY, PROXY_URL

_PERSONA = """
You are Aria, TravelBot's friendly and knowledgeable travel assistant.
Keep answers concise and warm. For policy questions, be direct and factual.
For itinerary requests, organise your answer with clear sections or bullet points.
""".strip()


def _gateway_model(group: str) -> LiteLlm:
    """
    An ADK LiteLlm model pointed at the LiteLLM gateway container instead of
    a provider directly. `model` here is the gateway's model_name (a group,
    not an actual provider model) — the "openai/" prefix just tells litellm
    to treat api_base as an OpenAI-compatible endpoint, which the LiteLLM
    proxy is.
    """
    return LiteLlm(model=f"openai/{group}", api_base=PROXY_URL, api_key=PROXY_API_KEY)


# fast-faq route — cheaper, lower-latency model for FAQ queries
faq_agent = LlmAgent(
    name="aria_faq",
    model=_gateway_model(FAST_FAQ_GROUP),
    instruction=_PERSONA,
    description="Aria on the fast-faq route — policy questions and quick answers.",
)

# deep-planning route — stronger model for complex itinerary planning
planning_agent = LlmAgent(
    name="aria_planning",
    model=_gateway_model(DEEP_PLANNING_GROUP),
    instruction=_PERSONA,
    description="Aria on the deep-planning route — multi-day itineraries and complex plans.",
)

# Default for  adk web .
root_agent = planning_agent
