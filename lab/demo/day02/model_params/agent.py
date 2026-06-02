"""
agent.py — Model Parameters Demo
==================================
Folder: model_params/

Concept:
  Shows how generation parameters (temperature, max_output_tokens, top_p,
  top_k, stop_sequences) change the model's behaviour without touching the
  instruction or the model itself.

  The parameters are set via GenerateContentConfig and passed to LlmAgent.
  Each parameter is commented to explain what it does and how to experiment
  with it in ADK Web.

ADK Web:
  Run from lab/demo/day02/:
      adk web model_params

  Suggested test:
      Ask: "Explain what temperature does and tell me a short travel tip."
      Then change a value below, restart, ask the same question, and compare.

How to experiment:
  1. Change TEMPERATURE (0.0 → 1.5) and re-run. Notice how the travel tip
     varies between runs at high temperature but stays identical at 0.0.

  2. Change MAX_OUTPUT_TOKENS (50 → 500) and re-run. Notice how a small
     limit cuts the reply mid-sentence.

  3. Change TOP_P (0.1 → 0.95) and re-run. Notice vocabulary diversity.

  4. Add a stop sequence and re-run. The reply stops at that string.
"""

from pathlib import Path

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

litellm.suppress_debug_info = True
load_dotenv()

_INSTRUCTION = (Path(__file__).parent / "instruction.txt").read_text().strip()
_MODEL = "openrouter/google/gemini-2.5-flash"

# ── Parameter knobs ────────────────────────────────────────────────────────
# Change any value here, restart `adk web model_params`, and compare.

TEMPERATURE = 0.2
# Controls randomness / creativity.
# 0.0  → fully deterministic; same prompt gives the same reply every time.
# 0.2  → low randomness; consistent, factual answers (good for support bots).
# 1.0  → moderate creativity; natural conversation.
# 1.5+ → high creativity; poetic, surprising, sometimes incoherent.
# Try: set to 1.5 and ask for a travel tip three times in separate sessions.

MAX_OUTPUT_TOKENS = 300
# Hard ceiling on reply length. One token ≈ 0.75 English words.
# 50   → a sentence or two; reply cuts off abruptly if the model needs more.
# 300  → a few paragraphs (current setting).
# 1024 → long-form answers.
# Try: set to 50 and ask a detailed question to see the truncation effect.

TOP_P = 0.9
# Nucleus sampling threshold (0.0–1.0).
# At each token step, the model considers only the smallest vocabulary subset
# whose cumulative probability ≥ top_p.
# 0.1  → very conservative; picks only the most likely words.
# 0.9  → broad vocabulary; more natural and varied phrasing (current setting).
# Works together with temperature; lower both for maximum determinism.

TOP_K = 40
# Limits the candidate pool at each step to the top-k most likely tokens.
# 1    → always picks the single most likely token (greedy decoding).
# 40   → balanced diversity (current setting; Google's recommended default).
# 100  → wide variety; risk of less coherent output at high temperature.

STOP_SEQUENCES = []
# Strings that immediately terminate generation when encountered.
# Example: ["---", "END", "\n\n\n"] stops at any of those strings.
# Try: set to [".\n"] and ask a multi-sentence question — only the first
# sentence will be returned.

# ── GenerateContentConfig ──────────────────────────────────────────────────
# Bundles all generation parameters into one config object for LlmAgent.
_gen_config = types.GenerateContentConfig(
    temperature=TEMPERATURE,
    max_output_tokens=MAX_OUTPUT_TOKENS,
    top_p=TOP_P,
    top_k=TOP_K,
    stop_sequences=STOP_SEQUENCES if STOP_SEQUENCES else None,
)

# ── Agent ──────────────────────────────────────────────────────────────────
root_agent = LlmAgent(
    name="model_params_agent",
    model=LiteLlm(model=_MODEL),
    instruction=_INSTRUCTION,
    description="A teaching agent that demonstrates LLM generation parameters",
    # generate_content_config passes the knobs above to the model at inference.
    generate_content_config=_gen_config,
)
