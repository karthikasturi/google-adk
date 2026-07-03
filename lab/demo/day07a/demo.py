"""
demo.py — Day 07a: Routing and Fallback via a standalone LiteLLM gateway
==========================================================================
Google ADK · LiteLLM Proxy (Docker) · OpenRouter

Day 07 ran a `litellm.Router` inside this process, so routing/fallback
*config* lived in routing.py next to the agent code. Day 07a moves that
config to a separate LiteLLM proxy container (docker-compose.yml +
litellm_config.yaml) — this process only ever asks the gateway for a named
model group ("fast-faq", "deep-planning", ...) over HTTP. Retries, timeouts,
and fallback chains are gateway config now; changing them is a YAML edit +
`docker compose restart litellm`, not a Python change.

Both fast-faq and deep-planning are pools of multiple deployments — one
low-latency model per provider for fast-faq (Gemini Flash/Flash-Lite,
Claude Haiku, GPT-4o-mini/4.1-mini), one flagship reasoning model per
provider for deep-planning (Gemini Pro, Claude Sonnet, GPT-5). The gateway
load-balances across a pool's deployments (router_settings.routing_strategy)
and, as a side effect, gets automatic cross-provider failover within the
pool for free — if one deployment errors, num_retries lets it retry a
*different* deployment in the same group before ever reaching the explicit
fallback groups below.

One consequence worth watching for in the scenario output: this process no
longer sees the *intermediate* failure when a primary model errors out —
the proxy retries/falls back internally and only the final HTTP response
comes back. What you get instead is richer headers on that one response
(x-litellm-attempted-fallbacks, x-litellm-attempted-retries, x-litellm-model-id)
revealing what the gateway actually did. There's also no shared mutable
routing_log and no callback-timing race to reason about — the gateway
response *is* the event, by construction.

Runs five scripted scenarios:
  1A  FAQ routing       — simple questions routed to the fast-faq model group
  1B  Plan routing      — complex itineraries routed to the deep-planning group
  2A  Error fallback    — primary model fails, gateway retries with backup
  2B  Timeout fallback  — primary times out, gateway switches to backup
  3A  Burst fallback    — concurrent requests, all hitting fallback, staying responsive

Then drops into a routing-aware REPL. Type  q  to quit.

Run:
    cp .env.example .env       # fill in OPENROUTER_API_KEY
    docker compose up -d       # start the litellm gateway container
    docker compose ps          # wait for "healthy"
    python demo.py             # all scenarios then REPL
    python demo.py --repl      # skip scenarios, go straight to REPL
"""

import asyncio
import logging
import os
import sys
import textwrap
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv
from google.genai import types

load_dotenv()

# ── Silence LiteLLM noise (same as previous days) ──────────────────────────
logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False

log = logging.getLogger("day07a")
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

from agent import faq_agent, planning_agent
from routing import (
    BACKUP_MODEL_LABEL,
    DEEP_MODEL_LABEL,
    DEEP_PLANNING_GROUP,
    FALLBACK_DEMO_GROUP,
    FAST_FAQ_GROUP,
    FAST_MODEL_LABEL,
    PROXY_URL,
    TIMEOUT_DEMO_GROUP,
    call_gateway,
    classify_query,
)
from session import make_runner

# ── Scenario guide ─────────────────────────────────────────────────────────
_GUIDE = """
  SCENARIO GUIDE — Day 07a: Routing and Fallback via a LiteLLM gateway
  ──────────────────────────────────────────────────────────────────────
  1A  FAQ routing       Simple questions → fast-faq model group
  1B  Plan routing      Complex itineraries → deep-planning model group
  2A  Error fallback    Primary model fails → gateway retries with backup
  2B  Timeout fallback  Primary times out  → gateway switches to backup
  3A  Burst fallback    Concurrent requests, all hitting fallback, staying responsive
  ──────────────────────────────────────────────────────────────────────
"""

_SYSTEM_PROMPT = "You are Aria, TravelBot's friendly travel assistant. Keep answers concise."

# ── Console helpers ────────────────────────────────────────────────────────


def _wrap(text: str, width: int = 74) -> str:
    prefix = "    "
    return textwrap.fill(text, width=width, initial_indent=prefix, subsequent_indent=prefix)


def _sep(char: str = "─", width: int = 70) -> None:
    print(f"  {char * width}")


