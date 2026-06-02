# Day 01 + Day 02 Lab Guide

## Google ADK – eComBot v1 to v1 Refined

> Scope: This lab guide covers the first two sessions only and stays aligned with the eCommerce capstone project.

---

## Part A — Day 01: Getting Started with ADK and the First eComBot Agent

### Starting state

- Python 3.11+ installed.
- Git, VS Code, and Docker Desktop available.
- OpenRouter API key available in `.env`.
- No existing eComBot code required.

### Target state

- A working local ADK project.
- A simple eComBot support agent running successfully.
- The agent can be opened and tested in ADK Web.
- The first reply is visible and the setup is verified.

### Recommended repository structure

```text
ecombot/
├── src/
│   ├── agents/
│   │   └── support_agent.py
│   ├── config/
│   │   └── settings.py
│   └── __init__.py
├── tests/
├── .env
├── .env.example
├── requirements.txt
└── README.md
```

### Tasks

1. Create the repository structure shown above.
2. Add the required dependencies to `requirements.txt`.
3. Create a `.env.example` file for the OpenRouter key.
4. Implement a minimal `LlmAgent` for the eComBot support use case.
5. Add a small runner script to launch the agent.
6. Start ADK Web and confirm the agent appears and responds.
7. Test a few basic prompts such as order status, product discovery, and greetings.

### Checkpoints

- The project installs without errors.
- The agent starts successfully.
- ADK Web opens and shows the agent conversation.
- A normal e-commerce support question receives a relevant answer.

### Verification

- Send a simple support question.
- Confirm the agent stays on e-commerce support topic.
- Confirm the tone matches the instruction.
- Confirm the response is understandable in ADK Web.

### Stretch tasks

- Try a friendlier instruction and compare the response.
- Try a more formal instruction and compare the response.
- Save both versions of the instruction in separate text files.

---

## Part B — Day 02: Prompt Refinement, Intent Modeling, and Manual Testing

### Starting state

- Day 01 eComBot support agent is working and visible in ADK Web.
- The base project structure already exists.
- A few simple prompts have already been tested.

### Target state

- The agent instruction is refined for clearer behavior.
- Different intents are handled more consistently.
- Manual test cases are created and executed.
- The output is more predictable across similar prompts.

### Recommended repository layout for prompt variants

```text
ecombot/
├── src/
│   ├── agents/
│   │   ├── support_agent.py
│   │   ├── support_instructions_v1.txt
│   │   ├── support_instructions_v2.txt
│   │   ├── support_instructions_v3.txt
│   │   ├── product_agent.py
│   │   └── sales_agent.py
│   └── config/
│       └── settings.py
├── tests/
│   ├── test_support_agent_manual.md
│   └── test_prompt_variants.md
├── .env
├── .env.example
├── requirements.txt
└── README.md
```

### Tasks

1. Keep the base eComBot support agent in `src/agents/support_agent.py`.
2. Create separate instruction files for prompt experiments.
3. Use the same base agent code with different instructions.
4. Test greeting, empathy, clarifying question, and closing patterns.
5. Test in-scope vs out-of-scope behavior.
6. Test known vs unknown data handling.
7. Test a follow-up message that depends on previous context.
8. Record what changes in the response when the instruction changes.
9. Update the instruction if the agent answers too broadly or too vaguely.
10. Re-run the same prompt after each refinement.

### Checkpoints

- The eComBot support agent stays aligned to the electronics e-commerce domain.
- Each instruction file is isolated and easy to compare.
- The agent responds differently when the instruction changes.
- Out-of-scope queries are handled politely.
- Unknown information is not invented.
- Follow-up context works as expected.

### Verification

- Compare the reply from two instruction variants using the same user question.
- Ask an unrelated coding question and confirm the agent refuses or redirects.
- Ask for live pricing and confirm the agent avoids guessing.
- Run a two-turn exchange and confirm the second turn uses prior context.

### Stretch tasks

- Add a second version of the same instruction and compare outputs.
- Write a short manual test note for each scenario.
- Save the best-performing instruction as the current version.

---

## Review Questions

- Did the agent start cleanly in ADK Web?
- Did the instruction affect tone and scope clearly?
- Did the repo structure stay aligned with the eComBot capstone layout?
- Did the agent avoid guessing when data was missing?
- Did follow-up context behave the way you expected?
