"""
routing.py — LiteLLM routing and fallback configuration
========================================================
Concept: Route TravelBot queries by complexity and protect against
provider failures using litellm.Router.

Two model groups mirror what a LiteLLM proxy config would define:
  fast-faq       → lower-latency model, optimised for FAQ-style answers
  deep-planning  → stronger model for multi-step itinerary planning

Three additional routers expose fallback behaviour for the demo:
  fallback_demo_router  — primary is a non-existent model (error → fallback)
  timeout_demo_router   — primary has a near-zero timeout (timeout → fallback)

Design note: in production these groups live in litellm_config.yaml and
agent code never changes — only the gateway config does. Here we replicate
the same behaviour locally so the demo runs without a proxy server.
"""

import os

import litellm
from litellm import Router

# ── Model identifiers (single source of truth) ─────────────────────────────
FAST_MODEL   = "openrouter/google/gemini-2.5-flash"  # fast, cost-effective
DEEP_MODEL   = "openrouter/google/gemini-2.5-pro"    # stronger reasoning, higher cost
BACKUP_MODEL = "openrouter/openai/gpt-4o-mini"       # cross-provider fallback

# ── Routing event capture ──────────────────────────────────────────────────
# demo.py clears this list before each scenario/prompt and reads it
# afterwards to print the gateway routing decisions (model chosen, latency,
# errors).
#
# Only FAILURE events are captured here via a litellm callback — litellm
# awaits the failure callback inline, synchronously, before the exception
# propagates, so it's a reliable source of truth for "primary attempt
# failed" (info the caller can't otherwise see, since Router swallows it
# internally before falling back). SUCCESS events are appended directly by
# the caller in demo.py instead: litellm defers success-callback execution
# to a background task with no guarantee it completes before acompletion()
# returns, which in practice showed up as SUCCESS entries missing or
# attributed to the wrong prompt.
routing_log: list[dict] = []


async def _on_failure(kwargs, completion_response, start_time, end_time) -> None:
    model = (
        kwargs.get("litellm_params", {}).get("model")
        or kwargs.get("model", "unknown")
    )
    exc = kwargs.get("exception")
    routing_log.append({
        "status": "failure",
        "model": model,
        "error": type(exc).__name__ if exc else "unknown",
    })


def enable_routing_callbacks() -> None:
    """Attach the failure routing callback to litellm. Call once at startup."""
    if not isinstance(getattr(litellm, "failure_callback", None), list):
        litellm.failure_callback = []
    if _on_failure not in litellm.failure_callback:
        litellm.failure_callback.append(_on_failure)


# ── Router factory ─────────────────────────────────────────────────────────

def _params(model: str, timeout: float = 30.0) -> dict:
    return {
        "model": model,
        "api_key": os.getenv("OPENROUTER_API_KEY"),
        "api_base": "https://openrouter.ai/api/v1",
        "timeout": timeout,
    }


def _make_router(
    primary: str,
    backup: str,
    *,
    primary_timeout: float = 30.0,
    num_retries: int = 0,
) -> Router:
    return Router(
        model_list=[
            {"model_name": "primary", "litellm_params": _params(primary, primary_timeout)},
            {"model_name": "backup",  "litellm_params": _params(backup)},
        ],
        fallbacks=[{"primary": ["backup"]}],
        num_retries=num_retries,
        retry_after=1,
        allowed_fails=1,
        cooldown_time=5,
    )


# ── Named routers for each demo scenario ──────────────────────────────────

# Scenarios 1A/1B: normal routing — ADK agents use their model strings directly.
# These routers are kept here for reference and for the REPL fallback path.
faq_router      = _make_router(FAST_MODEL,  BACKUP_MODEL)
planning_router = _make_router(DEEP_MODEL,  BACKUP_MODEL)

# Scenario 2A: primary model name does not exist → provider error → fallback
fallback_demo_router = _make_router(
    primary="openrouter/google/bad-model-xyz",
    backup=BACKUP_MODEL,
    num_retries=1,
)

# Scenario 2B: near-zero timeout on primary → Timeout exception → fallback
timeout_demo_router = _make_router(
    primary=DEEP_MODEL,
    backup=BACKUP_MODEL,
    primary_timeout=0.001,  # guaranteed timeout — shows fallback reliably
    num_retries=0,
)


# ── Query classifier ───────────────────────────────────────────────────────

_PLANNING_SIGNALS = {
    "plan", "itinerary", "7-day", "10-day", "3-week", "5-day",
    "day-by-day", "sequence of cities", "compare", "budget trip",
    "days", "week", "cities",
}


def classify_query(prompt: str) -> str:
    """
    Return 'fast-faq' or 'deep-planning' based on prompt content.
    In production this classification runs at the gateway as a pre-call
    hook; here it runs in the application layer so the demo is self-contained.
    """
    lower = prompt.lower()
    if any(sig in lower for sig in _PLANNING_SIGNALS):
        return "deep-planning"
    return "fast-faq"
