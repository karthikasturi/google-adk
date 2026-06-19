"""
serve_agent.py — host-side agent HTTP server for the Dockerised PromptFoo eval
=================================================================================
Why this exists: provider.py runs the agent *in-process*, which is perfect when
PromptFoo runs on the host (npx) and can reach the repo's Python venv. But the
official PromptFoo Docker image is Node + Alpine/musl Python with no ADK
installed, and installing google-adk there is impractical.

So for the Docker path we decouple: this tiny server runs the real ADK agent in
the host venv (where it already works), and the PromptFoo container calls it
over HTTP — no Python deps needed inside the container.

Run on the host (same venv as the rest of day12):
    cd lab/demo/day12/promptfoo
    python serve_agent.py            # listens on 0.0.0.0:8930

Then in another terminal:
    docker compose run --rm promptfoo eval

POST /eval  {"input": "..."}  → {"output": "...", "metadata": {...}}
Multiple turns can be encoded in one input separated by "\\n---\\n" (used by the
rejection-and-reflection case).
"""

import asyncio
import os
import sys

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

from agent import root_agent  # noqa: E402
from reasoning import run_turn  # noqa: E402
from session import make_runner  # noqa: E402

app = FastAPI(title="day12-travelbot-eval")


class EvalRequest(BaseModel):
    input: str


async def _run_turns(turns: list[str]) -> dict:
    runner, user_id, session_id = await make_runner(root_agent)
    result = None
    transcript = []
    for i, text in enumerate(turns):
        result = await run_turn(runner, user_id, session_id, text, i)
        transcript.append({"turn": text, "reply": result.final_text})
    return {
        "output": result.final_text if result else "",
        "metadata": {
            "transcript": transcript,
            "exit_reason": result.exit_reason if result else "",
            "tool_call_count": result.tool_call_count if result else 0,
            "is_reflection": result.is_reflection if result else False,
        },
    }


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/eval")
async def evaluate(req: EvalRequest) -> dict:
    turns = [t.strip() for t in req.input.split("\n---\n") if t.strip()]
    if not turns:
        return {"output": "", "error": "empty input"}
    return await _run_turns(turns)


if __name__ == "__main__":
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("[ERROR] OPENROUTER_API_KEY is not set — copy ../.env.example to ../.env")
        raise SystemExit(1)
    port = int(os.environ.get("AGENT_PORT", "8930"))
    print(f"TravelBot eval server on http://0.0.0.0:{port}  (POST /eval)")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
