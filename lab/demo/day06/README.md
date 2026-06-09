# Day 06 — PDF RAG & Configurable Vector Backends

**Google ADK · LiteLLM · OpenRouter · OpenAI embeddings · ChromaDB / AWS OpenSearch**

Day 05 showed the two ideas behind RAG — embedding text into vectors you can
search by meaning, and grounding an agent's answers in what that search
retrieves. Day 06 takes the same story and makes it production-shaped in two
ways:

1. **Real documents.** Instead of a handful of inline strings, the knowledge
   base is built by loading actual **PDF files**, extracting text page by
   page with `pypdf`, and carrying `{"source": filename, "page": N}`
   **metadata** all the way through embedding, indexing, retrieval, and into
   the agent's answers — so every grounded claim can be traced back to an
   exact page of an exact document and even **cited**.
2. **A configurable vector backend.** `kb.py` doesn't talk to a vector store
   directly — it asks `backends.get_backend()` for one, chosen at runtime by
   the `VECTOR_BACKEND` env var: an in-memory **ChromaDB** collection (same
   engine as Day 05, the default — nothing to set up) or a real **AWS
   OpenSearch** k-NN index (the production option). This is exactly Day 04's
   `SESSION_BACKEND` single-swap-point pattern, applied to vector storage.

---

## What's in here

| File | Role |
|---|---|
| `docs/*.pdf` | Three short sample PDFs — a destination guide, a visa FAQ, a baggage policy — that form the knowledge base |
| `kb.py` | Loads PDFs page by page (with metadata), embeds them, and exposes `semantic_search()` over the configured backend |
| `backends.py` | `MemoryBackend` (ChromaDB, default) and `OpenSearchBackend` (AWS OpenSearch k-NN) — the single swap point |
| `agent.py` | `plain_agent` (no retrieval) and `root_agent` (RAG-grounded with citations, exported for `adk web`) |
| `session.py` | In-memory session factory (same single-swap-point pattern as Day 03/05) |
| `demo.py` | Four scripted scenarios + free REPL |
| `tests/test_kb.py` | Offline tests for PDF loading, metadata, and ranking (embeddings stubbed, ChromaDB runs for real) |

---

## Prerequisites

- Python 3.12+
- An [OpenRouter](https://openrouter.ai/keys) API key (used for both the chat
  model and the embedding model — same key, same provider)
- AWS credentials + a running OpenSearch domain — **only** if you want to try
  `VECTOR_BACKEND=opensearch`. The default `memory` backend needs neither.

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
| 1 | PDF ingestion + semantic search | Which PDFs were loaded, how many pages were indexed, and raw `semantic_search()` results annotated with `[source.pdf p.N]` |
| 2 | Grounded vs ungrounded | The same fictional-policy question goes to `plain_agent` and `root_agent` — one guesses, the other answers from a retrieved page |
| 3 | Citations | A question whose answer names the exact PDF and page it came from, e.g. `(tokyo-destination-guide.pdf, p.2)` |
| 4 | Honest fallback | A question none of the three PDFs cover — the grounding rules make the agent say so instead of inventing an answer |

---

## How PDF ingestion works

`kb.load_pdf_chunks()` is the whole pipeline in a few lines:

1. Glob every `*.pdf` in `docs/`.
2. Open each with `pypdf.PdfReader` and extract text **page by page**.
3. Skip blank pages; for every page with text, emit one chunk:
   `{"id": "<file-stem>-p<N>", "text": "...", "metadata": {"source": "<file>.pdf", "page": N}}`.

"One page = one chunk" is the simplest possible splitting strategy — good
enough for short reference documents like these, and it keeps the metadata
trivial to reason about: every chunk maps to exactly one page of one file. A
larger production catalog would likely also split long pages into smaller,
overlapping windows.

`kb.get_backend()` then embeds every chunk's text once (via OpenRouter,
exactly like Day 05's `embed`) and upserts `{ids, texts, embeddings,
metadatas}` into whichever backend `VECTOR_BACKEND` selects. From there,
`semantic_search(query, top_k)` embeds the query the same way and asks the
backend for the nearest chunks — each result still carrying its `metadata`,
so the caller always knows exactly where a match came from.

---

## The configurable vector backend

`backends.py` defines two implementations of one tiny interface —
`upsert(ids, texts, embeddings, metadatas)` and `query(query_embedding,
top_k)` — so `kb.py` never needs to know which vector store it's talking to:

| `VECTOR_BACKEND` | Implementation | Setup |
|---|---|---|
| `memory` (default) | `MemoryBackend` — ChromaDB `EphemeralClient`, in-process | None — what the scripted demo runs against |
| `opensearch` | `OpenSearchBackend` — managed AWS OpenSearch *domain*, k-NN plugin | `OPENSEARCH_HOST` (a `*.es.amazonaws.com` domain endpoint), `AWS_REGION`, AWS credentials |
| `opensearch-serverless` | `OpenSearchBackend` — AWS OpenSearch **Serverless** k-NN *collection* | `OPENSEARCH_HOST` (a `*.aoss.amazonaws.com` collection endpoint), `AWS_REGION`, AWS credentials with access in the collection's data-access policy |

Switching backends is a one-line change at runtime — `kb.py`, `agent.py`, and
`demo.py` are completely unaffected, because `semantic_search()` returns the
same `{"id", "text", "metadata", "score"}` shape regardless of which one is active:

```bash
# Default — nothing to configure
python demo.py

