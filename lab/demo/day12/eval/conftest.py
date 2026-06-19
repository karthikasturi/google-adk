"""
conftest.py — eval test setup for ADK-native evaluation.

Two jobs:
  1. Put the day12 directory on sys.path so `import agent` (and the
     eval_target shim) resolve when pytest runs from anywhere.
  2. Register an OpenRouter-backed LiteLlm so ADK's eval *judge* can be
     pointed at OpenRouter.

Why (2) is needed: the agent constructs `LiteLlm(model="openrouter/...")`
directly, but the eval judge resolves its model *string* through ADK's
LLMRegistry, and LiteLlm's built-in patterns don't include `openrouter/*`.
Registering this subclass makes `openrouter/...` resolvable — so the judge
uses the same OpenRouter key as everything else, no OpenAI key required.
This is the native equivalent of the `defaultTest.options.provider` fix in
promptfooconfig.yaml.
"""

import os
import sys

from dotenv import load_dotenv

_DAY12_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _DAY12_DIR not in sys.path:
    sys.path.insert(0, _DAY12_DIR)

load_dotenv(os.path.join(_DAY12_DIR, ".env"))

from google.adk.models.lite_llm import LiteLlm  # noqa: E402
from google.adk.models.registry import LLMRegistry  # noqa: E402


class OpenRouterLiteLlm(LiteLlm):
    """LiteLlm registered for the `openrouter/*` model namespace."""

    @staticmethod
    def supported_models() -> list[str]:
        return [r"openrouter/.*"]


LLMRegistry.register(OpenRouterLiteLlm)
