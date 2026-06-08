# Day 05 — Semantic Search & Retrieval-Augmented Generation

**Google ADK · LiteLLM · OpenRouter · OpenAI embeddings (via OpenRouter)**

A small, self-contained look at the two ideas behind RAG: turning text into
vectors you can search by meaning, and grounding an agent's answers in what
that search retrieves — instead of letting it guess from memory.

`kb.py` keeps the whole pipeline — embed, index, query — in one short file
backed by **ChromaDB**, running as an in-memory (`EphemeralClient`) collection
so there's no server or persistence directory to manage; everything is built
fresh in one process. For a persistent, on-disk version of the same idea with
a larger catalog, see `lab/travelbot/rag/` (same ChromaDB + OpenRouter
embeddings, `PersistentClient` instead).

---

## What's in here

| File | Role |
|---|---|
| `kb.py` | Tiny ChromaDB-backed knowledge base: documents, embeddings, indexing, `semantic_search()` |
| `agent.py` | `plain_agent` (no retrieval) and `root_agent` (RAG-grounded, exported for `adk web`) |
| `session.py` | In-memory session factory (same single-swap-point pattern as Day 03) |
| `demo.py` | Three scripted scenarios + free REPL |
| `tests/test_kb.py` | Offline tests for cosine similarity & ranking (embeddings stubbed) |

---

## Prerequisites

- Python 3.12+
- An [OpenRouter](https://openrouter.ai/keys) API key (used for both the chat
  model and the embedding model — same key, same provider)

---

## Setup

### 1 — Install dependencies

```bash
pip install -r requirements.txt
```

### 2 — Configure environment

```bash
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY
```

### 3 — Run the demo

```bash
python demo.py
```

Skip scripted scenarios and go straight to the REPL:

```bash
python demo.py --repl
```

Or explore in ADK Web (discovers `root_agent` automatically):

```bash
adk web .
```

---

## Scenario walkthrough

| # | Scenario | What it demonstrates |
|---|---|---|
| 1 | Semantic search in action | Raw `semantic_search()` calls — embed query, ask ChromaDB for the nearest documents, return top-k with similarity scores |
| 2 | Grounded vs ungrounded | The same TravelBot-specific question goes to `plain_agent` and `root_agent` — one guesses, the other answers from retrieved text |
| 3 | Honest fallback | A question nothing in the knowledge base covers — the grounding rules make the agent say so instead of inventing an answer |

---

## How retrieval is wired into the agent

`agent.py` defines `root_agent` with a *dynamic* instruction — an
`InstructionProvider` function (`_build_instruction`) that ADK calls fresh on
every turn:

1. Pull the latest user message out of `ReadonlyContext.user_content`.
2. Run `kb.semantic_search(query, top_k=3)`.
3. Render the results (or their absence) as a "Retrieved context" section.
4. Append it — and a short set of grounding rules — to the agent's persona.

The model never sees the raw knowledge base; it only sees whatever the search
returned for *this* question, on *this* turn. That's the whole trick: the
retrieval step happens in your code, not the model's head.

---

## Why two fictional "TravelBot policies"

`kb.py` includes two made-up documents — a 24-hour cancellation policy and an
Elite loyalty program — that no general-purpose model could already know.
When `root_agent` answers questions about them correctly, there's only one
explanation: it actually retrieved and used the text. That's what makes
Scenario 2 a convincing, checkable demonstration of grounding rather than a
coincidence of the model "happening to know."

---

## Running the tests

```bash
python -m pytest tests/ -v
```

`kb.embed` is patched with a stub that returns hand-picked vectors, so
`semantic_search`'s indexing and ranking/top-k logic are checked against a
real (in-memory) ChromaDB collection — no API key or network access required.
