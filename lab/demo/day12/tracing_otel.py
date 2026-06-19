"""
tracing_otel.py — Day 12: framework-native observability (OpenTelemetry → LangSmith)
=======================================================================================
The ADK-native counterpart to tracing.py.

tracing.py rebuilds a trace tree by hand with langsmith.Client.create_run().
ADK already instruments itself with OpenTelemetry: the Runner emits a span
for every LLM call and every tool call (see google.adk.telemetry). So instead
of re-creating runs, we just install an OTLP exporter pointing at LangSmith's
OpenTelemetry ingest endpoint, and ADK's own spans — with token counts and
latency — show up in LangSmith automatically.

Call setup_langsmith_otel() ONCE before running the agent. No per-turn code,
no manual spans. No-op (returns None) if LANGSMITH_API_KEY is unset or the
OTel packages aren't installed, so callers don't need to guard.

LangSmith OTel docs: https://docs.smith.langchain.com/observability/how_to_guides/trace_with_opentelemetry
"""

import os

_provider = None


def setup_langsmith_otel():
    """Route ADK's built-in OpenTelemetry spans to LangSmith. Idempotent.

    Returns the TracerProvider, or None if not configured / unavailable.
    """
    global _provider
    if _provider is not None:
        return _provider

    api_key = os.environ.get("LANGSMITH_API_KEY")
    if not api_key:
        return None

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return None

    # LangSmith's OTel endpoint = the API base + "/otel". Honour the regional
    # endpoint (e.g. APAC) if the user set LANGSMITH_ENDPOINT, else default US.
    base = os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com").rstrip("/")
    if base.endswith("/otel"):
        otel_base = base
    else:
        otel_base = f"{base}/otel"
    project = os.environ.get("LANGSMITH_PROJECT", "day12-travelbot")

    exporter = OTLPSpanExporter(
        endpoint=f"{otel_base}/v1/traces",
        headers={"x-api-key": api_key, "Langsmith-Project": project},
    )

    provider = TracerProvider(
        resource=Resource.create({"service.name": project})
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _provider = provider
    return provider


def shutdown_otel() -> None:
    """Flush any buffered spans to LangSmith. Call before the process exits."""
    if _provider is not None:
        _provider.shutdown()
