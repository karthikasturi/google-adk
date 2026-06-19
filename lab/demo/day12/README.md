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

```bash
cd promptfoo
npx promptfoo@latest eval            # needs Node.js + network access to npm
npx promptfoo@latest view            # open the results UI
```

Or via Docker, if you'd rather not install anything with npm:

```bash
cd promptfoo
docker compose run --rm promptfoo eval
docker compose run --rm promptfoo view --port 15500
```

The Docker route mounts the repo's existing `.venv` into the container and
puts it first on `PATH`, since the official `promptfoo` image is Node-only
and has no `google-adk`/`litellm` installed for `provider.py` to import
`../agent.py` with — it shells out to whatever `python3` it finds on
`PATH`, which this resolves to the venv that already has this repo's deps.

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
  promptfooconfig.yaml  scenario group 4 — the 5 eval cases
  provider.py            runs prompts through the real agent for promptfoo
  docker-compose.yml     run promptfoo via Docker instead of npx
```

## Configuration

| Var | Default | Purpose |
|-----|---------|---------|
| `OPENROUTER_API_KEY` | — | required |
| `LANGSMITH_API_KEY` | — | optional; enables real trace export |
| `LANGSMITH_PROJECT` | `day12-travelbot` | LangSmith project name |

## Troubleshooting

- **`OPENROUTER_API_KEY is not set`** → put your key in `.env`
- **No traces in LangSmith** → check `LANGSMITH_API_KEY` is set and the key has access to `LANGSMITH_PROJECT`; the demo runs fine without it, just without export
- **`npx promptfoo` fails to find the provider** → run `npx promptfoo@latest eval` from inside `promptfoo/`, not from `day12/`
- **Chainlit reasoning panel is empty** → check the agent actually called a tool for that prompt; pure routing/refusal turns may have zero action/observation steps
