"""
selftest.py — STT/TTS round-trip benchmark (no microphone needed)
=================================================================
Run this before a live demo to confirm your API key and model access.

For each language it:
  1. Synthesises a sentence via OpenRouter TTS → saves to a temp WAV
  2. Transcribes that WAV via OpenRouter STT → checks the words came back
  3. Prints real TTS and STT latency numbers

    python selftest.py          # en + fr
    python selftest.py -l hi    # Hindi only
"""

from __future__ import annotations

import argparse
import os
import tempfile

from dotenv import load_dotenv
load_dotenv()

from languages import get_language
from stt_openrouter import OpenRouterSTT
from tts_openrouter import OpenRouterTTS

_C = {"b": "\033[1m", "g": "\033[32m", "r": "\033[31m", "dim": "\033[90m", "x": "\033[0m"}

_PHRASES = {
    "en": "Where is my flight from Mumbai to Dubai tomorrow?",
    "fr": "Où est mon vol de Mumbai à Dubaï demain ?",
    "hi": "कल मुंबई से दुबई की मेरी फ्लाइट कहाँ है?",
}


def _word_overlap(a: str, b: str) -> float:
    import re
    wa = set(re.findall(r"\w+", a.lower()))
    wb = set(re.findall(r"\w+", b.lower()))
    return len(wa & wb) / len(wa | wb) if (wa and wb) else 0.0


def run(lang_keys: list[str]) -> None:
    stt = OpenRouterSTT()
    tts = OpenRouterTTS()

    print(f"{_C['dim']}STT model: {stt.model}{_C['x']}")
    print(f"{_C['dim']}TTS model: {tts.model}{_C['x']}")

    all_ok = True
    for key in lang_keys:
        lang = get_language(key)
        phrase = _PHRASES.get(key, _PHRASES["en"])

        print(f"\n{'=' * 60}")
        print(f"{_C['b']}{lang.name} ({key}){_C['x']}")
        print(f"{'=' * 60}")
        print(f'  reference : "{phrase}"')

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        tts_s = tts.synth_to_wav(phrase, wav_path)
        tr = stt.transcribe_file(wav_path, language=lang.lang_code)
        os.unlink(wav_path)

        sim = _word_overlap(phrase, tr.text)
        ok = sim >= 0.4
        all_ok = all_ok and ok
        mark = f"{_C['g']}OK{_C['x']}" if ok else f"{_C['r']}CHECK{_C['x']}"

        print(f'  heard     : "{tr.text}"')
        print(f"  overlap   : {sim:.0%}  [{mark}]")
        print(f"  {_C['b']}latency{_C['x']}  TTS={int(tts_s*1000)}ms  STT={tr.latency_ms}ms")

    print(f"\n{'=' * 60}")
    print(f"Result: {_C['g']}all OK{_C['x']}" if all_ok else f"Result: {_C['r']}CHECK rows above{_C['x']}")
    print(f"{'=' * 60}")


def main() -> None:
    ap = argparse.ArgumentParser(description="STT/TTS round-trip benchmark")
    ap.add_argument("-l", "--lang", help="language key (default: en + fr)")
    args = ap.parse_args()
    run([args.lang] if args.lang else ["en", "fr"])


if __name__ == "__main__":
    main()
