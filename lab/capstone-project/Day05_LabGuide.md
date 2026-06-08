# Day 05 Lab Guide
## eComBot v3 — RAG with ChromaDB and Hallucination Guards

---

### Starting state
- eComBot v2 from Day 04 is working and testable via ADK Web.
- Redis-backed session continuity is already in place.
- PostgreSQL-backed tools and session history are already working.
- The repo already has `src/agents/`, `src/tools/`, `src/services/`, `src/config/`, and `tests/`.
- No RAG layer exists yet.

### Target state
- eComBot v3 retrieves answers from a local product catalog and FAQ knowledge base.
- ChromaDB stores embedded knowledge chunks.
- OpenAI embedding model produces embeddings for documents and user queries.
- The agent injects retrieved context before answering.
- Hallucination guards prevent unsupported answers.
- Weak or empty retrieval results trigger graceful fallback.

### Capstone alignment
This session adds the grounding layer that makes the agent trustworthy for factual product and support questions. The goal is to move from backend-backed tools to knowledge-backed answers, while keeping the same reusable architecture for later modules.

### Repository layout for this session
```text
ecombot/
├── src/
│   ├── agents/
│   │   └── support_agent.py
│   ├── rag/
│   │   ├── embed_catalog.py
│   │   └── retriever.py
│   ├── tools/
│   │   ├── order_tools.py
│   │   └── product_tools.py
│   ├── services/
│   │   ├── db.py
│   │   ├── session_service.py
│   │   └── history_service.py
│   └── config/
│       └── settings.py
├── data/
│   ├── products.json
│   └── faq.json
├── tests/
│   └── test_rag_manual.md
├── .env
├── .env.example
└── requirements.txt
```

---

## Task 1 — Add the RAG foundation

**Goal:** Create the local knowledge base structure for grounded answers.

1. Create `src/rag/`.
2. Add `embed_catalog.py` and `retriever.py`.
3. Create `data/products.json` and `data/faq.json` with realistic support content.
4. Include product specs, shipping rules, warranty notes, and support FAQ entries.

**Checkpoint:** The repo now contains the source material that will be embedded into ChromaDB.

---

## Task 2 — Build the embedding script

**Goal:** Convert the knowledge base into vector form.

1. Implement `src/rag/embed_catalog.py`.
2. Load the product and FAQ files.
3. Split content into retrievable chunks.
4. Use `OpenAI embedding model` to create embeddings.
5. Store chunks in a ChromaDB collection.

**Suggested collection name:** `ecombot_kb`

**Checkpoint:** Running the script creates or refreshes the vector store successfully.

---

## Task 3 — Build the retriever

**Goal:** Retrieve the most relevant context for each query.

1. Implement `src/rag/retriever.py`.
2. Add a `retrieve(query: str, n_results: int = 3)` function.
3. Embed the query using the same model as indexing.
4. Return the top matching chunks with their metadata.
5. Handle empty collections and retrieval failures safely.

**Checkpoint:** A test query returns meaningful chunks from the knowledge base.

---

## Task 4 — Ground the agent

**Goal:** Make the agent answer from retrieved evidence.

1. Update `src/agents/support_agent.py`.
2. Retrieve relevant chunks before generating an answer.
3. Inject the chunks into the agent prompt or context.
4. Add a grounding rule that limits answers to retrieved evidence only.
5. Keep the existing tool and session logic intact.

**Checkpoint:** The agent uses retrieved text as the basis for its response.

---

## Task 5 — Add hallucination guards

**Goal:** Prevent the agent from inventing unsupported facts.

1. Add a rule that blocks unsupported claims.
2. Add a fallback message for weak or missing retrieval.
3. Make sure the fallback is helpful, not generic.
4. Keep the user informed that the answer is not available in the current knowledge base.

**Checkpoint:** The agent refuses to guess when evidence is missing or weak.

---

## Task 6 — Build the manual test flow

**Goal:** Prove that grounding works in practice.

Create `tests/test_rag_manual.md` and test these four cases:

1. A clean match.
2. A partial match.
3. A query that should fallback.
4. A hallucination trap.

### Suggested checks
- Print retrieved chunks for each query.
- Capture the final agent response.
- Mark pass or fail for grounded behavior.

**Checkpoint:** The test notes clearly show when retrieval succeeds and when fallback fires.

---

## Task 7 — Validate in ADK Web

**Goal:** Confirm the grounded agent still works interactively.

Run ADK Web and test a few questions such as:
- `What is your baggage allowance?`
- `Do I need a visa for Dubai?`
- `Tell me about Paris in winter.`
- `What is the refund policy for missed connections?`

**Checkpoint:** The agent stays grounded and does not invent unsupported travel facts.

---

## Task 8 — Inspect failure behavior

**Goal:** Test the cases where the knowledge base is not enough.

### Required checks
- Query with no close match.
- Query with misleading keywords.
- Query with a missing document category.
- Query after deleting or emptying the collection.

### Expected behavior
- No hallucinated answer.
- Clear fallback message.
- No raw exceptions shown to the user.

**Checkpoint:** Failure behavior is safe and predictable.

---

## Task 9 — Keep the architecture clean

**Goal:** Make sure the new RAG layer remains reusable.

1. Keep retrieval logic separate from agent logic.
2. Keep embedding logic separate from retrieval logic.
3. Keep knowledge files separate from code.
4. Keep session state and history unchanged.

**Stretch goal:** Add a small script or helper to rebuild the vector store after knowledge edits.

**Checkpoint:** The RAG layer is modular and easy to reuse later.

---

## Task 10 — Production-readiness checks

**Goal:** Verify the implementation behaves like a real knowledge-grounded system.

Check the following:
- Embeddings and retrieval use the same embedding model consistently.
- ChromaDB collection can be rebuilt cleanly.
- Retrieved chunks are visible during debugging.
- The agent does not invent unsupported facts.
- Fallback is used when retrieval is weak.
- Existing Redis, PostgreSQL, and session logic still work.

**Stretch goal:** Add structured logging around retrieval and fallback events.

**Checkpoint:** The implementation is ready to support later routing, UI, and observability layers.

---

## Verification checklist
- [ ] `src/rag/embed_catalog.py` exists and indexes the knowledge base.
- [ ] `src/rag/retriever.py` returns relevant chunks.
- [ ] ChromaDB stores the embedded product and FAQ content.
- [ ] The agent injects retrieved context before answering.
- [ ] Hallucination guards block unsupported claims.
- [ ] Weak retrieval triggers graceful fallback.
- [ ] Manual test notes are saved in `tests/test_rag_manual.md`.
- [ ] ADK Web confirms grounded behavior in live chat.

---

## Stretch goal — Move toward the capstone

**Goal:** Prepare the RAG layer for future modules.

1. Keep the knowledge base structure compatible with later cloud vector storage.
2. Keep the retrieval interface simple so it can be reused by multiple agents later.
3. Keep the grounding rule explicit so it can survive prompt changes.
4. Keep the fallback behavior stable so later observability and evaluation can measure it.

**Why this matters:**
This is the first true knowledge-grounding layer in the build. It becomes the template for future retrieval, model routing, and agent decision flows.

---

## Next step
Once this lab works, the next session will extend the same grounding mindset into cloud vector storage and broader retrieval options.
