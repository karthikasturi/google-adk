"""
demo.py — Day 09a: Native ADK Multi-Agent Patterns
=====================================================
Google ADK · sub_agents routing + Workflow graphs (sequential edges,
fan-out/fan-in via JoinNode) · OpenRouter

Three groups, each demoing one native ADK multi-agent building block (see
agent.py for the full picture):

  A. Agent routing      concierge_agent hands whole turns off to
     (sub_agents)        trips_specialist / support_specialist via the
                         built-in transfer_to_agent tool - including a
                         specialist-to-specialist handoff.

  B. Sequential graph    trip_prep_pipeline runs booking_check_step ->
     (Workflow edges)    itinerary_step -> recap_step, in that fixed
                         order, passing data via output_key + {state}.

  C. Parallel + merge    trip_research_pipeline fans out from START to
     (Workflow,          attractions_researcher and weather_researcher
      fan-out/fan-in)    concurrently, joins via JoinNode, then
                         trip_synthesizer combines both into one plan.

Then drops into a REPL on concierge_agent (Group A) so you can keep
exploring handoffs. Type  q  to quit.

Run:
    cp .env.example .env   # fill in OPENROUTER_API_KEY
    python demo.py         # all groups then REPL
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

# ── Silence noise (same as previous days) ──────────────────────────────────
logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False

from agent import concierge_agent, trip_prep_pipeline, trip_research_pipeline
from session import make_runner

# ── Scenario guide ───────────────────────────────────────────────────────────
_GUIDE = """
  SCENARIO GUIDE — Day 09a: Native ADK Multi-Agent Patterns
  ──────────────────────────────────────────────────────────────────────
  A. Agent routing       concierge_agent -> [transfer_to_agent] ->
     (sub_agents)         trips_specialist / support_specialist
  B. Sequential graph     trip_prep_pipeline:
     (Workflow edges)      booking_check_step -> itinerary_step -> recap_step
  C. Parallel + merge     trip_research_pipeline:
     (Workflow,            [attractions_researcher | weather_researcher]
      fan-out/JoinNode)     -> trip_research_join -> trip_synthesizer
  ──────────────────────────────────────────────────────────────────────
  A1  Concierge -> Trips      a planning request gets transferred
  A2  Peer handoff            (same session) a booking question gets
                               handed from trips_specialist to
                               support_specialist directly
  A3  Direct answer           a general question is answered by
                               concierge_agent itself - no transfer
  B1  Sequential pipeline     booking check -> itinerary -> recap, in
                               that fixed order every time
  C1  Parallel + synthesis    attractions + weather research run at the
                               same time, then get merged into one plan
  ──────────────────────────────────────────────────────────────────────
