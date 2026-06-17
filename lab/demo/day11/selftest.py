"""
selftest.py — Non-simulated STT/TTS benchmark (no microphone needed)
=====================================================================
Validates the real pipeline and measures real latency without audio hardware.

For each language it:
  1. Synthesises a sentence with OpenRouter TTS → writes to a temp WAV
  2. Transcribes that WAV with OpenRouter STT → checks the text came back
  3. Optionally runs the transcript through the ADK agent
  4. Prints real latency numbers

Run this first to confirm your API key and model access before a live demo.

    python selftest.py              # en + fr
    python selftest.py -l hi        # Hindi only
    python selftest.py --with-agent # also time the ADK agent
"""

from __future__ import annotations

import argparse
import asyncio
import os
import tempfile
import time

from dotenv import load_dotenv
load_dotenv()

from languages import get_language

_C = {"b": "\033[1m", "g": "\033[32m", "y": "\033[33m", "r": "\033[31m",
      "dim": "\033[90m", "x": "\033[0m"}

_PHRASES = {
    "en": "Where is my flight from Mumbai to Dubai tomorrow?",
    "fr": "Où est mon vol de Mumbai à Dubaï demain ?",
    "hi": "कल मुंबई से दुबई की मेरी फ्लाइट कहाँ है?",
}


def _similar(a: str, b: str) -> float:
    import re
    wa = set(re.findall(r"\w+", a.lower()))
    wb = set(re.findall(r"\w+", b.lower()))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


async def _time_agent(text: str) -> tuple[str, int]:
    from agent import concierge_agent
    from session import make_runner
    from google.genai import types

    runner, uid, sid = await make_runner(concierge_agent)
    t0 = time.perf_counter()
    reply = ""
    async for event in runner.run_async(
        user_id=uid, session_id=sid,
        new_message=types.Content(role="user", parts=[types.Part(text=text)]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            t = event.content.parts[0].text
            if t:
                reply = t.strip()
    return reply, int((time.perf_counter() - t0) * 1000)


def run(lang_keys: list[str], with_agent: bool) -> None:
    from backends import make_stt, make_tts, stt_label, tts_label

    print(f"{_C['dim']}STT → {stt_label()}{_C['x']}")
    print(f"{_C['dim']}TTS → {tts_label()}{_C['x']}")

    stt = make_stt()
    tts = make_tts()

    if with_agent and not os.environ.get("OPENROUTER_API_KEY"):
        print(f"{_C['y']}OPENROUTER_API_KEY not set — skipping agent timing.{_C['x']}")
        with_agent = False

    all_ok = True
    for key in lang_keys:
        lang = get_language(key)
        phrase = _PHRASES.get(key, _PHRASES["en"])

        print(f"\n{'=' * 64}")
        print(f"{_C['b']}{lang.name} ({key}){_C['x']}")
        print(f"{'=' * 64}")
        print(f'  reference : "{phrase}"')

        # 1) TTS → WAV
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        tts_s = tts.synth_to_wav(phrase, wav_path)

        # 2) WAV → STT
        tr = stt.transcribe_file(wav_path, language=lang.lang_code)
        os.unlink(wav_path)

        sim = _similar(phrase, tr.text)
        ok = sim >= 0.4
        all_ok = all_ok and ok
        mark = f"{_C['g']}OK{_C['x']}" if ok else f"{_C['r']}CHECK{_C['x']}"

        print(f'  heard     : "{tr.text}"')
        print(f"  round-trip: word-overlap {sim:.0%}  [{mark}]")
        print(f"  {_C['b']}latency{_C['x']}  "
              f"TTS synth = {int(tts_s * 1000):>5}ms   "
              f"STT = {tr.latency_ms:>5}ms   "
              f"conf = {tr.confidence:.2f}")

        if with_agent:
            reply, agent_ms = asyncio.run(_time_agent(tr.text))
            print(f"  agent     = {agent_ms:>5}ms   reply: \"{reply[:60]}…\"")
            print(f"  {_C['b']}mouth-to-ear estimate{_C['x']} "
                  f"≈ {tr.latency_ms + agent_ms + int(tts_s * 1000)}ms")

    print(f"\n{'=' * 64}")
    if all_ok:
        print(f"Round-trip check: {_C['g']}all OK{_C['x']}")
    else:
        print(f"Round-trip check: {_C['y']}review CHECK rows above{_C['x']}")
    print(f"{'=' * 64}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Non-simulated STT/TTS benchmark")
    ap.add_argument("-l", "--lang", help="single language key (default: en + fr)")
    ap.add_argument("--with-agent", action="store_true",
                    help="also time the ADK agent (needs OPENROUTER_API_KEY)")
    args = ap.parse_args()

    langs = [args.lang] if args.lang else ["en", "fr"]
    run(langs, args.with_agent)


if __name__ == "__main__":
    main()
