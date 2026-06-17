# Day 11 Lab Guide – Voice Interface (eComBot v8)

## 1. Lab overview

In this lab, you will add a **real-time voice interface** on top of your existing eComBot stack.
You will build a pipeline that turns microphone audio into text, hands that text to your existing agents and tools, and then turns the agent’s reply back into speech.

The focus is on **interaction quality**: latency, confirmations, and how voice fits into your current multi-agent and UI layers.

> Note: For language model calls, use your existing gateway (for example, LiteLLM or OpenRouter-backed endpoints) instead of any new provider-specific SDKs. Speech components (STT/TTS) can be local or cloud-based as long as they expose simple APIs.

## 2. Starting state – what you should already have

Before you start, confirm that your environment matches this starting state:

- A working **eComBot v7** with:  
  - Multi-agent orchestration (Orchestrator, Support Agent, Sales Agent).  
  - Tools and RAG integrations functioning for support and sales flows.  
  - A Chainlit UI or equivalent for text-based interactions.  
- A configured **OpenRouter-backed model endpoint** (or equivalent) that your agents already use for text conversations.  
- Basic familiarity with your audio stack (for example, how to capture microphone input and play audio output on your machine).  

If any of these pieces are missing, align your environment before continuing.

## 3. Target state – what you will build

By the end of this lab, you should have:

- A simple **voice loop** that supports:  
  - Microphone → STT → eComBot agents → TTS → speakers.  
  - At least one language (for example, English) end-to-end.  
- Voice interactions for a small set of support and sales flows (for example, order status, simple recommendations).  
- Basic handling for:  
  - Latency (responding within a reasonable time).  
  - Confirmation of critical fields (IDs, dates, amounts).  
  - Interrupting long responses by starting to speak again (even if this is a simple prototype).  

## 4. Core tasks

### Task 4.1 – Sketch the voice pipeline for your eComBot

Goal: Make the components and data flow explicit before you write code.

Steps:

1. On paper or in a short document, draw or describe your planned pipeline:  
   - How microphone audio will reach STT.  
   - How STT text will reach your Orchestrator.  
   - How the Orchestrator will call agents and tools (reusing your OpenRouter-backed model endpoint).  
   - How the agent’s textual reply will reach TTS and then your speakers.  
2. Identify what you will use for:  
   - STT (for example, a local binary, a REST API, or a library).  
   - TTS (for example, a local engine or a REST API).  
3. Decide whether you will start with **turn-based audio** (speak → wait → respond) or a simple streaming approach.

Checkpoint:

- You have a clear textual or diagrammatic description of your voice pipeline.  
- You know which components are new and which are reused (agents, tools, OpenRouter model).

---

### Task 4.2 – Implement a minimal STT → agent → TTS loop

Goal: Get a basic end-to-end voice interaction working for simple queries.

Steps:

1. Create a new module (for example, `voice_loop.py`) in a suitable directory (for example, `src/voice/`).  
2. Implement a function that:  
   - Captures a short audio segment from the microphone.  
   - Sends the audio to your chosen STT component and receives a transcript string.  
   - Passes that transcript to your existing Orchestrator entrypoint, which uses OpenRouter-backed models as usual.  
   - Sends the Orchestrator’s reply text to your TTS component and plays the resulting audio.  
3. Hard-code a simple loop (for example, press a key to record, then listen to the reply) so you can exercise the pipeline with one turn at a time.  
4. Test with simple prompts like:  
   - “Where is my order one two three four five?”  
   - “Recommend a phone under thirty thousand rupees.”  

Checkpoint:

- You can speak once, wait, and hear a spoken reply from eComBot for at least a couple of test queries.  
- The content of the reply matches what you would expect from your text-based interface.

---

### Task 4.3 – Add basic latency measurement and logging

Goal: Measure how long each part of the voice loop takes so you can improve it later.

Steps:

1. In your `voice_loop.py`, add timestamps or timers around key stages:  
   - Audio capture start/stop.  
   - STT request/response.  
   - Orchestrator request/response (OpenRouter-backed model call included).  
   - TTS request/response and audio playback start.  
2. Log these timings in a structured way (for example, as a simple JSON or clearly labeled lines).  
3. Run a few test queries and note:  
   - Total time from end of your speech to the start of the bot’s audio.  
   - Which stages dominate the latency.  
4. Decide what “good enough” looks like for this lab (for example, first audio within 1.5–2 seconds) and see how close you are.

