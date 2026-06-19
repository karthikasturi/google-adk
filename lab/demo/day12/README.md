# Day 12 — Reasoning Loops, Observability, and Evaluation

TravelBot gains a visible reasoning trace, real distributed tracing, and an
automated eval suite on top of the same Google ADK multi-agent structure
used since Day 09/10/11:

```
concierge_agent (router, lite model)
  ├─ planner_specialist (capable model)  — flight search, comparisons, region search
  └─ support_specialist (lite model)     — cancellation policy, booking status
```

The "ReAct loop" is the same mechanism every prior day already used — the
ADK Runner keeps feeding tool results back to the model until it stops
calling tools, which **is** Thought → Action → Observation. What's new here
is that the loop is now *rendered* (`reasoning.py`), *traced*
(`tracing.py` → LangSmith), and *evaluated* (`promptfoo/`).

## Setup

```bash
cd lab/demo/day12
pip install -r requirements.txt

cp .env.example .env       # set OPENROUTER_API_KEY; LANGSMITH_API_KEY is optional

# Optional — only for the framework-native variants (see section below):
pip install -r requirements-native.txt
```

LangSmith is optional — `tracing.py` is a no-op without `LANGSMITH_API_KEY`,
so every scenario still runs with console-only reasoning traces.

PromptFoo runs via `npx` (Node.js) or Docker — no separate global install needed.

## Run

```bash
python demo.py                       # scripted scenario groups 1, 2, 3, 5 + REPL
python demo.py --repl                # skip scenarios, go straight to REPL

chainlit run chainlit_app.py -w      # UI with a collapsible "Agent Reasoning" panel
```

### PromptFoo eval (scenario group 4)

**Option A — npx (runs the agent in-process).** Simplest if you have Node.js
and network access to npm. PromptFoo shells out to this repo's Python venv to
run the agent via `provider.py`:

```bash
cd promptfoo
npx promptfoo@latest eval            # uses promptfooconfig.yaml + provider.py
npx promptfoo@latest view            # open the results UI
```

**Option B — Docker (self-contained, no host setup).** The official promptfoo
image is Node-only (Alpine) with no `google-adk` installed, so it can't run
the agent in-process. The compose file therefore has **two** services — the
agent (its own small Python image, built from `agent.Dockerfile`) and
promptfoo — wired together over the compose network. One command runs
everything:

```bash
cd promptfoo
docker compose run --rm promptfoo
```

`run` builds the agent image on first use (it pip-installs `google-adk`),
starts the `agent` service, waits for its healthcheck, then runs the eval
(`promptfooconfig.docker.yaml`) against `http://agent:8930`. For the results
UI instead of a one-shot eval:

```bash
docker compose run --rm --service-ports promptfoo promptfoo view -y --host 0.0.0.0 --port 15500
```

Clean up the agent service afterwards with `docker compose down`.

> Two earlier failures this layout fixes: `Cannot find module
> /app/dist/src/server/index.js` (an old compose mounted the config over the
> image's own `/app`) and the promptfoo container restart/exit-1 loop (it had
> nothing to connect to — now the `agent` service is a healthcheck-gated
> dependency, so promptfoo only starts once the agent is up, runs once, and
> exits cleanly with `restart: "no"`).

## Trainer scenario map

| Group | Prompt | What to show |
|---|---|---|
| **1** ReAct loop | "London → Tokyo, £900 budget, prefer direct." | Reasoning panel shows `action: search_flights` → `observation` (no direct under budget) → broadened reasoning in the final answer. |
| **1** Reflection | "Actually I'd rather have direct even if pricier." | A `reflection` step appears first (constraint-revision keyword match), then a fresh `action`/`observation` pair for the re-run search. |
| **2** Loop termination | "Cheapest flight to anywhere in Asia, ≤60 days, under £400." | `search_cheapest_in_region` returns `exhausted: true` in one call; the `exit` step says why the loop stopped instead of searching forever. |
| **3** Trace inspection | "Compare business class Dubai → New York for next Friday." | Open the LangSmith run: root span = the turn, child spans = each action/observation/exit step. Compare span durations to see where time went. |
| **4** PromptFoo eval | see `promptfoo/promptfooconfig.yaml` | 5 cases: happy-path routing, budget honesty, rejection+reflection, out-of-scope, invalid booking ID. |
| **5a** Cheap path | "What's your cancellation policy?" | Routes to `support_specialist` on the **lite** model — single tool call, no reasoning loop. |
| **5b** Capable path | "Family of 5 with mobility/pet needs, Cape Town → Vancouver." | Routes to `planner_specialist` on the **capable** model — compare LangSmith latency/cost against 5a. |

> Loop termination here is enforced by the mock data being finite
> (`search_cheapest_in_region` returns `exhausted: true` after one call) and
> by instructions telling the model not to re-query — not a hard iteration
> cap. Be upfront with participants that this is a prompt-level guardrail,
> same as every "confirm before acting" rule in earlier days, not a
> framework-level loop limiter.

## Files