# Managed AWS OpenSearch domain
VECTOR_BACKEND=opensearch \
OPENSEARCH_HOST=search-my-domain-xxxxxxxxxxxx.us-east-1.es.amazonaws.com \
AWS_REGION=us-east-1 \
python demo.py

# AWS OpenSearch Serverless collection (see provisioning guide below)
VECTOR_BACKEND=opensearch-serverless \
OPENSEARCH_HOST=xxxxxxxxxxxxxxxxxxxx.us-east-1.aoss.amazonaws.com \
AWS_REGION=us-east-1 \
python demo.py
```

### Yes — OpenSearch Serverless is supported

`opensearch` and `opensearch-serverless` share one `OpenSearchBackend` class
— they speak the same wire protocol and the same k-NN index mapping — but
they differ in two small, very AWS-specific ways that the `serverless=`
flag handles for you:

1. **SigV4 service name.** Requests to a managed domain are signed as `es`;
   requests to a Serverless collection must be signed as `aoss`, or AWS
   rejects them with an authentication error. `OpenSearchBackend` picks the
   right one from `serverless=`.
2. **No explicit refresh, and "near-real-time" can mean minutes.** Managed
   domains accept `refresh=true` on an index request to make a document
   searchable immediately; **Serverless rejects that parameter outright**.
   Worse, its idea of "near" is loose, and the lag compounds at *two*
   levels — measured by hand against a live collection:
   - **Index visibility**: right after `_ensure_index` drops and recreates
     the index, the *search* path can keep 404'ing with "no such index"
     for a while, even though indexing requests already succeed against it.
   - **Document visibility**: once the index itself is visible, freshly
     indexed documents still took **45–60 seconds** to show up in search
     results (0/6 visible at 30s, 5/6 at 45s, 6/6 at 60s).

   A short fixed sleep would either race the index or waste time, so the
   backend instead **polls** `match_all` (tolerating 404s) until the
   expected document count actually shows up
   (`OpenSearchBackend._wait_until_searchable`, capped at 180s) — exactly
   as long as it needs to wait, no more. In practice this makes the *very
   first* `get_backend()` call after dropping and recreating the index take
   **up to several minutes** (one measured run: ~200s end to end) — that's
   normal for Serverless, not a hang. Subsequent backend creations within
   the same warm collection/index are fast; it's the drop-and-recreate
   cycle that's slow.

Authentication for both goes through `AWSV4SignerAuth` over the standard
boto3 credential chain (env vars, `~/.aws/credentials`, an instance role,
...) — no separate username/password to manage either way. `_ensure_index`
creates the k-NN index on first use if it doesn't already exist — a
`knn_vector` field sized to the embedding model's dimension, plus
`source`/`page` metadata fields (see `OpenSearchBackend._ensure_index`).

This whole arrangement mirrors Day 04's `SESSION_BACKEND` pattern almost
exactly — see `lab/demo/day04/session.py`'s `get_session_service()` for the
session-storage analogue of `backends.get_backend()`.

---

## Provisioning an OpenSearch Serverless collection from scratch

Everything below assumes you already have an AWS account and either the AWS
Console or the AWS CLI (`aws configure` already run). Unlike a managed
domain, a Serverless collection needs three **security policies** in place
*before* it will accept connections — there's no cluster to size or patch,
but AWS needs to know who can reach it, how traffic is encrypted, and who
can read/write data.

### Option A — AWS Console

1. Open **Amazon OpenSearch Service → Serverless → Security → Encryption
   policies** and create a policy that covers a collection named e.g.
   `day06-travel-docs` (you can use an AWS-owned key — no KMS setup needed
   for a demo).
2. Under **Network policies**, create one for the same collection name.
   For a demo, "Public access" for both the OpenSearch endpoint and
   dashboards is the simplest choice; for anything beyond a demo, scope it
   to a VPC instead.
3. Under **Data access policies**, create a policy that grants your IAM
   user or role `aoss:*` permissions on both the collection
   (`collection/day06-travel-docs`) and its indexes
   (`index/day06-travel-docs/*`). **This is the step people most often
   miss** — without it, the SDK authenticates fine but every request comes
   back as a 403.
4. Under **Collections**, choose **Create collection**, name it
   `day06-travel-docs`, set **Collection type** to **Vector search** (this
   is what turns on the k-NN plugin), and attach the three policies above.
5. Wait for the collection's status to become **Active**, then copy its
   **Endpoint** — it looks like
   `https://xxxxxxxxxxxxxxxxxxxx.us-east-1.aoss.amazonaws.com`. Strip the
   `https://` and that's your `OPENSEARCH_HOST`.

### Option B — AWS CLI

The same five things, as `aws opensearchserverless` calls (replace the
account ID, region, and IAM principal ARN with your own):

```bash
COLLECTION=day06-travel-docs
REGION=us-east-1
PRINCIPAL=arn:aws:iam::<ACCOUNT_ID>:user/<YOUR_IAM_USER>

# 1. Encryption policy (AWS-owned key — fine for a demo)
aws opensearchserverless create-security-policy \
  --name "${COLLECTION}-enc" --type encryption --region "$REGION" \
  --policy "{\"Rules\":[{\"ResourceType\":\"collection\",\"Resource\":[\"collection/${COLLECTION}\"]}],\"AWSOwnedKey\":true}"

# 2. Network policy (public access — scope to a VPC for anything beyond a demo)
aws opensearchserverless create-security-policy \
  --name "${COLLECTION}-net" --type network --region "$REGION" \
  --policy "[{\"Rules\":[{\"ResourceType\":\"collection\",\"Resource\":[\"collection/${COLLECTION}\"]},{\"ResourceType\":\"dashboard\",\"Resource\":[\"collection/${COLLECTION}\"]}],\"AllowFromPublic\":true}]"

# 3. Data access policy — the step that's easy to forget; without it every
#    request authenticates but comes back 403
aws opensearchserverless create-access-policy \
  --name "${COLLECTION}-access" --type data --region "$REGION" \
  --policy "[{\"Rules\":[{\"ResourceType\":\"collection\",\"Resource\":[\"collection/${COLLECTION}\"],\"Permission\":[\"aoss:*\"]},{\"ResourceType\":\"index\",\"Resource\":[\"index/${COLLECTION}/*\"],\"Permission\":[\"aoss:*\"]}],\"Principal\":[\"${PRINCIPAL}\"]}]"

# 4. The collection itself — type VECTORSEARCH is what enables k-NN
aws opensearchserverless create-collection \
  --name "$COLLECTION" --type VECTORSEARCH --region "$REGION"

# 5. Wait for it to become ACTIVE, then grab its endpoint
aws opensearchserverless batch-get-collection \
  --names "$COLLECTION" --region "$REGION" \
  --query 'collectionDetails[0].[status,collectionEndpoint]'
```

Once `status` shows `ACTIVE`, take the `collectionEndpoint`, strip the
`https://`, and wire it up:

```bash
cp .env.example .env
# In .env, set:
#   VECTOR_BACKEND=opensearch-serverless
#   OPENSEARCH_HOST=<endpoint without "https://">
#   AWS_REGION=us-east-1

python demo.py
```

The same AWS principal you put in the data-access policy must be the one
the demo authenticates as — i.e. whatever `boto3.Session().get_credentials()`
resolves to in your shell (check with `aws sts get-caller-identity`).

> **Cleaning up.** Serverless bills for OpenSearch Compute Units (OCUs) by
> the hour while the collection exists. When you're done,
> `aws opensearchserverless delete-collection --id <collection-id> --region "$REGION"`
> (and optionally delete the three policies) to stop the meter.

---

## How retrieval and citation are wired into the agent

`agent.py` defines `root_agent` with a *dynamic* instruction — an
`InstructionProvider` function (`_build_instruction`) that ADK calls fresh on
every turn, exactly like Day 05's `aria_rag`:

1. Pull the latest user message out of `ReadonlyContext.user_content`.
2. Run `kb.semantic_search(query, top_k=3)`.
3. Render each result as `(similarity=0.XX, source=<file>.pdf, p.N) <text>`.
4. Append it — and the grounding/citation rules — to the agent's persona.

The grounding rules go one step further than Day 05's: they tell the model to
**cite** each chunk it uses, inline, as `(source.pdf, p.N)`. That citation is
only possible because the `{"source", "page"}` metadata survived the entire
round trip — PDF → chunk → embedding → vector backend → retrieval →
instruction — which is the whole point of carrying metadata through a RAG
pipeline: it turns "the model said so" into "here's exactly where to verify
that."

---

## Why the documents are partly fictional

`docs/baggage-allowance-policy.pdf` describes a "TravelBot" baggage policy
that no general-purpose model could already know — the same trick Day 05
used with its cancellation-policy and loyalty-program documents. When
`root_agent` answers questions about it correctly (Scenario 2) and cites the
exact page (Scenario 3), there's only one explanation: it actually retrieved
and used that PDF page. That's what makes these scenarios checkable
demonstrations of grounding rather than the model "happening to know."

---

## Running the tests

```bash
python -m pytest tests/ -v
```

`kb.embed` is patched with a stub that returns hand-picked vectors, so no
network access or API key is required. Everything else runs for real: `pypdf`
extracts text from the actual sample PDFs in `docs/`, and the default
`MemoryBackend` indexes and searches them through a real (in-memory) ChromaDB
collection. The tests check PDF loading, `{"source", "page"}` metadata, and
ranking/top-k behavior end to end.
