"""
common.py -- Shared configuration and helpers for all Day 01 scenarios
-----------------------------------------------------------------------
Imported by each scenario_XX.py file.
"""

import asyncio
import logging
import os
import textwrap
import uuid

# ── Silence noisy loggers ──────────────────────────────────────────────────
# asyncio: suppresses httpx background connection-teardown noise.
logging.getLogger("asyncio").setLevel(logging.CRITICAL)

# LiteLLM: the botocore/sagemaker warnings in common_utils.py fire during
# litellm's own __init__.  Setting LITELLM_LOG via os.environ is the
# authoritative way LiteLLM checks its own log level at import time.
# We also silence the logging.Logger and disable propagation so no handler
# on the root logger can pick up the records.
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False

from dotenv import load_dotenv

load_dotenv()  # reads OPENROUTER_API_KEY from .env

import litellm

litellm.suppress_debug_info = True

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# ── Configuration ──────────────────────────────────────────────────────────
MODEL = "openrouter/google/gemini-2.5-flash"
APP_NAME = "day01-travel-demo"

# ── System prompts ─────────────────────────────────────────────────────────

FRIENDLY_SYSTEM_PROMPT = """
You are Aria, a friendly and enthusiastic AI travel assistant.
Your role is to help travelers plan trips, understand travel requirements,
and make informed decisions about flights, hotels, and itineraries.

Guidelines:
- Be warm, conversational, and encouraging.
- Provide helpful general guidance based on well-known travel knowledge.
- Do NOT invent live prices, flight schedules, or real-time availability --
  you do not have access to live data.
- If asked something outside travel, politely redirect the user.
""".strip()

FORMAL_SYSTEM_PROMPT = """
You are a professional travel advisor AI.
Your function is to provide concise, accurate travel guidance.

Guidelines:
- Use formal, professional language.
- Be brief and direct; avoid filler phrases.
- Provide authoritative general guidance based on established travel knowledge.
- Do NOT fabricate live pricing, schedules, or real-time availability data.
- Decline politely but firmly any requests outside the travel domain.
""".strip()

# ── Console helpers ────────────────────────────────────────────────────────

def divider(title: str) -> None:
    """Print a clearly visible section header."""
    width = 70
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def label(tag: str) -> None:
    """Print a sub-label (USER / AGENT)."""
    print(f"\n  [{tag}]")


def wrap(text: str, indent: int = 4) -> str:
    """Word-wrap long text for readable console output."""
    prefix = " " * indent
    return textwrap.fill(
        text, width=74, initial_indent=prefix, subsequent_indent=prefix
    )


# ── ADK helpers ────────────────────────────────────────────────────────────

def _build_message(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


async def ask(runner: Runner, user_id: str, session_id: str, question: str) -> str:
    """Send one user message and return the agent's final text reply."""
    reply_text = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=_build_message(question),
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                reply_text = event.content.parts[0].text or ""
    return reply_text.strip()


async def make_runner(system_prompt: str) -> tuple[Runner, str, str]:
    """
    Build a fresh Runner + isolated session for a given system prompt.
    Returns (runner, user_id, session_id).
    """
    session_service = InMemorySessionService()
    agent = LlmAgent(
        name="travel_assistant",
        model=LiteLlm(model=MODEL),
        instruction=system_prompt,
        description="A travel planning assistant",
    )
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    user_id = f"user-{uuid.uuid4().hex[:6]}"
    session_id = f"session-{uuid.uuid4().hex[:8]}"
    await session_service.create_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    return runner, user_id, session_id
