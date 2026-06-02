from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

_MODEL = "openrouter/google/gemini-2.5-flash"

root_agent = Agent(
    model=LiteLlm(model=_MODEL),
    name='aria',
    description='A helpful assistant for user questions.',
    instruction='Answer user questions to the best of your knowledge',
)
