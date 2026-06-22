"""
guardrails.py — Day 13: reusable ADK guardrails (the actual teaching point)
=============================================================================
Three independent layers, each a standard ADK callback. They are deliberately
separate because they defend different surfaces:

  1. INPUT guardrail  → before_model_callback
        Catches prompt injection and off-topic / policy-bypass asks in the
        user's message and *sanitises* them (drops the offending clause)
        before the model ever sees them. If nothing safe is left, it blocks.

  2. OUTPUT guardrail  → after_model_callback
        Scans the model's answer for PII (email / phone / account id) and
        redacts it before it reaches the user.

  3. TOOL guardrail    → before_tool_callback
        Validates tool arguments before the tool runs: rejects unsafe values
        (e.g. order_id=all) and forces confirmation for destructive actions.

Each guardrail records what it did into session state under "guardrail_events"
so the demo / Chainlit UI can show a clear "intercepted" indicator.

These are detection heuristics for teaching, not a production WAF — the README
is explicit about that.
"""

import re
from typing import Callable, Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

# ── Pattern banks ───────────────────────────────────────────────────────────

INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior|earlier|above) instructions",
    r"disregard (all )?(previous|prior|earlier|above) (instructions|prompts)",
    r"system prompt",
    r"reveal (your )?(instructions|system prompt|prompt|rules)",
    r"show me your (system )?(prompt|instructions)",
    r"internal policy",
    r"developer (message|prompt)",
]

SCOPE_PATTERNS = [
    r"bypass .*(policy|policies|rules|restrictions)",
    r"(reveal|show|leak) .*(admin|private|confidential|internal) (notes|data|info)",
    r"admin notes",
    r"override .*(policy|safety|guardrail)",
]

_PII = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone": re.compile(r"\+?\d[\d\s().-]{7,}\d"),
    "account id": re.compile(r"\b(?:ACC|ACCT|ACC-)[\s#:-]*\d{3,}\b", re.I),
}

_CLAUSE_SPLIT = re.compile(r"([.!?;\n,]+)")

# Connective fragments left behind after a clause is removed ("Also, …", "…, but
# also …") — dropped so the sanitised request reads cleanly.
_ORPHAN = re.compile(
    r"^(also|and|but|or|so|then|still|please|if you can'?t do that|"
    r"and don'?t ask me again|don'?t ask me again)$",
    re.I,
)


# ── State helper ────────────────────────────────────────────────────────────

def _record(state, guardrail: str, action: str, detail: str) -> None:
    """Append a guardrail event to session state (read-modify-write so the
    change is tracked and persisted). De-duplicates identical events, since
    before_model_callback fires again on each model turn of the same request."""
    events = list(state.get("guardrail_events", []))
    record = {"guardrail": guardrail, "action": action, "detail": detail}
    if record in events:
        return
    events.append(record)
    state["guardrail_events"] = events


def _matches(text: str, patterns: list[str]) -> list[str]:
    hits = []
    for p in patterns:
        if re.search(p, text, re.I):
            hits.append(p)
    return hits


def _sanitise(text: str, patterns: list[str]) -> tuple[str, list[str]]:
    """Drop clauses matching any pattern; return (cleaned_text, removed_clauses)."""
    tokens = _CLAUSE_SPLIT.split(text)
    kept, removed = [], []
    i = 0
    while i < len(tokens):
        clause = tokens[i]
        delim = tokens[i + 1] if i + 1 < len(tokens) else ""
        stripped = clause.strip()
        if stripped and _matches(clause, patterns):
            removed.append(stripped)          # unsafe → drop (and report)
        elif stripped and _ORPHAN.match(stripped):
            pass                               # leftover connective → drop silently
        else:
            kept.append(clause + delim)
        i += 2
    return "".join(kept).strip(), removed


# ── 1. INPUT guardrail (before_model_callback) ──────────────────────────────

