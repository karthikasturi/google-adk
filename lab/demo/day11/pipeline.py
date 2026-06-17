"""
pipeline.py — Day 11: Real-time voice TravelBot
================================================
End-to-end, no simulation:

    microphone → STT (OpenRouter) → Google ADK agents/tools → TTS (OpenRouter) → speaker

Features
  - Real STT and TTS via OpenRouter (one API key for everything).
  - VAD endpointing (webrtcvad): just talk, no push-to-talk.
  - Barge-in: start speaking while TravelBot talks and it stops and listens.
  - Per-turn latency measured (STT / agent / TTS first-audio / mouth-to-ear).
  - Multiple languages: English, French, Hindi (-l en | -l fr | -l hi).

Run
    python pipeline.py                 # English
    python pipeline.py -l fr           # French
    python pipeline.py -l hi           # Hindi
    python pipeline.py --list-langs
    python pipeline.py --no-barge-in   # disable interruption (single-mic setups)
    python pipeline.py --text          # type instead of speaking (no mic needed)

Prereqs
    pip install -r requirements.txt
    cp .env.example .env   # set OPENROUTER_API_KEY
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

from dotenv import load_dotenv
load_dotenv()

from agent import concierge_agent
from languages import LANGUAGES, get_language
from metrics import MetricsLog, TurnMetrics, print_turn
from session import make_runner

_C = {
    "b": "\033[1m", "cyan": "\033[36m", "green": "\033[32m",
    "yellow": "\033[33m", "red": "\033[31m", "dim": "\033[90m", "x": "\033[0m",
}


def _banner(title: str, sub: str = "") -> None:
    print(f"\n{'=' * 70}")
    print(f"{_C['b']}{_C['cyan']}{title}{_C['x']}")
    if sub:
        print(f"{_C['dim']}{sub}{_C['x']}")
    print(f"{'=' * 70}")


class AgentTurnRunner:
    """Runs one text turn through the ADK runner, collecting reply + trace."""

    def __init__(self, runner, user_id, session_id):
        self.runner = runner
        self.user_id = user_id
        self.session_id = session_id

    async def run(self, text: str) -> tuple[str, str, list[str], int]:
        from google.genai import types

        t0 = time.perf_counter()
        final_text, author, tools = "", "", []

        async for event in self.runner.run_async(
            user_id=self.user_id,
            session_id=self.session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=text)]),
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    fc = getattr(part, "function_call", None)
                    if fc:
                        if fc.name == "transfer_to_agent":
                            tgt = dict(fc.args or {}).get("agent_name", "specialist")
                            print(f"  {_C['dim']}[route] {event.author} → {tgt}{_C['x']}")
                        else:
                            tools.append(fc.name)
                            args = ", ".join(f"{k}={v!r}" for k, v in (fc.args or {}).items())
                            print(f"  {_C['dim']}[tool]  {fc.name}({args}){_C['x']}")
            if event.is_final_response() and event.content and event.content.parts:
                t = event.content.parts[0].text
                if t:
                    final_text, author = t.strip(), event.author

        return final_text, author, tools, int((time.perf_counter() - t0) * 1000)


def _split_sentences(text: str) -> list[str]:
    import re
    parts = re.split(r"(?<=[.!?。！？])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


async def run_voice_loop(lang_key: str, allow_barge_in: bool, text_mode: bool) -> None:
    from backends import make_stt, make_tts, stt_label, tts_label

    lang = get_language(lang_key)

    _banner(
        f"Day 11 — Voice TravelBot  [{lang.name}]",
        f"mic → {stt_label()} → Google ADK → {tts_label()} → speaker"
        "   (Ctrl-C to quit)",
    )

    print(f"{_C['dim']}STT → {stt_label()}{_C['x']}")
    stt = make_stt()

    print(f"{_C['dim']}TTS → {tts_label()}{_C['x']}")
    tts = make_tts()

    audio = None
    if not text_mode:
        from audio_io import AudioIO
        audio = AudioIO()

    runner, uid, sid = await make_runner(concierge_agent)
    turns = AgentTurnRunner(runner, uid, sid)
    metrics = MetricsLog()

    print(f"\n{_C['green']}TravelBot:{_C['x']} {lang.greeting}")
    if audio:
        audio.speak(tts.iter_pcm(lang.greeting), tts.sample_rate, allow_barge_in=False)

    print(f"\n{_C['dim']}Try: {lang.sample_prompts[0]}{_C['x']}\n")

    pending_audio = None
    try:
        while True:
            # 1) Capture user speech
            if text_mode:
                try:
                    text = input(f"{_C['b']}You (type):{_C['x']} ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if text.lower() in ("quit", "exit", "q", ""):
                    if text.lower() in ("quit", "exit", "q"):
                        break
                    continue
                speech_end_t = time.perf_counter()
                stt_ms, conf = 0, 1.0
            else:
                if pending_audio is not None:
                    utt, pending_audio = pending_audio, None
                else:
                    print(f"{_C['dim']}🎙  listening… (speak now){_C['x']}")
                    utt = audio.listen_utterance()
                speech_end_t = utt.capture_end_t
                tr = stt.transcribe(utt.audio, language=lang.whisper_code)
                text, stt_ms, conf = tr.text, tr.latency_ms, tr.confidence
                if not text:
                    print(f"{_C['yellow']}…didn't catch that, please repeat.{_C['x']}")
                    continue
                lowconf = "  ⚠ low confidence" if conf < 0.6 else ""
                print(f"{_C['b']}You said:{_C['x']} \"{text}\"  "
                      f"{_C['dim']}(stt {stt_ms}ms, conf {conf:.2f}){lowconf}{_C['x']}")

            # 2) Agent
            print(f"{_C['dim']}…thinking…{_C['x']}")
            reply, author, tools, agent_ms = await turns.run(text)
            if not reply:
                reply = "Sorry, I didn't get a response. Could you try again?"
            print(f"{_C['green']}TravelBot ({author}):{_C['x']} {reply}")

            # 3) Speak sentence by sentence (lower first-audio latency, natural barge-in)
            tts_ttfb_ms = 0
            interrupted = False
            if audio:
                t_speak0 = time.perf_counter()
                first_audio_t = None
                for sentence in _split_sentences(reply):
                    completed, ttfb, barge = audio.speak(
                        tts.iter_pcm(sentence), tts.sample_rate,
                        allow_barge_in=allow_barge_in,
                    )
                    if first_audio_t is None and ttfb is not None:
                        first_audio_t = t_speak0 + ttfb
                    if not completed and barge is not None:
                        print(f"  {_C['yellow']}[barge-in detected — stopping playback]{_C['x']}")
                        pending_audio = barge
                        interrupted = True
                        break
                if first_audio_t is not None:
                    tts_ttfb_ms = int((first_audio_t - t_speak0) * 1000)

            # 4) Latency table
            m = TurnMetrics(
                stt_ms=stt_ms,
                agent_ms=agent_ms,
                tts_ttfb_ms=tts_ttfb_ms,
                speech_to_first_audio_ms=stt_ms + agent_ms + tts_ttfb_ms,
                transcript=text,
                confidence=conf,
            )
            metrics.add(m)
            print_turn(m)
            if interrupted:
                print(f"  {_C['dim']}(next turn = the words you interrupted with){_C['x']}")
            print()
    except KeyboardInterrupt:
        pass
    finally:
        metrics.summary()
        print("\nGoodbye!")


def main() -> None:
    ap = argparse.ArgumentParser(description="Day 11 real-time voice TravelBot")
    ap.add_argument("-l", "--lang", default="en", help="language key: en (default), fr, hi")
    ap.add_argument("--list-langs", action="store_true", help="list languages and exit")
    ap.add_argument("--no-barge-in", action="store_true", help="disable interruption")
    ap.add_argument("--text", action="store_true",
                    help="type input instead of speaking (no mic needed)")
    args = ap.parse_args()

    if args.list_langs:
        for k, v in LANGUAGES.items():
            print(f"  {k:4} {v.name}")
        return

    try:
        asyncio.run(run_voice_loop(args.lang, not args.no_barge_in, args.text))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
