"""
test_eval.py — Day 12: framework-native evaluation (ADK AgentEvaluator)
==========================================================================
The ADK-native counterpart to the promptfoo/ suite. Same five behaviours,
but scored by ADK's own evaluation framework instead of an external Node
tool:

  - cases live in travelbot.evalset.json (ADK EvalSet schema)
  - AgentEvaluator runs the real day12 agent against each case
  - final_response_match_v2 is an LLM-as-judge metric (the native parallel
    of promptfoo's `llm-rubric`), with the judge pointed at OpenRouter via
    the registration in conftest.py

Run:
    cd lab/demo/day12/eval
    python -m pytest test_eval.py -v -s

This is additive — promptfoo/ is unchanged. Needs `pip install
'google-adk[eval]'` (pulls the eval deps) and OPENROUTER_API_KEY in ../.env.
"""

import asyncio
import os
import pathlib

import pytest

from google.adk.evaluation import AgentEvaluator
from google.adk.evaluation.eval_config import EvalConfig
from google.adk.evaluation.eval_metrics import JudgeModelOptions
from google.adk.evaluation.eval_set import EvalSet
from google.adk.evaluation.final_response_match_v2 import LlmAsAJudgeCriterion

_HERE = pathlib.Path(__file__).parent
_EVALSET = _HERE / "travelbot.evalset.json"
_JUDGE_MODEL = "openrouter/google/gemini-2.5-flash"


def _eval_config() -> EvalConfig:
    """LLM-judge config — judge runs on OpenRouter (see conftest.py)."""
    return EvalConfig(
        criteria={
            "final_response_match_v2": LlmAsAJudgeCriterion(
                threshold=0.5,
                judge_model_options=JudgeModelOptions(
                    judge_model=_JUDGE_MODEL,
                    num_samples=1,
                ),
            ),
        }
    )


@pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set",
)
def test_travelbot_evalset():
    eval_set = EvalSet.model_validate_json(_EVALSET.read_text())
    asyncio.run(
        AgentEvaluator.evaluate_eval_set(
            agent_module="eval_target",
            eval_set=eval_set,
            eval_config=_eval_config(),
            num_runs=1,
            print_detailed_results=True,
        )
    )
