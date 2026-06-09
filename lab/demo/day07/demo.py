"""
demo.py — Day 07: LiteLLM Routing and Fallback
================================================
Google ADK · LiteLLM Router · OpenRouter

Runs five scripted scenarios:
  1A  FAQ routing       — simple questions routed to the fast-faq model group
  1B  Plan routing      — complex itineraries routed to the deep-planning group
  2A  Error fallback    — primary model fails, LiteLLM retries with backup
  2B  Timeout fallback  — primary times out, LiteLLM switches to backup
  3A  Burst fallback    — concurrent requests, all hitting fallback, staying responsive

Then drops into a routing-aware REPL. Type  q  to quit.

Run:
    cp .env.example .env   # fill in OPENROUTER_API_KEY
    python demo.py         # all scenarios then REPL
    python demo.py --repl  # skip scenarios, go straight to REPL
"""

import asyncio
import logging
import os
import sys
import textwrap

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

log = logging.getLogger("day07")
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

from agent import faq_agent, planning_agent
from routing import (
    BACKUP_MODEL,
    DEEP_MODEL,
    FAST_MODEL,
    classify_query,
    enable_routing_callbacks,
    fallback_demo_router,
    routing_log,
    timeout_demo_router,
)
from session import make_runner

# Enable routing event capture — fires for every litellm call in this process
enable_routing_callbacks()

# ── Scenario guide ─────────────────────────────────────────────────────────
_GUIDE = """
  SCENARIO GUIDE — Day 07: LiteLLM Routing and Fallback
  ──────────────────────────────────────────────────────────────────────
  1A  FAQ routing       Simple questions → fast-faq model group
  1B  Plan routing      Complex itineraries → deep-planning model group
  2A  Error fallback    Primary model fails → LiteLLM retries with backup
  2B  Timeout fallback  Primary times out  → LiteLLM switches to backup
  3A  Burst fallback    Concurrent requests, all hitting fallback, staying responsive
  ──────────────────────────────────────────────────────────────────────
"""

# ── Console helpers ────────────────────────────────────────────────────────


def _wrap(text: str, width: int = 74) -> str:
    prefix = "    "
    return textwrap.fill(text, width=width, initial_indent=prefix, subsequent_indent=prefix)


def _sep(char: str = "─", width: int = 70) -> None:
    print(f"  {char * width}")