def _build_message(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


def _print_routing_events(events: list[dict]) -> None:
    """Print gateway routing events for the current prompt."""
    for ev in events:
        if ev["status"] == "failure":
            print(
                f"  [gateway] FAILURE  group={ev['model_group']}  "
                f"error={ev['error']}  latency={ev['latency_ms']}ms"
            )
            continue
        tag = "FALLBACK" if ev.get("fell_back") else "SUCCESS"
        fields = [f"group={ev['model_group']}"]
        if ev.get("model"):
            fields.append(f"model={ev['model']}")
        if ev.get("model_id"):
            fields.append(f"deployment_id={ev['model_id']}")
        if ev.get("attempted_retries"):
            fields.append(f"retries={ev['attempted_retries']}")
        if ev.get("attempted_fallbacks"):
            fields.append(f"fallbacks={ev['attempted_fallbacks']}")
        fields.append(f"latency={ev['latency_ms']}ms")
        print(f"  [gateway] {tag}  " + "  ".join(fields))


def _check_gateway_reachable() -> bool:
    try:
        urllib.request.urlopen(f"{PROXY_URL}/health/liveliness", timeout=3)
        return True
    except (urllib.error.URLError, TimeoutError):
        return False


# ── ADK ask helper (scenarios 1A/1B + REPL — routing is invisible here) ────
#
# The agent itself only knows "call my LiteLlm model" — agent.py pointed
# that model at the gateway container. ADK doesn't expose the underlying
# HTTP response headers per turn, so these events are lighter than the ones
# from _gateway_ask() below: no retry/fallback counts, just confirmation of
# which group was requested and how long it took.


async def _ask(runner, user_id: str, session_id: str, prompt: str, model_group: str) -> dict:
    reply = ""
    start = time.monotonic()
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=_build_message(prompt),
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                reply = event.content.parts[0].text or ""
    latency_ms = round((time.monotonic() - start) * 1000)
    return {
        "status": "success",
        "model_group": model_group,
        "latency_ms": latency_ms,
        "reply": reply.strip(),
    }


# ── Gateway ask helper (fallback scenarios call the proxy directly) ────────


async def _gateway_ask(model_group: str, prompt: str) -> dict:
    """
    Call the LiteLLM gateway directly for `model_group`, bypassing the ADK
    runner, so the routing event carries the full header detail (retries,
    fallbacks, actual model) the way an infra engineer debugging the
    gateway would look at it.
    """
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    return await call_gateway(model_group, messages)


async def _pool_probe(model_group: str, label: str, rounds: int = 5) -> None:
    """
    Fire a handful of trivial requests directly at the gateway (bypassing
    ADK) so the x-litellm-model-id header can show *which* pool member
    answered each one. Not part of the agent flow — just proof that
    router_settings.routing_strategy is actually spreading load across the
    providers configured in litellm_config.yaml, which the ADK-based
    scenario above can't show on its own.
    """
    print(f"  [pool check] {rounds} quick direct calls to {label} (not through ADK):")
    events = await asyncio.gather(
        *[_gateway_ask(model_group, "Reply with just the word: ready.") for _ in range(rounds)]
    )
    seen = set()
    for i, ev in enumerate(events, start=1):
        model_id = ev.get("model_id") or "unknown"
        seen.add(model_id)
        print(f"    call {i}: deployment_id={model_id}  latency={ev['latency_ms']}ms")
    print(f"  → {len(seen)} distinct pool member(s) answered across {rounds} calls.\n")


# ── Scripted scenarios ─────────────────────────────────────────────────────


async def scenario_1a_faq_routing(faq_runner, faq_user, faq_session) -> None:
    _sep()
    print("  Scenario 1A — FAQ routing (fast-faq model group)")
    _sep()
    print("\n  Route: fast-faq")
    print(_wrap(FAST_MODEL_LABEL))
    print("\n  Short, factual queries — optimised for latency and cost.\n")

    prompts = [
        "What is your baggage allowance for domestic flights within India?",
        "Do I need a visa for a 5-day trip from India to Thailand?",
        "What are your customer support hours if my flight gets delayed?",
    ]
    for prompt in prompts:
        route = classify_query(prompt)
        print(f"  classify_query → {route}")
        print(f"  You: {prompt}\n")
        event = await _ask(faq_runner, faq_user, faq_session, prompt, FAST_FAQ_GROUP)
        print("  [aria_faq]")
        print(_wrap(event["reply"]))
        _print_routing_events([event])
        print()

    print(
        "  Notice: all three queries hit the fast-faq group. Latency is low\n"
        "  and token counts are small — the right trade-off for FAQ traffic.\n"
        "  No agent code changed to produce this routing — it's a model_name\n"
        "  entry in litellm_config.yaml. The ADK agent only sees its own\n"
        "  replies though — it has no visibility into *which* pool member\n"
        "  answered each turn. The probe below bypasses ADK to show that.\n"
    )

    await _pool_probe(FAST_FAQ_GROUP, "aria_faq's fast-faq pool")


async def scenario_1b_planning_routing(plan_runner, plan_user, plan_session) -> None:
    _sep()
    print("  Scenario 1B — Itinerary planning routing (deep-planning model group)")
    _sep()
    print("\n  Route: deep-planning")
    print(_wrap(DEEP_MODEL_LABEL))
    print("\n  Multi-step queries that need structured, longer reasoning.\n")

    prompts = [
        "Plan a 10-day trip to Japan for two adults and one child, starting from Bengaluru in October, with a mix of cities and one day at an onsen.",
        "Suggest a 5-day budget trip to the Andamans with snorkeling, and include rough daily costs in INR.",
    ]
    for prompt in prompts:
        route = classify_query(prompt)
        print(f"  classify_query → {route}")
        short_prompt = textwrap.shorten(prompt, width=70, placeholder="...")
        print(f"  You: {short_prompt}\n")
        event = await _ask(plan_runner, plan_user, plan_session, prompt, DEEP_PLANNING_GROUP)
        # Trim long planning responses for demo readability
        short_reply = textwrap.shorten(event["reply"], width=300, placeholder=" ...")
        print("  [aria_planning]")
        print(_wrap(short_reply))
        _print_routing_events([event])
        print()

    print(
        "  Notice: the deep-planning group was chosen automatically — higher\n"
        "  latency and token usage are expected and acceptable for itinerary\n"
        "  quality. The agent is unaware of the routing decision, and unaware\n"
        "  that a gateway container is even involved. Like fast-faq, this is a\n"
        "  multi-provider pool — skipping a live pool-member probe here since\n"
        "  each flagship reasoning model costs real time and money; watch\n"
        "  `docker compose logs -f litellm` while this scenario runs if you\n"
        "  want to see the gateway's per-request pool pick.\n"
    )


async def scenario_2a_error_fallback() -> None:
    _sep()
    print("  Scenario 2A — Fallback on model error")
    _sep()
    print("\n  Gateway config (litellm_config.yaml):")
    print("    fallback-demo : openrouter/google/bad-model-xyz   ← non-existent, will fail")
    print(f"    backup        : {BACKUP_MODEL_LABEL}")
    print("    fallbacks     : fallback-demo → backup  (num_retries: 1)\n")

    prompts = [
        "Find me the cheapest non-stop flight from Bengaluru to Delhi this Friday evening.",
        "Show me options for pet-friendly hotels in Mumbai for this weekend, near Bandra.",
    ]
    for prompt in prompts:
        print(f"  You: {prompt}\n")
        event = await _gateway_ask(FALLBACK_DEMO_GROUP, prompt)
        _print_routing_events([event])
        print(f"\n  [aria via backup]\n{_wrap(event['reply'])}\n")

    print(
        "  Notice: the client only ever sees one HTTP response — the gateway\n"
        "  retried the primary and fell back to backup internally. The\n"
        "  x-litellm-attempted-fallbacks header on that response is how we\n"
        "  know a fallback happened at all. No agent or demo code changed to\n"
        "  produce this — it's entirely litellm_config.yaml.\n"
    )


async def scenario_2b_timeout_fallback() -> None:
    _sep()
    print("  Scenario 2B — Fallback on timeout")
    _sep()
    print("\n  Gateway config (litellm_config.yaml):")
    print(f"    timeout-demo : {DEEP_MODEL_LABEL}  timeout=0.001s  ← guaranteed timeout")
    print(f"    backup       : {BACKUP_MODEL_LABEL}  timeout=30s   ← cross-provider")
    print("    fallbacks    : timeout-demo → backup\n")

    prompts = [
        "Compare red-eye vs daytime flights from Bengaluru to Dubai next week, including approximate arrival times and jet-lag impact.",
        "Suggest a sequence of cities for a 3-week USA trip starting in New York and ending in San Francisco, balancing cost and travel time.",
    ]
    for prompt in prompts:
        short_prompt = textwrap.shorten(prompt, width=70, placeholder="...")
        print(f"  You: {short_prompt}\n")
        event = await _gateway_ask(TIMEOUT_DEMO_GROUP, prompt)
        _print_routing_events([event])
        print(f"\n  [aria via backup]\n{_wrap(event['reply'])}\n")

    print(
        "  Notice: the primary timed out and the gateway switched to the\n"
        "  backup before returning anything to this process. Timeout\n"
        "  threshold is a tuning knob in litellm_config.yaml — no agent code\n"
        "  changes needed, and no code change here either.\n"
    )


async def scenario_3a_burst_fallback() -> None:
    _sep()
    print("  Scenario 3A — Burst of requests hitting fallback")
    _sep()
    print("\n  Sending 3 requests concurrently. Primary is broken for all of them.")
    print("  Showing that the gateway's retry limit holds and stays responsive.\n")

    prompts = [
        "I need last-minute flights to Goa for this weekend; show me options under ₹10,000.",
        "Find two adjacent aisle seats on an evening flight from Chennai to Hyderabad tomorrow.",
        "List budget hotels near Jaipur old city for a 4-night stay next month.",
    ]
    events = await asyncio.gather(
        *[_gateway_ask(FALLBACK_DEMO_GROUP, p) for p in prompts],
        return_exceptions=False,
    )

    print("  Gateway routing events (all 3 concurrent requests):")
    _print_routing_events(events)
    print()
    for i, (prompt, ev) in enumerate(zip(prompts, events), start=1):
        short_p = textwrap.shorten(prompt, width=58, placeholder="...")
        short_r = textwrap.shorten(str(ev["reply"]), width=110, placeholder=" ...")
        print(f"  Request {i}: {short_p}")
        print(f"             → {short_r}")

    print(
        "\n  Notice: every request fell back quickly — no unbounded retries,\n"
        "  no hang, and the gateway container handled all 3 concurrent\n"
        "  fallback decisions on its own. TravelBot stayed responsive\n"
        "  throughout the simulated error storm.\n"
    )


# ── Free REPL (routing-aware) ──────────────────────────────────────────────


async def run_repl(
    faq_runner, faq_user, faq_session,
    plan_runner, plan_user, plan_session,
) -> None:
    _sep("═")
    print("  Free REPL — routing-aware Aria. Type any prompt or  q  to quit.")
    print("  Each query is classified and routed to the right gateway model group.")
    _sep("═")

    while True:
        try:
            prompt = input("  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if prompt.lower() == "q":
            break
        if not prompt:
            continue

        route = classify_query(prompt)
        if route == "fast-faq":
            event = await _ask(faq_runner, faq_user, faq_session, prompt, FAST_FAQ_GROUP)
            label = "aria_faq"
        else:
            event = await _ask(plan_runner, plan_user, plan_session, prompt, DEEP_PLANNING_GROUP)
            label = "aria_planning"

        print(f"\n  [route: {route}]")
        _print_routing_events([event])
        print(f"  [{label}]")
        print(_wrap(event["reply"]))
        print()

    print("  ── session ended ──\n")


# ── Main ───────────────────────────────────────────────────────────────────


async def main() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "\n[ERROR] OPENROUTER_API_KEY is not set.\n"
            "  Copy .env.example → .env, set OPENROUTER_API_KEY, then\n"
            "  docker compose up -d to (re)start the gateway with it.\n"
        )
        return

    if not _check_gateway_reachable():
        print(
            f"\n[ERROR] Can't reach the LiteLLM gateway at {PROXY_URL}.\n"
            "  Start it with:\n"
            "    docker compose up -d\n"
            "    docker compose ps        # wait for \"healthy\"\n"
        )
        return

    print("""
+======================================================================+
|   DAY 07a — Routing and Fallback via a standalone LiteLLM gateway   |
|   Google ADK · LiteLLM Proxy (Docker) · OpenRouter                  |
+======================================================================+""")
    print(_GUIDE)
    print(f"  Gateway: {PROXY_URL}  (docker compose service: litellm)\n")

    repl_only = "--repl" in sys.argv

    faq_runner,  faq_user,  faq_session  = await make_runner(faq_agent)
    plan_runner, plan_user, plan_session = await make_runner(planning_agent)

    print(f"  faq session:      user={faq_user}  session={faq_session}")
    print(f"  planning session: user={plan_user}  session={plan_session}\n")

    if not repl_only:
        try:
            await scenario_1a_faq_routing(faq_runner, faq_user, faq_session)
            await scenario_1b_planning_routing(plan_runner, plan_user, plan_session)
            await scenario_2a_error_fallback()
            await scenario_2b_timeout_fallback()
            await scenario_3a_burst_fallback()
        except KeyboardInterrupt:
            print("\n  Scenarios interrupted.\n")

        cont = input("  Continue to free REPL? [y/N]: ").strip().lower()
        if cont != "y":
            return

    await run_repl(faq_runner, faq_user, faq_session, plan_runner, plan_user, plan_session)


if __name__ == "__main__":
    asyncio.run(main())