Checkpoint:

- You have concrete timing numbers for at least three test queries.  
- You can identify which parts of the loop might need optimisation in the future.

---

### Task 4.4 – Add confirmation steps for critical fields

Goal: Reduce the impact of STT mistakes on high-stakes values like IDs and dates.

Steps:

1. Choose a support flow that uses an ID or similar critical value (for example, order ID or booking reference).  
2. Modify the Orchestrator or Support Agent logic so that when it detects such a value coming from STT, it:  
   - Generates a short confirmation prompt (“I heard order ID one two three four five, is that correct?”).  
   - Pauses further tool calls until the user confirms or corrects.  
3. In your voice loop, handle this by:  
   - Feeding the confirmation question to TTS.  
   - Capturing the user’s next utterance as a yes/no or corrected ID.  
   - Only then calling the tools and returning the final answer.  
4. Test this flow by speaking IDs clearly and unclearly, and observe how the confirmation helps avoid wrong actions.

Checkpoint:

- For the chosen flow, the system now asks for confirmation before acting on a critical value.  
- You can see a clear difference in behaviour when the user says “yes” versus when they correct the ID.

---

### Task 4.5 – Prototype simple barge-in behaviour

Goal: Let the user interrupt a long response and steer the conversation.

Steps:

1. Identify a query that makes the agent produce a longer answer (for example, a multi-day itinerary or a detailed explanation).  
2. Update your playback logic so that while TTS audio is playing, you still monitor for microphone input (even if this is a simple “press to talk” mechanism).  
3. When new speech is detected:  
   - Stop or cancel the current audio playback.  
   - Treat the new utterance as a fresh query, sending it through STT → Orchestrator → TTS.  
4. Test by asking a long question, then interrupting with a shorter follow-up like “Stop, just tell me if I get a refund.”  
5. Note any limitations of this simple implementation (for example, no automatic VAD yet) for future improvement.

Checkpoint:

- You can interrupt a long response and have the agent switch to answering the new question.  
- The behaviour, while basic, is enough to show the value of barge-in for real users.

---

### Task 4.6 – Exercise a full voice journey using existing agents

Goal: Prove that voice integrates cleanly with your multi-agent and tool stack.

Steps:

1. Define a short **support-first, then planning** journey, such as:  
   - Turn 1: Check a flight status by voice.  
   - Turn 2: Ask for a plan based on the arrival time.  
2. Run this journey entirely via your voice loop, without falling back to text UI.  
3. Watch your logs or traces to confirm that:  
   - Orchestrator, Support Agent, and Sales Agent are invoked as expected.  
   - The OpenRouter-backed model calls happen as in your text interactions.  
4. Pay attention to how the speaking style and confirmations feel when the logic crosses agent boundaries.  
5. Adjust prompts or confirmation patterns if needed to keep the conversation natural.

Checkpoint:

- You have completed at least one multi-turn, multi-agent journey entirely in voice.  
- The journey feels understandable and reasonably responsive from a user perspective.

## 5. Stretch tasks (optional)

These tasks are optional and intended for participants who finish the core lab early.

### Stretch 5.1 – Add a simple “voice trace” summary

Goal: Capture and display a compact summary of each voice interaction for debugging.

Ideas:

- For each completed turn, log a small object containing:  
  - Transcript of user speech.  
  - Agent or agents invoked.  
  - Tools called (names only).  
  - Total latency and per-stage timings.  
- Optionally expose this in a developer-only view in your existing UI or a simple CLI command.

### Stretch 5.2 – Tune speaking style for different flows

Goal: Make the agent speak differently for quick checks versus long explanations.

Ideas:

- Adjust prompts or templates so that:  
  - Support answers are short and confirmation-heavy.  
  - Planning answers are slightly longer but broken into sections.  
- Experiment with different default lengths and see how they affect perceived latency and comprehension.

## 6. Lab completion checklist

You can consider this lab complete when:

- You have a working voice loop: microphone → STT → eComBot agents (via OpenRouter-backed models) → TTS → speakers.  
- You can handle at least one support and one sales flow via voice.  
- You have basic latency measurements for the full pipeline.  
- At least one flow asks for confirmation before acting on a critical STT-derived value.  
- You can interrupt at least one long response and have the agent respond to a new question instead.  

At this point, eComBot v8 can be controlled by voice for focused scenarios, and you have the metrics and patterns you need to improve the experience further.