"""

# ── Console helpers ──────────────────────────────────────────────────────────


def _wrap(text: str, width: int = 74) -> str:
    prefix = "    "
    return textwrap.fill(text, width=width, initial_indent=prefix, subsequent_indent=prefix)


def _sep(char: str = "─", width: int = 70) -> None:
    print(f"  {char * width}")


def _build_message(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


def _format_tool_result(response: dict) -> str:
    """Render a function_response dict for console output."""
    if "error" in response:
        return f"ERROR: {response['error']}"
    text = " ".join(str(response).split())
    return textwrap.shorten(text, width=160, placeholder=" ...")


def _format_state_value(value) -> str:
    text = " ".join(str(value).split())
    return textwrap.shorten(text, width=120, placeholder=" ...")


# ── ADK ask helper ───────────────────────────────────────────────────────────


async def _run_traced(runner, user_id: str, session_id: str, prompt: str) -> tuple[str, list[dict], str]:
    """
    Run one turn and return (reply, trace, final_author):
      trace        — ordered list of steps: tool calls/results, agent
                      transfers, and output_key state writes, each tagged
                      with the agent ("author") that produced it
      final_author — the name of the agent whose text became the reply
                      (the active specialist after a transfer, or the
                      last step of a pipeline)
    """
    trace: list[dict] = []
    reply = ""
    final_author = ""

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=_build_message(prompt),
    ):
        author = event.author

        if event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "function_call", None):
                    fc = part.function_call
                    trace.append({"agent": author, "type": "call", "tool": fc.name, "args": dict(fc.args or {})})
                if getattr(part, "function_response", None):
                    fr = part.function_response
                    trace.append({"agent": author, "type": "result", "tool": fr.name, "response": fr.response or {}})

        if event.actions:
            if event.actions.transfer_to_agent:
                trace.append({"agent": author, "type": "transfer", "to": event.actions.transfer_to_agent})
            for key, value in (event.actions.state_delta or {}).items():
                if key.startswith("_") or ":" in key:
                    continue
                trace.append({"agent": author, "type": "state", "key": key, "value": value})

        if event.is_final_response():
            if event.content and event.content.parts:
                text = event.content.parts[0].text
                if text:
                    reply = text
                    final_author = author

    return reply.strip(), trace, final_author


def _print_trace(trace: list[dict]) -> None:
    if not trace:
        print("  (no tool calls, transfers, or state writes for this turn)")
        return

    for step in trace:
        agent = step["agent"]
        if step["type"] == "call":
            args = ", ".join(f"{k}={v!r}" for k, v in step["args"].items())
            print(f"  [{agent}] tool call    {step['tool']}({args})")
        elif step["type"] == "result":
            print(f"  [{agent}] tool result  {step['tool']} -> {_format_tool_result(step['response'])}")
        elif step["type"] == "transfer":
            print(f"  [{agent}] transfer_to_agent -> {step['to']}")
        elif step["type"] == "state":
            print(f"  [{agent}] writes state['{step['key']}'] = {_format_state_value(step['value'])}")


def _describe_route(trace: list[dict]) -> str:
    """Summarise any transfer_to_agent hops in `trace` as 'a -> b -> c'."""
    hops = [step for step in trace if step["type"] == "transfer"]
    if not hops:
        return "no transfer — answered directly"
    path = " -> ".join([hops[0]["agent"]] + [hop["to"] for hop in hops])
    return f"routed: {path}"


async def _turn(runner, user_id: str, session_id: str, prompt: str, label: str | None = None) -> tuple[str, list[dict], str]:
    print(f"  You: {prompt}\n")
    reply, trace, final_author = await _run_traced(runner, user_id, session_id, prompt)
    _print_trace(trace)
    print(f"\n  [{label or final_author or 'agent'}]")
    print(_wrap(reply))
    print()
    return reply, trace, final_author


# ── Group A: agent routing (sub_agents + transfer_to_agent) ─────────────────


async def scenario_a1_concierge_to_trips(runner, user_id, session_id) -> None:
    _sep()
    print("  Group A1 — Concierge routes to the Trips specialist")
    _sep()
    print(
        "\n  Expect: concierge_agent calls the built-in transfer_to_agent\n"
        "  tool to hand the whole turn to trips_specialist.\n"
    )

    _, trace, _ = await _turn(
        runner, user_id, session_id,
        "Plan a 3-day trip to Singapore with kid-friendly activities.",
    )

    print(
        f"  Notice: {_describe_route(trace)}. ADK added transfer_to_agent\n"
        "  automatically because trips_specialist is a sub_agent of\n"
        "  concierge_agent — no custom delegation tool was written for it.\n"
        "  From here, trips_specialist is the active agent for this session.\n"
    )


async def scenario_a2_peer_handoff(runner, user_id, session_id) -> None:
    _sep()
    print("  Group A2 — Specialist-to-specialist handoff")
    _sep()
    print(
        "\n  Same session as A1, so trips_specialist is still active.\n"
        "  Expect it to hand this booking question off to\n"
        "  support_specialist — directly, or via concierge_agent.\n"
    )

    _, trace, _ = await _turn(
        runner, user_id, session_id,
        "Also, can you check the status of booking BLR-DEL-123?",
    )

    print(
        f"  Notice: {_describe_route(trace)}. Either way, support_specialist\n"
        "  ends up answering — peers (and the parent) are valid transfer\n"
        "  targets for any agent in the tree, not just the root.\n"
    )


async def scenario_a3_direct_answer(runner, user_id, session_id) -> None:
    _sep()
    print("  Group A3 — Concierge answers directly")
    _sep()
    print(
        "\n  New session. Expect a general question to be answered by\n"
        "  concierge_agent itself, with no transfer.\n"
    )

    _, trace, _ = await _turn(
        runner, user_id, session_id,
        "Hi! What can TravelBot help me with?",
    )

    print(
        f"  Notice: {_describe_route(trace)}. concierge_agent judged its own\n"
        "  description sufficient for a general capabilities question.\n"
    )


# ── Group B: Workflow graph (sequential edges) ──────────────────────────────


async def scenario_b1_sequential_pipeline(runner, user_id, session_id) -> None:
    _sep()
    print("  Group B1 — Sequential pipeline (a graph with one path)")
    _sep()
    print(
        "\n  trip_prep_pipeline is a Workflow graph:\n"
        "    (START, booking_check_step, itinerary_step, recap_step)\n"
        "  which always runs in this order. Expect step 1 to find a delay,\n"
        "  step 2 to adjust the itinerary for it, and step 3 to combine\n"
        "  both for the traveller.\n"
    )

    await _turn(
        runner, user_id, session_id,
        "My booking is BOM-DXB-552 (Mumbai to Dubai) - check it and plan a "
        "3-day Dubai itinerary with family activities.",
        label="trip_prep_pipeline",
    )

    print(
        "  Notice: the trace ran strictly in order. booking_check_step wrote\n"
        "  state['booking_summary'], itinerary_step's instruction pulled it\n"
        "  back in via {booking_summary} and wrote itinerary_plan, and\n"
        "  recap_step combined both via {booking_summary} and\n"
        "  {itinerary_plan}. The Workflow graph's edges enforce this order\n"
        "  regardless of what any step's LLM might otherwise 'want' to do.\n"
    )


# ── Group C: Workflow graph (fan-out from START, JoinNode fan-in) ───────────


async def scenario_c1_parallel_pipeline(runner, user_id, session_id) -> None:
    _sep()
    print("  Group C1 — Parallel research, then sequential synthesis")
    _sep()
    print(
        "\n  trip_research_pipeline is a Workflow graph:\n"
        "    (START, attractions_researcher, trip_research_join)\n"
        "    (START, weather_researcher, trip_research_join)\n"
        "    (trip_research_join, trip_synthesizer)\n"
        "  Expect the two researchers' steps to interleave in the trace\n"
        "  (both branches start at START, so they run concurrently), then\n"
        "  trip_research_join waits for both before trip_synthesizer runs.\n"
    )

    await _turn(
        runner, user_id, session_id,
        "I'm planning 3 days in Singapore with kid-friendly activities - "
        "what should I do and when?",
        label="trip_research_pipeline",
    )

    print(
        "  Notice: attractions_researcher and weather_researcher ran\n"
        "  concurrently (both edges fan out from START) - their tool\n"
        "  calls/results and output_key writes interleave in the trace.\n"
        "  trip_research_join then waited for both branches before\n"
        "  trip_synthesizer read {attractions_findings} and\n"
        "  {weather_findings} from state to produce a weather-aware\n"
        "  day-by-day plan - notice Day 1 (thunderstorms) gets treated\n"
        "  differently from the sunnier days.\n"
    )


def print_observability_notes() -> None:
    _sep("═")
    print("  Group D — Observability walkthrough")
    _sep("═")
    print(
        "\n  Compare these traces with Day 09's custom delegation tools:\n"
        "    - Group A: routing is now a framework feature. concierge_agent\n"
        "      never calls a 'delegate_to_*' tool - ADK injects\n"
        "      transfer_to_agent automatically based on each sub_agent's\n"
        "      description, and A2 shows it also works peer-to-peer.\n"
        "    - Group B: trip_prep_pipeline is a Workflow graph with one\n"
        "      path - the edges (START -> booking_check_step ->\n"
        "      itinerary_step -> recap_step) fix the order, and {state}\n"
        "      placeholders in each step's instruction are filled from the\n"
        "      previous step's output_key.\n"
        "    - Group C: trip_research_pipeline is a Workflow graph that\n"
        "      fans the same request out to two independent specialists\n"
        "      from START (the graph briefly splits into two branches),\n"
        "      then a JoinNode waits for both before feeding their results\n"
        "      into one synthesis step (the branches join back together).\n"
        "\n  All three patterns are declarative - you describe the agents and\n"
        "  how they're wired (sub_agents / Workflow edges with START and\n"
        "  JoinNode), and ADK handles routing, ordering, and concurrency for\n"
        "  you.\n"
    )


# ── Free REPL ──────────────────────────────────────────────────────────────────


async def run_repl(runner, user_id, session_id) -> None:
    _sep("═")
    print("  Free REPL — TravelBot Concierge (Group A: native ADK routing).")
    print("  Ask about an itinerary, then ask about a booking (or vice")
    print("  versa) to see specialist-to-specialist handoffs. Type a")
    print("  prompt or  q  to quit.")
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

        reply, trace, final_author = await _run_traced(runner, user_id, session_id, prompt)
        _print_trace(trace)
        print(f"\n  [{final_author or 'concierge_agent'}]")
        print(_wrap(reply))
        print()

    print("  ── session ended ──\n")


# ── Main ─────────────────────────────────────────────────────────────────────


async def main() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "\n[ERROR] OPENROUTER_API_KEY is not set.\n"
            "  Copy .env.example → .env and fill in your key.\n"
        )
        return

    print("""
+======================================================================+
|   DAY 09a — Native ADK Multi-Agent Patterns                          |
|   Google ADK · sub_agents routing + Workflow graphs · OpenRouter     |
+======================================================================+""")
    print(_GUIDE)

    repl_only = "--repl" in sys.argv

    if not repl_only:
        try:
            # A1/A2 share one session so A2 can show the handoff that
            # follows A1's transfer.
            a_runner, a_user, a_session = await make_runner(concierge_agent)
            await scenario_a1_concierge_to_trips(a_runner, a_user, a_session)
            await scenario_a2_peer_handoff(a_runner, a_user, a_session)

            await scenario_a3_direct_answer(*await make_runner(concierge_agent))
            await scenario_b1_sequential_pipeline(*await make_runner(trip_prep_pipeline))
            await scenario_c1_parallel_pipeline(*await make_runner(trip_research_pipeline))
            print_observability_notes()
        except KeyboardInterrupt:
            print("\n  Scenarios interrupted.\n")

        cont = input("  Continue to free REPL? [y/N]: ").strip().lower()
        if cont != "y":
            return

    await run_repl(*await make_runner(concierge_agent))


if __name__ == "__main__":
    asyncio.run(main())
