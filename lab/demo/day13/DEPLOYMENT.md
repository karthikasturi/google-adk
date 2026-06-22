# Day 13 — Production Readiness & Azure Deployment Design

Design-level reference for Scenario 5. This is the "how do we know it's ready,
and how would we run it on Azure" discussion — deliberately at the architecture
level, not a copy-paste deploy script.

## Production readiness — what to measure before deploying

Readiness is not "the prototype answers correctly once." It's evidence across
five dimensions:

| Dimension | What "ready" looks like | How you measure it |
|---|---|---|
| **Correctness** | An eval suite gates releases; known scenarios pass at a threshold | Day 12-style eval (`AgentEvaluator` / PromptFoo): pass-rate, regression diff vs last release |
| **Observability** | Every turn is traceable end to end | Distributed tracing (OpenTelemetry → App Insights / LangSmith): per-span latency, tool calls, token counts |
| **Cost awareness** | Spend per request is known and bounded | Token + latency budgets per route; cheaper model for simple turns, capable model only when needed; alert on cost drift |
| **Security** | Untrusted input and sensitive output are controlled | The three guardrail layers below; secrets in a vault, never in code or `.env` in the image |
| **Resilience** | A bad model/tool/deploy degrades gracefully and is reversible | Health checks, timeouts, retries with backoff, circuit-breaking on tool calls, rollback-ready deploys |

A release checklist that operationalises the above:

- [ ] Eval suite green at/above threshold; results traceable to the commit
- [ ] Tracing on; a sampled trace reviewed for the critical paths
- [ ] p50/p95 latency and per-request token cost recorded and within budget
- [ ] Input guardrail, output filter, and tool-arg validation enabled and tested
- [ ] Secrets from a managed vault; no keys in the image or repo
- [ ] Health/readiness endpoints wired to the platform probes
- [ ] Rollback path verified (previous revision can take traffic immediately)
- [ ] Alerts on error rate, latency, cost, and guardrail-trigger spikes

## The three guardrail layers (from this demo)

Defence in depth — each protects a different surface, and no single one is
sufficient:

1. **Input guardrail** (`before_model_callback`) — prompt-injection and
   off-topic/policy-bypass detection; sanitise the offending clause or block.
2. **Output filter** (`after_model_callback`) — redact PII / secrets from the
   answer even if the model was coaxed into emitting them.
3. **Tool-argument validation** (`before_tool_callback`) — reject unsafe
   arguments (bulk/wildcard ids) and force confirmation for destructive
   actions, before the tool runs.

These belong in the app, not the platform — they travel with the agent across
any host.

## Azure deployment design

```
                          ┌────────────────────────────────────────┐
   client ── HTTPS ──▶    │  Azure Front Door / App Gateway (WAF)   │
                          └───────────────────┬────────────────────┘
                                              │
                          ┌───────────────────▼────────────────────┐
                          │  Azure Container Apps (or AKS)          │
                          │  ADK agent + guardrails (this demo)     │
                          │  - min replicas ≥ 2, autoscale on RPS   │
                          │  - /health + /ready probes              │
                          │  - revision-based rollout (blue/green)  │
                          └───┬───────────────┬──────────────┬──────┘
                              │               │              │
                  ┌───────────▼──┐   ┌────────▼───────┐  ┌───▼─────────────┐
                  │ Key Vault    │   │ App Insights /  │  │ OpenRouter /    │
                  │ (API keys,   │   │ OTel collector  │  │ model provider  │
                  │  secrets)    │   │ (traces/metrics)│  │ (egress only)   │
                  └──────────────┘   └─────────────────┘  └─────────────────┘
                              │
                  ┌───────────▼──────────────┐
                  │ Postgres (state/history) │   ← managed: Azure DB for
                  │ + Redis (sessions)       │     PostgreSQL / Azure Cache
                  └──────────────────────────┘
```

**Mapping each component to a readiness dimension**

- **Front Door / App Gateway (WAF)** — first-line security and TLS termination;
  rate-limiting and IP rules. The app guardrails are the second line.
- **Container Apps / AKS** — horizontal scale, revision rollouts, and
  health-probe-gated traffic. Use **Container Apps** for a managed,
  scale-to-load service; **AKS** only if you already run Kubernetes.
- **Key Vault** — all secrets (the OpenRouter key, DB creds) injected at
  runtime; nothing baked into the image. CSI driver or managed identity.
- **App Insights + OpenTelemetry** — ADK already emits OTel spans (see Day 12);
  point the OTLP exporter at the collector. This is the observability backbone.
- **Managed Postgres + Redis** — session state and audit history (Day 04
  pattern), so app instances stay stateless and replaceable.

**Rollout & rollback**

- Blue/green or canary via Container Apps revisions: send 5–10% of traffic to
  the new revision, watch error rate / latency / guardrail triggers, then ramp.
- Keep the previous revision warm so rollback is a traffic-weight change, not a
  redeploy.

**CI/CD gate**

```
build → unit tests → eval suite (threshold) → image scan → deploy canary
      → smoke + health check → ramp → full → (auto-rollback on alert)
```

The eval suite and guardrail tests are **blocking** gates — a green build that
skips them is not a release.
