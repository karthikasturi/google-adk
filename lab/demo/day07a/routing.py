"""
routing.py — LiteLLM gateway client
====================================
Concept: Day 07 ran a `litellm.Router` in-process, so the routing/fallback
*configuration* lived next to application code in routing.py. Day 07a moves
that configuration out of the process entirely — it now lives in
`litellm_config.yaml`, served by a standalone LiteLLM proxy container (see
docker-compose.yml). This module is a thin client: it asks the gateway for a
named model *group* and reports what the gateway's response headers reveal
about the routing decision it made.

Two model groups mirror the fast/deep split from Day 07:
  fast-faq       → lower-latency model, optimised for FAQ-style answers
  deep-planning  → stronger model for multi-step itinerary planning

Two more exist purely to demonstrate resilience, entirely via gateway config:
  fallback-demo  — primary is a non-existent model (error → fallback)
  timeout-demo   — primary has a near-zero timeout (timeout → fallback)

Design note: unlike Day 07, application code here never constructs a Router
or a fallback list — it only ever references a model *group name* (a string
that must match a `model_name` entry in litellm_config.yaml). Changing retry
counts, swapping the backup provider, or adding a new fallback chain is a
config-file + `docker compose restart litellm` change, not a code change.
"""

import os
import time

import litellm

# ── Gateway connection ──────────────────────────────────────────────────────
PROXY_URL = os.getenv("LITELLM_PROXY_URL", "http://localhost:4000")
PROXY_API_KEY = os.getenv("LITELLM_MASTER_KEY", "sk-day07a-local")

# ── Model group names (must match litellm_config.yaml `model_name` values) ──
FAST_FAQ_GROUP = "fast-faq"
DEEP_PLANNING_GROUP = "deep-planning"
FALLBACK_DEMO_GROUP = "fallback-demo"
TIMEOUT_DEMO_GROUP = "timeout-demo"

# Human-readable labels for the scenario printouts — the *real* model
# strings only exist in litellm_config.yaml now, so these are descriptions,
# not values the app depends on.
FAST_MODEL_LABEL = "openrouter/google/gemini-2.5-flash  (gateway group: fast-faq)"
DEEP_MODEL_LABEL = "openrouter/google/gemini-2.5-pro  (gateway group: deep-planning)"
BACKUP_MODEL_LABEL = "openrouter/openai/gpt-4o-mini  (gateway group: backup)"


# ── Query classifier ────────────────────────────────────────────────────────
# This stays in the application layer deliberately: it decides *which*
# gateway model group to call, which is a request-shaping concern. The
# resilience rules for whatever group it picks (retries, timeouts,
# fallbacks) are the gateway's job now, configured in litellm_config.yaml.

_PLANNING_SIGNALS = {
    "plan", "itinerary", "7-day", "10-day", "3-week", "5-day",
    "day-by-day", "sequence of cities", "compare", "budget trip",
    "days", "week", "cities",
}


def classify_query(prompt: str) -> str:
    """Return 'fast-faq' or 'deep-planning' based on prompt content."""
    lower = prompt.lower()
    if any(sig in lower for sig in _PLANNING_SIGNALS):
        return "deep-planning"
    return "fast-faq"


# ── Gateway call + routing-event extraction ─────────────────────────────────
#
# The proxy makes the retry/fallback decision out of process, so the client
# only ever sees the final HTTP response — never the intermediate failures
# the way Day 07's in-process failure_callback could. That response carries
# LiteLLM's own routing headers though, which is exactly what a real gateway
# integration would read instead of a local callback:
#   x-litellm-model-id            which deployment id actually served this
#   x-litellm-attempted-retries   how many times the *same* deployment retried
#   x-litellm-attempted-fallbacks how many times the proxy fell back to another group
# response.model also changes: LiteLLM restamps it to the actual downstream
# model whenever a fallback occurred (instead of echoing back the requested
# group name), so comparing it to the requested group is a second signal.
#
# litellm's client captures raw upstream response headers and stores them
# under response._hidden_params["additional_headers"], prefixed with
# "llm_provider-" (see litellm.litellm_core_utils.core_helpers.process_response_headers).

_HEADER_PREFIX = "llm_provider-"


def _header(hidden_params: dict, name: str):
    return hidden_params.get("additional_headers", {}).get(f"{_HEADER_PREFIX}{name}")


async def call_gateway(model_group: str, messages: list[dict]) -> dict:
    """
    Call the LiteLLM gateway for `model_group` and return a routing event
    describing what actually happened — same shape as Day 07's routing_log
    entries, but derived entirely from the gateway's own response instead of
    a local Router callback.
    """
    start = time.monotonic()
    try:
        response = await litellm.acompletion(
            model=f"openai/{model_group}",
            api_base=PROXY_URL,
            api_key=PROXY_API_KEY,
            messages=messages,
        )
    except Exception as exc:
        latency_ms = round((time.monotonic() - start) * 1000)
        return {
            "status": "failure",
            "model_group": model_group,
            "error": type(exc).__name__,
            "latency_ms": latency_ms,
            "reply": f"[error after all retries: {exc}]",
        }

    latency_ms = round((time.monotonic() - start) * 1000)
    hidden_params = getattr(response, "_hidden_params", {}) or {}
    attempted_fallbacks = _header(hidden_params, "x-litellm-attempted-fallbacks")
    attempted_retries = _header(hidden_params, "x-litellm-attempted-retries")
    model_id = _header(hidden_params, "x-litellm-model-id")

    return {
        "status": "success",
        "model_group": model_group,
        "model": response.model,
        "model_id": model_id,
        "attempted_retries": int(attempted_retries) if attempted_retries else 0,
        "attempted_fallbacks": int(attempted_fallbacks) if attempted_fallbacks else 0,
        "fell_back": bool(attempted_fallbacks) and int(attempted_fallbacks) > 0,
        "latency_ms": latency_ms,
        "reply": (response.choices[0].message.content or "").strip(),
    }