def make_input_guardrail(label: str, patterns: list[str]) -> Callable:
    """Build a before_model_callback that sanitises matching clauses out of the
    latest user message. Blocks entirely only if nothing safe remains."""

    def guardrail(callback_context: CallbackContext,
                  llm_request: LlmRequest) -> Optional[LlmResponse]:
        removed_all: list[str] = []
        last_user_emptied = False

        for content in llm_request.contents or []:
            if content.role != "user" or not content.parts:
                continue
            for part in content.parts:
                if not getattr(part, "text", None):
                    continue
                cleaned, removed = _sanitise(part.text, patterns)
                if removed:
                    removed_all.extend(removed)
                    part.text = cleaned or "[request removed by guardrail]"
                    last_user_emptied = not cleaned

        if not removed_all:
            return None  # nothing to do — let the model run normally

        if last_user_emptied:
            _record(callback_context.state, label, "blocked",
                    f"entire request matched {label}; nothing safe to forward")
            return LlmResponse(content=types.Content(
                role="model",
                parts=[types.Part(text=(
                    "I can't help with that request, but I'm happy to help with "
                    "a genuine request in my area."))]))

        _record(callback_context.state, label, "sanitised",
                f"removed {len(removed_all)} clause(s): {removed_all}")
        return None  # proceed with the cleaned request

    return guardrail


# Ready-made instances for the demo agents.
injection_guardrail = make_input_guardrail("input:injection", INJECTION_PATTERNS)
scope_guardrail = make_input_guardrail("input:scope", SCOPE_PATTERNS)


# ── 2. OUTPUT guardrail (after_model_callback) — PII redaction ───────────────

def output_pii_guardrail(callback_context: CallbackContext,
                         llm_response: LlmResponse) -> Optional[LlmResponse]:
    if getattr(llm_response, "partial", False):
        return None
    if not llm_response.content or not llm_response.content.parts:
        return None

    found: list[str] = []
    changed = False
    for part in llm_response.content.parts:
        text = getattr(part, "text", None)
        if not text:
            continue
        new_text = text
        for kind, rx in _PII.items():
            if rx.search(new_text):
                found.append(kind)
                new_text = rx.sub(f"[REDACTED {kind.upper()}]", new_text)
        if new_text != text:
            part.text = new_text
            changed = True

    if not changed:
        return None

    _record(callback_context.state, "output:pii", "redacted",
            f"masked: {sorted(set(found))}")
    return llm_response


# ── 3. TOOL guardrail (before_tool_callback) — argument safety ───────────────

_SAFE_ORDER_ID = re.compile(r"^#?\d{4,6}$")
_DESTRUCTIVE_TOOLS = {"cancel_order"}


def tool_safety_guardrail(tool: BaseTool, args: dict,
                          tool_context: ToolContext) -> Optional[dict]:
    if tool.name == "cancel_order":
        order_id = str(args.get("order_id", "")).strip()

        # Reject unsafe / bulk identifiers before the tool ever runs.
        if not _SAFE_ORDER_ID.match(order_id):
            _record(tool_context.state, "tool:cancel_order", "blocked",
                    f"unsafe order_id '{order_id}' rejected before tool call")
            return {"status": "blocked",
                    "reason": f"'{order_id}' is not a valid single order id. "
                              "Bulk or wildcard cancellation is not allowed."}

        # Destructive action → require explicit confirmation. We do NOT trust a
        # model-supplied confirmed=True: confirmation must come from the user,
        # tracked in session state across turns. First attempt always asks.
        oid = order_id.lstrip("#")
        confirm_key = f"cancel_confirmed_{oid}"
        if not tool_context.state.get(confirm_key):
            tool_context.state[confirm_key] = "pending"
            _record(tool_context.state, "tool:cancel_order", "confirmation_required",
                    f"destructive cancel of {oid} blocked pending user confirmation "
                    "(model-supplied confirmed flag ignored)")
            return {"status": "confirmation_required", "order_id": oid,
                    "message": f"Please confirm: cancel order {oid}? This cannot be undone."}

    return None  # safe — allow the tool to run
