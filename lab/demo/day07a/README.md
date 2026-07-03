# Day 07a — Routing and Fallback via a standalone LiteLLM gateway

**Google ADK · LiteLLM Proxy (Docker) · OpenRouter**

Day 07 ran a `litellm.Router` inside the Python process, so the routing and
fallback *configuration* lived in `routing.py` next to the agent code. Day
07a moves that configuration into a separate, real LiteLLM proxy service —
this process only ever asks the gateway for a named model group over HTTP.
The demo scenarios and their outcomes are the same as Day 07; only where the
routing rules live has changed.

---

## What's different from Day 07

| | Day 07 | Day 07a |
|---|---|---|
| Where routing config lives | `litellm.Router` in `routing.py` | `litellm_config.yaml`, served by a separate container |
| How the app calls a model | `router.acompletion(model="primary", ...)` | HTTP call to the gateway: `openai/<group-name>` at `http://localhost:4000` |
| Changing a fallback chain | Edit `routing.py`, restart the Python process | Edit `litellm_config.yaml`, `docker compose restart litellm` |
| Visibility into a failed primary attempt | In-process `failure_callback`, fires before the fallback | Not visible directly — only the final response's `x-litellm-attempted-fallbacks` / `x-litellm-attempted-retries` headers reveal it |
| Client-side dependency | `litellm.Router` (in-process) | Any OpenAI-compatible HTTP client (`litellm.acompletion` used here as a convenient client) |

The `docker-compose.yml` + `litellm_config.yaml` pattern here is exactly what
you'd point at a real LiteLLM Cloud or self-hosted proxy deployment — the
Python application code doesn't know the difference.

---

## Prerequisites

- Docker + Docker Compose
- Python 3.12+
- An [OpenRouter](https://openrouter.ai/keys) API key

---

## Setup (run once, in order)

### 1 — Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2 — Configure environment

```bash
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY
```

### 3 — Start the gateway

```bash
docker compose up -d
docker compose ps        # wait for "healthy"
```

The gateway reads `litellm_config.yaml` on startup and exposes an
OpenAI-compatible API on `http://localhost:4000`. Edit that file to change
any routing/fallback rule, then:

```bash
docker compose restart litellm
```

### 4 — Run the demo

```bash
python demo.py
```

Skip scripted scenarios and go straight to the REPL:

```bash
python demo.py --repl
```

---

## Scenario walkthrough

Same five scenarios as Day 07 — see `demo.py`'s module docstring for the
one behavioural difference worth noticing: this process no longer sees the
*intermediate* failure when a primary model errors out, only the final
response and its routing headers.

| # | Scenario | What it demonstrates |
|---|---|---|
| 1A | FAQ routing | `classify_query()` picks `fast-faq`; ADK agent's model points at the gateway |
| 1B | Planning routing | `classify_query()` picks `deep-planning` |
| 2A | Error fallback | `fallback-demo` group's primary model doesn't exist → gateway falls back to `backup` |
| 2B | Timeout fallback | `timeout-demo` group's primary has a 1ms timeout → gateway falls back to `backup` |
| 3A | Burst fallback | 3 concurrent requests, all falling back, gateway stays responsive |

---

## Gateway config reference (`litellm_config.yaml`)

| Model group | Primary | Fallback | Purpose |
|---|---|---|---|
| `fast-faq` | `openrouter/google/gemini-2.5-flash` | — | Scenario 1A |
| `deep-planning` | `openrouter/google/gemini-2.5-pro` | — | Scenario 1B |
| `backup` | `openrouter/openai/gpt-4o-mini` | — | Fallback target for the two groups below |
| `fallback-demo` | `openrouter/google/bad-model-xyz` (doesn't exist) | `backup` | Scenario 2A / 3A |
| `timeout-demo` | `openrouter/google/gemini-2.5-pro`, `timeout: 0.001` | `backup` | Scenario 2B |

`litellm_settings.num_retries`, `allowed_fails`, and `cooldown_time` apply
gateway-wide — tune them in one place instead of per client.

---

## Docker Compose commands

```bash
# Start the gateway
docker compose up -d

# Check health
docker compose ps

# View logs (useful for seeing the gateway's own retry/fallback decisions)
docker compose logs -f litellm

# Apply a litellm_config.yaml change
docker compose restart litellm

# Stop the gateway
docker compose down
```

---

## File structure

```
day07a/
├── docker-compose.yml     # LiteLLM gateway service
├── litellm_config.yaml    # Routing/fallback rules — the single source of truth
├── .env.example           # Environment variable template
├── requirements.txt       # Python dependencies
├── routing.py             # Thin gateway client: classify_query() + call_gateway()
├── agent.py               # Aria — ADK agents pointed at the gateway container
├── session.py             # In-memory ADK sessions (unchanged from Day 07)
└── demo.py                # Scripted scenarios + free REPL
```
