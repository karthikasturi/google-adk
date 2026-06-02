"""
hello_agent.py -- Simplest possible Google ADK example
-------------------------------------------------------
Demonstrates the four core building blocks of ADK:

  1. LlmAgent   -- the agent with an instruction (system prompt) and a model
  2. Runner     -- executes the agent against a session
  3. Session    -- holds the conversation history
  4. Events     -- the streaming output from the agent

Run:
    python hello_agent.py
"""

import asyncio
import logging
import os

from dotenv import load_dotenv

# Suppress httpx background-teardown noise
logging.getLogger("asyncio").setLevel(logging.CRITICAL)

load_dotenv()  # reads OPENROUTER_API_KEY from .env

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# ── Config ─────────────────────────────────────────────────────────────────
MODEL = "openrouter/google/gemini-2.5-flash"
APP_NAME = "hello-adk"
USER_ID = "user-1"
SESSION_ID = "session-1"


async def main() -> None:
    # 1. Session storage (in-memory for demos)
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    # 2. Agent: instruction + model
    agent = LlmAgent(
        name="hello_agent",
        model=LiteLlm(model=MODEL),
        instruction="You are a helpful assistant. Answer concisely.",
    )

    # 3. Runner: wires the agent to the session service
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    # 4. Send a message and collect the response
    question = "What are the top 3 things to do in Bangalore?"
    print(f"User : {question}\n")

    user_message = types.Content(
        role="user",
        parts=[types.Part(text=question)],
    )

    response_text = ""
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=user_message,
    ):
        if event.is_final_response():
            response_text = event.content.parts[0].text or ""

    print(f"Agent: {response_text.strip()}")


if __name__ == "__main__":
    asyncio.run(main())
