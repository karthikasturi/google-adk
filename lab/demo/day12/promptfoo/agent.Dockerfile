# Agent server image for the Dockerised PromptFoo eval.
#
# A small Python image with just the ADK deps the agent needs. The day12 code
# (agent.py, tools.py, reasoning.py, session.py, serve_agent.py) is mounted at
# runtime (see docker-compose.yml), so editing it doesn't require a rebuild.
#
# Built automatically by `docker compose` — you don't run this directly.

FROM python:3.12-slim

# Deps for the agent + the HTTP server. Pinned to match the day12 venv.
RUN pip install --no-cache-dir \
        google-adk==2.3.0 \
        litellm==1.86.2 \
        python-dotenv==1.2.2 \
        "fastapi>=0.115" \
        "uvicorn>=0.30"

WORKDIR /day12
EXPOSE 8930

# serve_agent.py lives in promptfoo/, mounted at /day12/promptfoo
CMD ["python", "promptfoo/serve_agent.py"]
