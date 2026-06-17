"""
pipeline.py — Day 11: Real-time voice TravelBot
================================================
End-to-end pipeline, no simulation:

    microphone → STT (OpenRouter) → ADK agents/tools → TTS (OpenRouter) → speaker

Scenarios covered:
  1A  Basic voice loop + latency table
  2A  STT error → agent confirms booking ID before acting
  3A  Barge-in: speak over TravelBot to interrupt playback
  4A  Multi-agent journey (support → trips handoff shown in [route] lines)
  5A  Long task: spoken sentence-by-sentence, each sentence interruptible
  6A  Noisy/unclear input → agent asks instead of guessing
  7A  Voice as thin layer: same tools as text mode, only I/O differs

Run
    python pipeline.py              # English (default)
    python pipeline.py -l fr        # French
    python pipeline.py -l hi        # Hindi
    python pipeline.py --no-barge-in
    python pipeline.py --text       # type instead of speaking (no mic needed)

Prereqs
    pip install -r requirements.txt
    cp .env.example .env            # set OPENROUTER_API_KEY
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time

from dotenv import load_dotenv
load_dotenv()

from google.genai import types

from agent import concierge_agent
from audio_io import AudioIO
from languages import LANGUAGES, get_language
from metrics import MetricsLog, TurnMetrics, print_turn
from session import make_runner
from stt_openrouter import OpenRouterSTT
from tts_openrouter import OpenRouterTTS

_C = {
    "b": "\033[1m", "cyan": "\033[36m", "green": "\033[32m",
    "yellow": "\033[33m", "dim": "\033[90m", "x": "\033[0m",
}


# ── Agent ─────────────────────────────────────────────────────────────────────

async def ask_agent(runner, uid, sid, text: str) -> tuple[str, str, int]:
    """Send one turn to the ADK agent. Returns (reply, author, elapsed_ms)."""
    t0 = time.perf_counter()
    reply = ""
    author = ""
    async for event in runner.run_async(
        user_id=uid, session_id=sid,
        new_message=types.Content(role="user", parts=[types.Part(text=text)]),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                fc = getattr(part, "function_call", None)
                if fc:
                    if fc.name == "transfer_to_agent":
                        dest = dict(fc.args or {}).get("agent_name", "specialist")
                        print(f"  {_C['dim']}[route] {event.author} → {dest}{_C['x']}")
                    else:
                        args = ", ".join(f"{k}={v!r}" for k, v in (fc.args or {}).items())
                        print(f"  {_C['dim']}[tool]  {fc.name}({args}){_C['x']}")
        if event.is_final_response() and event.content and event.content.parts:
            t = event.content.parts[0].text
            if t:
                reply, author = t.strip(), event.author
    return reply, author, int((time.perf_counter() - t0) * 1000)


# ── Voice loop ────────────────────────────────────────────────────────────────

async def run_voice_loop(lang_key: str, allow_barge_in: bool, text_mode: bool) -> None:
    lang = get_language(lang_key)
    stt = OpenRouterSTT()
    tts = OpenRouterTTS()
    audio = None if text_mode else AudioIO()

    print(f"\n{'=' * 65}")
    print(f"{_C['b']}{_C['cyan']}Day 11 — Voice TravelBot  [{lang.name}]{_C['x']}")
    print(f"{_C['dim']}mic → OpenRouter STT → Google ADK → OpenRouter TTS → speaker{_C['x']}")
    print(f"{'=' * 65}")

    runner, uid, sid = await make_runner(concierge_agent)
    metrics = MetricsLog()

    # Greeting
    print(f"\n{_C['green']}TravelBot:{_C['x']} {lang.greeting}")
    if audio:
        audio.speak(tts.iter_pcm(lang.greeting), tts.sample_rate, allow_barge_in=False)
    print(f"\n{_C['dim']}Try: {lang.sample_prompts[0]}{_C['x']}\n")

    pending_audio = None   # barge-in utterance carried into the next turn
    try:
        while True:
            # 1. Capture user input
            if text_mode:
                try:
                    text = input(f"{_C['b']}You (type):{_C['x']} ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if text.lower() in ("quit", "exit", "q"):
                    break
                if not text:
                    continue
                stt_ms, conf = 0, 1.0
            else:
                utt = pending_audio or audio.listen_utterance()
                pending_audio = None
                print(f"{_C['dim']}🎙  listening…{_C['x']}")
                tr = stt.transcribe(utt.audio, language=lang.lang_code)
                text, stt_ms, conf = tr.text, tr.latency_ms, tr.confidence
                if not text:
                    print(f"{_C['yellow']}…didn't catch that, please repeat.{_C['x']}")
                    continue
                note = "  ⚠ low confidence" if conf < 0.6 else ""
                print(f"{_C['b']}You said:{_C['x']} \"{text}\"  "
                      f"{_C['dim']}(stt {stt_ms}ms, conf {conf:.2f}){note}{_C['x']}")

            # 2. Agent
            print(f"{_C['dim']}…thinking…{_C['x']}")
            reply, author, agent_ms = await ask_agent(runner, uid, sid, text)
            if not reply:
                reply = "Sorry, I didn't get a response. Please try again."
            print(f"{_C['green']}TravelBot ({author}):{_C['x']} {reply}")

            # 3. Speak — sentence by sentence so barge-in can interrupt early
            tts_ttfb_ms = 0
            interrupted = False
            if audio:
                sentences = re.split(r"(?<=[.!?。！？])\s+", reply.strip())
                t0_speak = time.perf_counter()
                first_audio_t = None
                for sentence in [s.strip() for s in sentences if s.strip()]:
                    done, ttfb, barge = audio.speak(
                        tts.iter_pcm(sentence), tts.sample_rate,
                        allow_barge_in=allow_barge_in,
                    )
                    if first_audio_t is None and ttfb is not None:
                        first_audio_t = t0_speak + ttfb
                    if not done and barge is not None:
                        print(f"  {_C['yellow']}[barge-in — stopping]{_C['x']}")
                        pending_audio = barge
                        interrupted = True
                        break
                if first_audio_t is not None:
                    tts_ttfb_ms = int((first_audio_t - t0_speak) * 1000)

            # 4. Latency table
            m = TurnMetrics(
                stt_ms=stt_ms, agent_ms=agent_ms, tts_ttfb_ms=tts_ttfb_ms,
                speech_to_first_audio_ms=stt_ms + agent_ms + tts_ttfb_ms,
                transcript=text, confidence=conf,
            )
            metrics.add(m)
            print_turn(m)
            if interrupted:
                print(f"  {_C['dim']}(next turn = your interruption){_C['x']}")
            print()
    except KeyboardInterrupt:
        pass
    finally:
        metrics.summary()
        print("\nGoodbye!")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Day 11 real-time voice TravelBot")
    ap.add_argument("-l", "--lang", default="en", help="en (default) | fr | hi")
    ap.add_argument("--list-langs", action="store_true")
    ap.add_argument("--no-barge-in", action="store_true")
    ap.add_argument("--text", action="store_true", help="keyboard input, no mic")
    args = ap.parse_args()

    if args.list_langs:
        for k, v in LANGUAGES.items():
            print(f"  {k}  {v.name}")
        return

    try:
        asyncio.run(run_voice_loop(args.lang, not args.no_barge_in, args.text))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
