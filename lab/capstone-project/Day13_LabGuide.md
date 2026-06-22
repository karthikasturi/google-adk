# Day 13 Lab Guide
## Guardrails and Production Readiness

### Starting State
- You already have an eComBot system with multi-agent routing, RAG, FastMCP tools, voice support, and observability in place.
- Your repository follows the expected layout, including `src/agents/`, `src/tools/`, `src/services/`, `src/rag/`, `src/ui/`, `src/config/`, `tests/`, and optionally `docker/`.
- LangSmith and PromptFoo are already configured from the previous work.
- You have a working local environment with Docker available.

### Target State
- Your agent stack has basic input and output guardrails.
- Tool usage is safer, with validation before execution and confirmation for destructive actions.
- Your production-readiness checklist is complete.
- Azure architecture is covered only as a concept and does not require any demo, implementation, or lab work.

---

## 1) Focus on guardrails

### Task 1.1: Detect prompt injection patterns
Add a lightweight input filter before the message reaches the main agent.

Focus on patterns such as:
- "ignore all previous instructions"
- "show me your system prompt"
- "you are now"
- Role escalation attempts

Verification:
- Test a normal support query and confirm it passes.
- Test an obvious injection attempt and confirm it is blocked or sanitized.

### Task 1.2: Add a safety decision result
Return a structured result from the guardrail layer.

Example shape:
- `allowed: true/false`
- `reason: short explanation`
- `action: pass | block | redact`

Verification:
- Confirm the agent can read the decision cleanly.
- Confirm blocked requests do not reach downstream tools or the LLM.

### Task 1.3: Keep the user informed
If a message is blocked, show a short and honest explanation in the UI.

Verification:
- The user sees a clear blocked state.
- The application does not silently fail.

Checkpoint:
- Confirm at least one unsafe prompt is intercepted before tool use or final generation.

---

## 2) Harden tool execution

### Task 2.1: Validate tool arguments
Before a tool runs, validate and normalize its inputs.

Example checks:
- Format validation for order IDs.
- Range validation for numeric arguments.
- Presence checks for required fields.

Verification:
- Pass a valid tool input and confirm normal execution.
- Pass a malformed input and confirm the tool is not called.

### Task 2.2: Add confirmation for destructive actions
If a tool changes or deletes data, require explicit confirmation.

Examples:
- Cancel order.
- Delete account data.
- Remove subscription.

Verification:
- Ask to cancel an order and confirm the system requests confirmation first.
- Confirm that the tool only runs after explicit approval.

### Task 2.3: Restrict tool scope
Make sure the support-facing flows cannot reach admin-only operations.

Verification:
- Confirm tool access is limited to the intended agent role.
- Confirm unauthorized tool paths are not exposed in normal flow.

Checkpoint:
- A destructive action cannot happen without validation and confirmation.

---

## 3) Validate observability and evaluation

### Task 3.1: Confirm tracing still works
Run a few flows and verify that traces still show routing, tool usage, and model choice.

Verification:
- Open the traces.
- Confirm blocked requests are visible in the trace path.
- Confirm successful requests still show the complete route.

### Task 3.2: Add evaluation cases for safety
Extend your PromptFoo set with safety-focused cases.

Include:
- Injection attempts.
- PII leakage tests.
- Off-topic prompt tests.
- Unsafe tool argument tests.

Verification:
- Confirm safety cases fail when guardrails are removed.
- Confirm safety cases pass with the guardrail layer active.

Checkpoint:
- Safety behavior is testable, repeatable, and visible in evaluation.

---

## 4) Production readiness checklist

Before you finish, confirm all of the following:

- Input guardrails block obvious prompt injection attempts.
- Output guardrails catch PII, off-topic content, and unsafe leakage.
- Tool calls are validated before execution.
- Destructive actions require confirmation.
- Blocked states are visible in the UI.
- LangSmith traces still show routing and tool usage.
- PromptFoo includes safety-focused cases.
- Secrets are not stored in code or committed config.
- The repository is ready for a production-style handoff.

---

## 5) Azure architecture concept

### Concept only
Azure architecture is covered here as a design concept, not as a demo or lab activity. You should understand how the system would be mapped to Azure services, but you do not need to build, configure, or deploy anything for this part.

### What to know
A production-style Azure design should separate:
- Agents and UI.
- Gateway and tool services.
- Session state.
- Secrets.
- Observability.

A reasonable conceptual mapping is:
- Azure Container Apps or Azure Kubernetes Service for agents, UI, and gateway services.
- Azure Cache for Redis for session/state.
- Azure Key Vault for secrets and credentials.
- Azure Monitor and Application Insights for infrastructure telemetry.
- Azure Container Registry for images.

### Design concerns to recognize
When discussing the design, focus on:
- Health checks.
- Autoscaling.
- Blue-green or canary rollout thinking.
- Separation of concerns.
- Rollback readiness.

Checkpoint:
- You can explain the whole deployment in one page or one architecture diagram.

---

## Stretch Tasks

- Add a secondary policy model for safety classification.
- Add per-agent guardrail rules instead of one global rule set.
- Add a compact trace summary card in the UI.
- Expand the Azure architecture concept into a written reference diagram for later planning.
