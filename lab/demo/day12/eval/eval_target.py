"""
eval_target.py — adapter so AgentEvaluator can load the day12 agent.

AgentEvaluator._get_agent_for_eval imports a module and expects it to either
end in `.agent` or expose an `agent` member. Importing the day12 `agent`
module here re-exports it as this module's `agent` attribute, so the eval
loader finds `eval_target.agent.root_agent`.

Swap `import agent` for `import agent_native` to evaluate the PlanReActPlanner
variant instead.
"""

import agent  # noqa: F401  (day12/agent.py, on sys.path via conftest.py)