def _build_message(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


def _print_routing_events(events: list[dict]) -> None:
    """Print captured gateway routing events for the current scenario."""
    for ev in events:
        if ev["status"] == "success":
            print(f"  [gateway] SUCCESS  model={ev['model']}  latency={ev['latency_ms']}ms")
        else:
            print(f"  [gateway] FAILURE  model={ev['model']}  error={ev['error']}")


# ── ADK ask helper ─────────────────────────────────────────────────────────


async def _ask(runner, user_id: str, session_id: str, prompt: str) -> str:
    reply = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=_build_message(prompt),
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                reply = event.content.parts[0].text or ""
    return reply.strip()


# ── Router ask helper (fallback scenarios bypass the ADK runner) ───────────


async def _router_ask(router, prompt: str) -> str:
    """
    Call router.acompletion() directly with a minimal system prompt.
    Used for fallback scenarios where we want to observe the router's
    error-handling chain without going through the ADK runner.
    """
    messages = [
        {"role": "system", "content": "You are Aria, TravelBot's friendly travel assistant. Keep answers concise."},
        {"role": "user",   "content": prompt},
    ]
    try:
        response = await router.acompletion(model="primary", messages=messages)
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        return f"[error after all retries: {exc}]"


# ── Scripted scenarios ─────────────────────────────────────────────────────


async def scenario_1a_faq_routing(faq_runner, faq_user, faq_session) -> None:
    _sep()
    print("  Scenario 1A — FAQ routing (fast-faq model group)")
    _sep()
    print(f"\n  Route: fast-faq  →  model: {FAST_MODEL}")
    print("  Short, factual queries — optimised for latency and cost.\n")

    prompts = [
        "What is your baggage allowance for domestic flights within India?",
        "Do I need a visa for a 5-day trip from India to Thailand?",
        "What are your customer support hours if my flight gets delayed?",
    ]
    for prompt in prompts:
        routing_log.clear()
        route = classify_query(prompt)
        print(f"  classify_query → {route}")
        print(f"  You: {prompt}\n")
        reply = await _ask(faq_runner, faq_user, faq_session, prompt)
        print("  [aria_faq]")
        print(_wrap(reply))
        _print_routing_events(routing_log)
        print()

    print(
        "  Notice: all three queries hit the fast-faq group. Latency is low\n"
        "  and token counts are small — the right trade-off for FAQ traffic.\n"
        "  No agent code changed to produce this routing.\n"
    )


async def scenario_1b_planning_routing(plan_runner, plan_user, plan_session) -> None:
    _sep()
    print("  Scenario 1B — Itinerary planning routing (deep-planning model group)")
    _sep()
    print(f"\n  Route: deep-planning  →  model: {DEEP_MODEL}")
    print("  Multi-step queries that need structured, longer reasoning.\n")

    prompts = [
        "Plan a 10-day trip to Japan for two adults and one child, starting from Bengaluru in October, with a mix of cities and one day at an onsen.",
        "Suggest a 5-day budget trip to the Andamans with snorkeling, and include rough daily costs in INR.",
    ]
    for prompt in prompts:
        routing_log.clear()
        route = classify_query(prompt)
        print(f"  classify_query → {route}")
        short_prompt = textwrap.shorten(prompt, width=70, placeholder="...")
        print(f"  You: {short_prompt}\n")
        reply = await _ask(plan_runner, plan_user, plan_session, prompt)
        # Trim long planning responses for demo readability
        short_reply = textwrap.shorten(reply, width=300, placeholder=" ...")
        print("  [aria_planning]")
        print(_wrap(short_reply))
        _print_routing_events(routing_log)
        print()

    print(
        "  Notice: the deep-planning group was chosen automatically — higher\n"
        "  latency and token usage are expected and acceptable for itinerary\n"
        "  quality. The agent is unaware of the routing decision.\n"
    )


async def scenario_2a_error_fallback() -> None:
    _sep()
    print("  Scenario 2A — Fallback on model error")
    _sep()
    print("\n  Router config:")
    print("    primary : openrouter/google/bad-model-xyz   ← non-existent, will fail")
    print(f"    backup  : {BACKUP_MODEL}")
    print("    retries : 1  (retry primary once, then use backup)\n")

    prompts = [
        "Find me the cheapest non-stop flight from Bengaluru to Delhi this Friday evening.",
        "Show me options for pet-friendly hotels in Mumbai for this weekend, near Bandra.",
    ]
    for prompt in prompts:
        routing_log.clear()
        print(f"  You: {prompt}\n")
        reply = await _router_ask(fallback_demo_router, prompt)
        _print_routing_events(routing_log)
        print(f"\n  [aria via backup]\n{_wrap(reply)}\n")

    print(
        "  Notice: the primary call failed (FAILURE in gateway log) and LiteLLM\n"
        "  switched to the backup — TravelBot answered normally. The fallback\n"
        "  chain is config-only; no agent code changed.\n"
    )


async def scenario_2b_timeout_fallback() -> None:
    _sep()
    print("  Scenario 2B — Fallback on timeout")
    _sep()
    print("\n  Router config:")
    print(f"    primary : {DEEP_MODEL}  timeout=0.001s  ← guaranteed timeout")
    print(f"    backup  : {BACKUP_MODEL}  timeout=30s   ← cross-provider")
    print("    retries : 0  (timeout once → immediately use backup)\n")

    prompts = [
        "Compare red-eye vs daytime flights from Bengaluru to Dubai next week, including approximate arrival times and jet-lag impact.",
        "Suggest a sequence of cities for a 3-week USA trip starting in New York and ending in San Francisco, balancing cost and travel time.",
    ]
    for prompt in prompts:
        routing_log.clear()
        short_prompt = textwrap.shorten(prompt, width=70, placeholder="...")
        print(f"  You: {short_prompt}\n")
        reply = await _router_ask(timeout_demo_router, prompt)
        _print_routing_events(routing_log)
        print(f"\n  [aria via backup]\n{_wrap(reply)}\n")

    print(
        "  Notice: the primary timed out (Timeout in gateway log) and LiteLLM\n"
        "  switched to the backup. The response may be slightly simpler but is\n"
        "  still useful. Timeout threshold is a tuning knob in the gateway\n"
        "  config — no agent code changes needed.\n"
    )


async def scenario_3a_burst_fallback() -> None:
    _sep()
    print("  Scenario 3A — Burst of requests hitting fallback")
    _sep()
    print("\n  Sending 3 requests concurrently. Primary is broken for all of them.")
    print("  Showing that the retry limit holds and the system stays responsive.\n")

    prompts = [
        "I need last-minute flights to Goa for this weekend; show me options under ₹10,000.",
        "Find two adjacent aisle seats on an evening flight from Chennai to Hyderabad tomorrow.",
        "List budget hotels near Jaipur old city for a 4-night stay next month.",
    ]
    routing_log.clear()
    results = await asyncio.gather(
        *[_router_ask(fallback_demo_router, p) for p in prompts],
        return_exceptions=True,
    )

    print("  Gateway routing events (all 3 concurrent requests):")
    _print_routing_events(routing_log)
    print()
    for i, (prompt, reply) in enumerate(zip(prompts, results), start=1):
        short_p = textwrap.shorten(prompt, width=58, placeholder="...")
        short_r = textwrap.shorten(str(reply), width=110, placeholder=" ...")
        print(f"  Request {i}: {short_p}")
        print(f"             → {short_r}")

    print(
        "\n  Notice: every request failed on primary and fell back quickly —\n"
        "  no unbounded retries, no hang. Retry limits are respected and\n"
        "  TravelBot stayed responsive throughout the simulated error storm.\n"
    )


# ── Free REPL (routing-aware) ──────────────────────────────────────────────


async def run_repl(
    faq_runner, faq_user, faq_session,
    plan_runner, plan_user, plan_session,
) -> None:
    _sep("═")
    print("  Free REPL — routing-aware Aria. Type any prompt or  q  to quit.")
    print("  Each query is classified and routed to the right model group.")
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

        routing_log.clear()
        route = classify_query(prompt)
        if route == "fast-faq":
            reply = await _ask(faq_runner, faq_user, faq_session, prompt)
            label = "aria_faq"
        else:
            reply = await _ask(plan_runner, plan_user, plan_session, prompt)
            label = "aria_planning"

        print(f"\n  [route: {route}]")
        _print_routing_events(routing_log)
        print(f"  [{label}]")
        print(_wrap(reply))
        print()

    print("  ── session ended ──\n")


# ── Main ───────────────────────────────────────────────────────────────────


async def main() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "\n[ERROR] OPENROUTER_API_KEY is not set.\n"
            "  Copy .env.example → .env and fill in your key.\n"
        )
        return

    print("""
+======================================================================+
|   DAY 07 — LiteLLM Routing and Fallback                             |
|   Google ADK · LiteLLM Router · OpenRouter                          |
+======================================================================+""")
    print(_GUIDE)

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
