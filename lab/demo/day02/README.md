# Day 02 — Prompt Refinement, Intent Modeling, and Manual Testing

Google ADK · Gemini 2.5 Flash via OpenRouter · ADK Web

---

## What this demo shows

| Example | Concept |
|---|---|
| `friendly_travel` | Warm tone driven by system prompt |
| `formal_airline` | Same query, formal tone — shows tone is prompt-controlled |
| `scope_limited_support` | Scope enforcement and polite refusal |
| `unknown_data` | Honest fallback when live data is unavailable |
| `session_memory` | Multi-turn context within a single session |

Each example lives in its own folder under `examples/`.
The **folder structure is deliberate** — it makes prompt differences visible
and lets you open two folders side-by-side to compare them.

---

## Setup

```bash
# 1. Activate the shared virtual environment (from repo root)
source .venv/bin/activate

# 2. Copy the env file and add your OpenRouter key
cp .env.example .env
# edit .env and set OPENROUTER_API_KEY

# 3. Install dependencies (if not already installed)
pip install -r requirements.txt
```

---

## Running in ADK Web

### All examples at once (pick one from the left panel)

```bash
cd lab/demo/day02
adk web examples/
```

### One example at a time

```bash
cd lab/demo/day02
adk web examples/friendly_travel
adk web examples/formal_airline
adk web examples/scope_limited_support
adk web examples/unknown_data
adk web examples/session_memory
```

Open `http://localhost:8000` in your browser.

---

## Suggested test messages per example

### friendly_travel
```
I'm planning a trip to Japan for the first time. Where should I start?
```

### formal_airline
```
I need guidance on changing my connecting flight due to a delay.
```

### scope_limited_support
```
Can you tell me about the baggage allowance for my flight?
```
Then try an out-of-scope question:
```
What is the capital of France?
```

### unknown_data
```
What is the current price of a flight from Chennai to London tomorrow?
```

### session_memory
```
Turn 1: I'm travelling to Bali with my family of four in August.
Turn 2: What kind of accommodation would suit us?
```

---

## How to experiment

1. Open `instruction.txt` in any example folder.
2. Change a word — e.g., swap "warm" for "concise" in `friendly_travel`.
3. Restart `adk web` (Ctrl-C, then re-run).
4. Send the same message and observe the difference in reply style.

This is the core learning: **the instruction is the lever.**
