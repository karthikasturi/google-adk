# Day 11 — Real-Time Voice TravelBot

A real voice loop (no simulation) on top of the Google ADK multi-agent TravelBot:

```
microphone → STT (OpenRouter) → Google ADK agents/tools → TTS (OpenRouter) → speaker
```

One OpenRouter API key covers everything: the agent (Gemini), STT, and TTS.

## Setup

```bash
sudo apt-get install -y libportaudio2     # system audio library (Ubuntu/Debian)

cd lab/demo/day11
pip install -r requirements.txt

cp .env.example .env                     # set OPENROUTER_API_KEY=sk-or-...
```

## Run

### Validate first (no mic needed)

```bash
python selftest.py              # TTS → WAV → STT round-trip, en + fr
python selftest.py -l hi        # Hindi
python selftest.py --with-agent # also time the ADK agent
```

Synthesises a real sentence, transcribes the audio back, and prints real latency.
Run this before a live demo to confirm your key and model access.

### Live voice loop

```bash
python pipeline.py              # English (default)
python pipeline.py -l fr        # French
python pipeline.py -l hi        # Hindi
python pipeline.py --no-barge-in   # disable interruption (single-mic setups)
python pipeline.py --text          # type instead of speaking (no mic needed)
```

Just talk — VAD detects start/stop automatically. Each turn prints a latency table
showing STT / agent / TTS / mouth-to-ear times. Start talking **while TravelBot is
speaking** to trigger barge-in.

## Latency budget

Mouth-to-ear = time from end of speech to first audio out (STT + agent + TTS).

| Budget   | Verdict |
|----------|---------|
| ≤ 1500 ms | PASS (responsive) |
| ≤ 2500 ms | WARN (usable) |
| > 2500 ms | SLOW |

TTS replies sentence by sentence so first audio starts after the first sentence,
not the whole answer — this lowers perceived latency and creates natural barge-in points.

Validated on this machine: TTS `gpt-audio` ≈ 2 s, STT `gemini-2.5-flash` ≈ 1.5–2.5 s,
transcript accuracy 100% for en + fr.

## Trainer scenario map

| # | Spoken prompt | What to show |
|---|---------------|--------------|
| **1A** Basic loop | "Where is my flight from Mumbai to Dubai tomorrow?" | STT latency; short voice answer; mouth-to-ear verdict |
| **2A** STT error + confirm | "Check the status of booking A-B-one-three-seven for my hotel in Goa." | Agent repeats the ID back before the tool call; correct it → looks up AB-137 |
| **3A** Barge-in | "Explain my options if my flight is cancelled because of bad weather." → start talking: "Stop. Just tell me if I get a refund." | TTS stops; interrupting words become the next turn |
| **4A** Multi-agent journey | "Check if my flight from Delhi to Singapore is on time." → "Suggest a one-day itinerary near the airport." | Turn 1 = support tool, turn 2 = trips agent; `[route]` lines show handoffs |
| **5A** Long task | "Plan a 7-day Europe trip to Paris, Amsterdam, and Berlin with a rest day." | Spoken acknowledgment first; each sentence is interruptible |
| **6A** Noisy / clarify | (mumble the city) "Book a hotel in… Zurich." | Agent asks "did you say Zurich?" — use `--text` to force this path reliably |
| **7A/7B** Voice = thin layer | "Where is my hotel booking for Barcelona?" then "Which Barcelona hotel for a family?" | Same tools as text mode — only the I/O surface changed |

> Scenarios 2A/6A rely on real STT mistakes (non-deterministic). Use `--text` to
> reliably demo the confirm-before-acting and ask-don't-guess logic.

## Configuration

| Var | Default | Purpose |
|-----|---------|---------|
| `OPENROUTER_API_KEY` | — | required |
| `OPENROUTER_STT_MODEL` | `google/gemini-2.5-flash` | any audio-input model on OpenRouter |
| `OPENROUTER_TTS_MODEL` | `openai/gpt-audio` | `gpt-audio-mini` is cheaper but can spike to 40 s+ |
| `OPENROUTER_TTS_VOICE` | `alloy` | gpt-audio voice |
| `OPENROUTER_TTS_DEADLINE` | `45` | seconds before a slow TTS call is aborted |

## Files

```
pipeline.py       live mic → STT → ADK agents → TTS loop (barge-in, latency)
selftest.py       mic-less TTS→STT round-trip benchmark
stt_openrouter.py STT via OpenRouter audio-input model
tts_openrouter.py TTS via OpenRouter audio-output model
audio_io.py       mic capture (VAD endpointing) + interruptible playback
metrics.py        per-turn and session latency tables
agent.py          ADK concierge + trips/support/hotel specialists (voice-tuned)
tools.py          mock booking / attractions / weather / hotel tools
session.py        ADK Runner + in-memory session factory
languages.py      en / fr / hi registry
backends.py       STT/TTS engine factory
```

## Troubleshooting

- **`OPENROUTER_API_KEY is not set`** → put your key in `.env`
- **TTS: "returned no audio"** → `openai/gpt-audio` is a paid model; check credits at openrouter.ai
- **TTS: "exceeded 45s"** → model is slow/queued; raise `OPENROUTER_TTS_DEADLINE` or try `gpt-audio` (default, more stable than `gpt-audio-mini`)
- **`PortAudioError` / no device** → `sudo apt-get install libportaudio2`; use `--text` if no audio hardware
- **Barge-in fails to open mic** → run `--no-barge-in`
