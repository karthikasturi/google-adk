# Reference & Future Learning Guide — Google ADK / Agentic AI

Companion to `course-outline/Google-ADK-Course-Outline.pdf`. This course (M1–M11 +
Capstone) builds one working system, eComBot, end to end. This doc is deliberately
**not** another tutorial — it's a topic list and roadmap for what to learn *next*,
once the fundamentals from this course are solid.

---

## 1. What this course already covered

| Module | Concept | eComBot state |
|---|---|---|
| M1 | Agent concepts, lifecycle, ADK Web | v1 — basic agent |
| M2 | Tool calling, structured output, session state | v2 — stateful, tool-using |
| M3 | RAG — embeddings, ChromaDB, hallucination guard | v3 — knowledge-grounded |
| M4 | LiteLLM routing, cost-aware fallback | v4 — multi-model |
| M5 | MCP tool servers via FastMCP | v5 — externally connected |
| M6 | Multi-agent (Planner–Executor / Orchestrator) | v6 — multi-agent |
| M7 | Generative UI (Gradio) | v7 — UI layer |
| M8 | Voice AI — STT → agent → TTS | v8 — voice-enabled |
| M9 | ReAct / reflection reasoning loops | v9 — reasoning |
| M10 | Observability — LangSmith, PromptFoo evals | v10 — observable |
| M11 | Guardrails — injection defence, output filtering | v11 — hardened |
| Capstone | CI/CD, deployment | shipped |

Everything below assumes this baseline and points at what's beyond it.

---

## 2. Production perspective — what changes beyond the course

The course builds a *correct* agent. Production requires it to also be
*reliable, scalable, governed, and observable under real load*. Topics only —
each is a rabbit hole worth its own follow-up session.

### Reliability
- Retries, timeouts, and circuit breakers on every external call (tool APIs, MCP
  servers, model providers) — M4's LiteLLM fallback is the seed of this, taken
  further with per-dependency circuit breakers
- Idempotent tool calls (safe to retry `cancel_booking` without double-cancelling)
- Graceful degradation — partial answers when a tool/model is down, not a hard fail
- Health checks + readiness probes for every service in the pipeline (agent, MCP
  servers, vector DB, session store)
- Chaos testing — kill a dependency mid-conversation, verify recovery

### Scalability
- Stateless agent runtimes so requests can be load-balanced across replicas
- Session/state store scaling — Redis Cluster / managed session services instead
  of a single instance (M2/M4 used single-node Redis)
- Async / queue-based execution for long-running agent tasks (don't hold an HTTP
  connection open for a 2-minute multi-tool chain)
- Vector DB scaling — sharding, managed vector stores (Vertex AI Vector Search,
  Pinecone, etc.) vs local ChromaDB from M3
- Rate-limit-aware request shaping — backpressure, queuing, token-bucket clients
  per model provider
- Load testing agentic flows specifically (latency compounds across tool calls +
  multi-agent hops, unlike a single API request)

### Cost governance
- Token budgets per session/user/tenant, not just per-call
- Semantic caching (skip the LLM call entirely for near-duplicate queries)
- Prompt caching (provider-level, e.g. Gemini context caching)
- Model cascades — cheap model first, escalate only on low confidence

### Security & compliance
- Secrets management (Secret Manager / Vault, not `.env` files)
- Tool execution sandboxing — least-privilege scopes per tool, no raw shell/DB access
- MCP server supply-chain risk — vetting third-party MCP servers before granting tool access
- PII handling, data residency, audit trails, right-to-be-forgotten for session/memory stores
- Red-teaming agents specifically (prompt injection, tool-abuse, jailbreaks) — M11 is the entry point, not the ceiling

### Observability maturity
- Distributed tracing across agent → tool → sub-agent hops (OpenTelemetry GenAI
  semantic conventions), not just LangSmith traces per call
- Alerting + SLOs/error budgets on latency, cost, and hallucination rate — not just logging
- Continuous eval in production (shadow traffic, canary agents) vs one-off PromptFoo runs