```
agent.py            concierge router + planner (capable model) + support (lite model)
tools.py             mock flight search/compare/region-search/policy/booking data
reasoning.py         turns ADK events into Thought/Action/Observation/Reflection/Exit steps
tracing.py           exports each turn's steps to LangSmith as a root + child runs
session.py           ADK Runner + in-memory session factory
demo.py              scripted scenario groups 1/2/3/5 + REPL (console reasoning trace)
chainlit_app.py       UI with a collapsible "Agent Reasoning" panel per reply
promptfoo/
  promptfooconfig.yaml         scenario group 4 — npx path (in-process provider.py)
  provider.py                   runs prompts through the real agent (npx path)
  promptfooconfig.docker.yaml  Docker path — HTTP provider → agent service
  serve_agent.py                agent HTTP server (runs inside the agent container)
  agent.Dockerfile              small Python image for the agent service
  docker-compose.yml            two services: agent + promptfoo, self-contained

# ── framework-native variants (added alongside; see section below) ──
agent_native.py     same agents, but planner_specialist uses PlanReActPlanner
tracing_otel.py      routes ADK's built-in OpenTelemetry spans → LangSmith
demo_native.py       runs the planner scenarios on agent_native + OTel
requirements-native.txt   optional deps for the native variants
eval/
  travelbot.evalset.json  the 5 cases in ADK EvalSet schema
  test_eval.py            AgentEvaluator + LLM-judge (OpenRouter), via pytest
  eval_target.py          adapter so AgentEvaluator can load the day12 agent
  conftest.py             sys.path + registers the OpenRouter judge model
```

## Framework-native equivalents (ADK 2.1)

This demo deliberately hand-rolls the reasoning trace, the LangSmith export,
and the eval suite so the mechanics are visible rather than hidden behind
framework magic. ADK 2.1 ships native facilities for all three, and each one
is now implemented **alongside** the hand-rolled version so trainees can run
both and compare. Verified against the installed `google-adk==2.1.0`:

| Concern | Hand-rolled (teaching default) | ADK-native variant (added alongside) |
|---|---|---|
| **ReAct / reflection** | `reasoning.py` infers Thought/Action/Observation by parsing `function_call`/`function_response` events; reflection is a keyword heuristic | `agent_native.py` gives `planner_specialist` a `PlanReActPlanner`, so the model emits explicit `/*PLANNING*/`, `/*REASONING*/`, `/*ACTION*/`, `/*REPLANNING*/`, `/*FINAL_ANSWER*/` tags — `REPLANNING` **is** reflection, no keyword guessing. |
| **Observability** | `tracing.py` rebuilds the trace tree with `langsmith.Client.create_run()` | `tracing_otel.py` installs an OTLP exporter so ADK's own OpenTelemetry spans (every LLM + tool call, with token/cost) export to LangSmith automatically — no per-turn code. |
| **Evaluation** | `promptfoo/` (external Node tool) | `eval/` — the same cases as an ADK `*.evalset.json`, scored by `AgentEvaluator` with the `final_response_match_v2` LLM-judge (the native parallel of promptfoo's `llm-rubric`), judge pointed at OpenRouter. Run via pytest. |
| **UI** | `chainlit_app.py` (custom collapsible reasoning panel) | kept — `adk web` was intentionally **not** adopted (it can't customise the "Agent Reasoning" panel). |

Run the native variants (after `pip install -r requirements-native.txt`):

```bash
python demo_native.py              # PlanReActPlanner reasoning tags + OTel → LangSmith

cd eval && python -m pytest test_eval.py -v -s   # AgentEvaluator, OpenRouter judge
```

Two things worth flagging to trainees:
- ADK's eval **judge** resolves its model from a string via `LLMRegistry`,
  which doesn't know `openrouter/*` out of the box (the agent dodges this by
  constructing `LiteLlm` directly). `eval/conftest.py` registers it — the
  native counterpart of the `defaultTest.options.provider` fix in
  `promptfooconfig.yaml`.
- The native evalset uses the deterministic behaviours (routing, budget
  search, policy, scope, not-found); the generative reflection scenario is
  left to PromptFoo's rubric, which tolerates phrasing variation better than
  a reference-match judge.

The hand-rolled versions remain the teaching default — the native variants
are there to show what the framework does for you once the concepts land.

## Configuration

| Var | Default | Purpose |
|-----|---------|---------|
| `OPENROUTER_API_KEY` | — | required |
| `LANGSMITH_API_KEY` | — | optional; enables real trace export |
| `LANGSMITH_PROJECT` | `day12-travelbot` | LangSmith project name |
| `LANGSMITH_ENDPOINT` | US region | set to the APAC endpoint if your org is on that region |

## Troubleshooting

- **`OPENROUTER_API_KEY is not set`** → put your key in `.env`
- **No traces in LangSmith** → check `LANGSMITH_API_KEY` is set and the key has access to `LANGSMITH_PROJECT`; the demo runs fine without it, just without export
- **`npx promptfoo` fails to find the provider** → run `npx promptfoo@latest eval` from inside `promptfoo/`, not from `day12/`
- **Chainlit reasoning panel is empty** → check the agent actually called a tool for that prompt; pure routing/refusal turns may have zero action/observation steps
