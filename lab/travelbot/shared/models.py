"""
shared/models.py — Model configuration for TravelBot
------------------------------------------------------
Central place to change the model or add routing logic as the project grows.

v2: single model via LiteLlm + OpenRouter
v4: add LiteLLM routing (fast model for simple, large for complex)
v6: add cost tracking + fallback providers
"""

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

# ── Default model ──────────────────────────────────────────────────────────
# Phase 1–3: one model for everything.
# Phase 4: swap to a LiteLlm router config here.
MODEL = "openrouter/google/gemini-2.5-flash"


def get_llm():
    """Return the configured LLM instance."""
    return LiteLlm(model=MODEL)


def build_agent(name: str, instruction: str, description: str, tools=None) -> LlmAgent:
    """
    Build an LlmAgent with the shared model configuration.

    Args:
        name:        Agent identifier (appears in ADK Web traces).
        instruction: System prompt / instruction for the agent.
        description: Short description shown in ADK Web.
        tools:       List of callable tool functions (optional).
    """
    return LlmAgent(
        name=name,
        model=get_llm(),
        instruction=instruction,
        description=description,
        tools=tools or [],
    )