### Testing & release maturity
- Golden datasets + regression suites for agent behaviour (prompt/model changes shouldn't silently regress)
- Canary releases and shadow deployments for new agent versions
- LLM-as-judge pipelines for response quality at scale

### Deployment targets
- Vertex AI Agent Engine — managed agent runtime with built-in autoscaling, sessions, and Memory Bank
- Cloud Run / GKE — containerized ADK agents (this course's Docker patterns extend directly)
- Vertex AI Agent Builder — for enterprise agent governance and tool cataloguing

---

## 3. Advanced ADK & agentic AI concepts to learn next

### Agent-to-Agent interoperability (A2A)
The Agent2Agent protocol standardizes how independent agents (possibly built by
different teams, in different frameworks) discover and delegate to each other over
HTTP/JSON-RPC — complementary to MCP (MCP = agent-to-tool, A2A = agent-to-agent).
- Agent Cards (`/.well-known/agent-card.json`) — public capability discovery
- `RemoteA2aAgent` in ADK — consume a remote agent as if it were local
- Exposing an ADK agent as an A2A server for other teams/frameworks to call
- Auth between agents (OAuth 2.0) and task lifecycle (structured, bidirectional, resumable)
- Compare to this course's M6 orchestration, which is single-process/in-framework only

### Agent Skills
A packaging model for agent capabilities, distinct from tools — solves "instruction
bloat" when an agent has 10+ specialised behaviours.
- Progressive disclosure: L1 metadata (name+description, cheap) → L2 instructions
  (loaded only when triggered) → L3 resources (reference docs, scripts)
- Inline skills (small, in-code) vs directory-based skills (`SKILL.md` + assets)
- Skill discovery via Agent Cards — how a skill becomes part of what other agents can see

### Memory layers beyond session state
This course's session state (M2) is short-lived working memory. Long-term memory
is a distinct, larger topic:
- Working vs episodic vs semantic/long-term memory — different retention and retrieval needs
- `VertexAiMemoryBankService` — managed, Gemini-extracted facts/preferences across sessions
- Preload memory (auto-injected each turn) vs load memory (agent decides when to fetch)
- Third-party memory frameworks worth knowing: Mem0, Zep, LangMem
- When memory beats RAG (personalization, "remember me") vs when RAG is still right (shared knowledge base)

### Advanced multi-agent orchestration patterns
Beyond this course's Planner–Executor/Orchestrator:
- Hierarchical delegation (manager-of-managers) at larger agent counts
- Swarm / decentralized agent coordination (no single orchestrator)
- Blackboard pattern — agents read/write shared state instead of direct delegation
- Event-driven / pub-sub agents — reactive instead of request/response
- Human-in-the-loop approval gates for high-risk actions (refunds, cancellations)

### Durable / long-running agents
- Checkpointing and resuming an agent workflow after a crash or timeout
- Async execution for multi-hour or multi-day agent tasks
- Workflow engines paired with agents (Temporal, Cloud Workflows) for durable execution

### Advanced retrieval
This course's M3 is single-hop vector RAG. Next steps:
- Agentic RAG — the agent decides *whether*, *when*, and *what* to retrieve, not a fixed pipeline
- Multi-hop retrieval — chain multiple retrieval steps for compound questions
- Hybrid search — keyword (BM25) + vector, then rerank
- GraphRAG — knowledge-graph-backed retrieval for relationship-heavy domains

### Multi-modal agents
- Vision — image/document understanding as tool input, not just text
- Video understanding and generation as agent capabilities
- Extending M8's voice pipeline to full multi-modal (image + voice + text) turns

### Advanced model routing & cost optimization
Beyond M4's primary/fallback routing:
- Confidence-based model cascades (escalate only when the cheap model is unsure)
- Semantic + prompt caching layered under the router
- Multi-provider load balancing for both cost *and* latency SLOs

### Evaluation & guardrail maturity
Beyond M10/M11:
- LLM-as-judge eval pipelines, not just PromptFoo's static assertions
- Guardrail frameworks to evaluate: NeMo Guardrails, Llama Guard, Microsoft Presidio (PII)
- Continuous/production evaluation, not just pre-release test suites

### Standards & ecosystem landscape
Context worth having even if not hands-on yet:
- MCP vs A2A vs plain function calling — what each solves, where they overlap
- Other agent frameworks for comparison: LangGraph, CrewAI, AutoGen, Semantic Kernel
- Where ADK sits in Google's stack: ADK (build) → Agent Engine (run) → Agent Builder (govern)

---

## 4. Suggested roadmap

**Stage 1 — Harden what you built (2–3 weeks)**
Reliability + scalability topics from Section 2, applied to the capstone eComBot:
add circuit breakers, make the agent runtime stateless, load-test the multi-agent
flow, move session storage to a clustered/managed store.

**Stage 2 — Interoperability (2–3 weeks)**
A2A protocol end to end: expose one eComBot sub-agent as an A2A server, consume
it from a separate ADK project via `RemoteA2aAgent`. Then try Agent Skills to
replace one sub-agent's bloated instruction block.

**Stage 3 — Memory & retrieval (2–3 weeks)**
Add `VertexAiMemoryBankService` (or Mem0/Zep) for cross-session personalization.
Upgrade M3's RAG to agentic RAG — let the agent decide when to retrieve instead
of always retrieving.

**Stage 4 — Production operations (ongoing)**
Observability maturity (OTel tracing, SLOs), continuous eval in production,
canary releases, cost governance (caching + cascades). Deploy the capstone to
Vertex AI Agent Engine or Cloud Run and put real monitoring behind it.

**Stage 5 — Frontier topics (as needed)**
Multi-modal agents, durable/long-running workflows, GraphRAG, decentralized
multi-agent patterns — pull these in when a real use case demands them rather
than pre-emptively.

---

## 5. Curated resources

- ADK docs: https://google.github.io/adk-docs/
- A2A protocol: https://a2a-protocol.org/
- MCP spec: https://modelcontextprotocol.io/
- Vertex AI Agent Engine / Memory Bank: https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview
- ADK Skills guide: https://developers.googleblog.com/developers-guide-to-building-adk-agents-with-skills/
- OpenTelemetry GenAI semantic conventions: https://opentelemetry.io/docs/specs/semconv/gen-ai/
