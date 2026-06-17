"""
metrics.py — Latency measurement for the voice loop
====================================================
Real (not simulated) timing of each stage so the trainer can correlate the
console trace with what they hear:

    end-of-speech ──► STT ──► agent (LLM + tools) ──► TTS first audio ──► speaker
                   └──────────── "mouth-to-ear" latency ───────────────┘

Target: first audio within ~1.5 s of the user finishing speaking feels
responsive in conversation. The table flags PASS / WARN against that budget.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

# Mouth-to-ear budget (ms) for the response to *start*.
RESPONSIVE_MS = 1500
ACCEPTABLE_MS = 2500

_C = {
    "g": "\033[32m", "y": "\033[33m", "r": "\033[31m",
    "dim": "\033[90m", "b": "\033[1m", "x": "\033[0m",
}


@dataclass
class TurnMetrics:
    stt_ms: int
    agent_ms: int
    tts_ttfb_ms: int          # synth + first-audio after agent returns
    speech_to_first_audio_ms: int
    tts_total_ms: int = 0
    transcript: str = ""
    confidence: float = 0.0

    def verdict(self) -> str:
        m = self.speech_to_first_audio_ms
        if m <= RESPONSIVE_MS:
            return f"{_C['g']}PASS (responsive){_C['x']}"
        if m <= ACCEPTABLE_MS:
            return f"{_C['y']}WARN (usable){_C['x']}"
        return f"{_C['r']}SLOW{_C['x']}"


def print_turn(m: TurnMetrics) -> None:
    rows = [
        ("STT (OpenRouter)", m.stt_ms),
        ("Agent (ADK + LLM + tools)", m.agent_ms),
        ("TTS first audio (OpenRouter)", m.tts_ttfb_ms),
        ("MOUTH-TO-EAR (speech → audio)", m.speech_to_first_audio_ms),
    ]
    w = max(len(r[0]) for r in rows)
    total = max(1, m.speech_to_first_audio_ms)
    scale = max(1, total // 36)

    print(f"\n{_C['b']}  LATENCY{_C['x']}  {_C['dim']}conf={m.confidence:.2f}{_C['x']}")
    for label, ms in rows:
        if label.startswith("MOUTH"):
            print(f"  {_C['dim']}{'─' * (w + 16)}{_C['x']}")
        bar = "█" * max(1, ms // scale)
        print(f"  {label:<{w}}  {ms:>6}ms  {_C['dim']}{bar}{_C['x']}")
    print(f"  {'verdict':<{w}}  {m.verdict()}  "
          f"{_C['dim']}(budget {RESPONSIVE_MS}ms){_C['x']}")


class MetricsLog:
    """Collects per-turn metrics and prints a session summary."""

    def __init__(self):
        self.turns: list[TurnMetrics] = []

    def add(self, m: TurnMetrics) -> None:
        self.turns.append(m)

    def summary(self) -> None:
        if not self.turns:
            return
        def col(attr):
            return [getattr(t, attr) for t in self.turns]

        print(f"\n{'=' * 60}")
        print(f"{_C['b']}  SESSION LATENCY SUMMARY  ({len(self.turns)} turns){_C['x']}")
        print(f"{'=' * 60}")
        for label, attr in [
            ("STT", "stt_ms"),
            ("Agent", "agent_ms"),
            ("TTS first audio", "tts_ttfb_ms"),
            ("Mouth-to-ear", "speech_to_first_audio_ms"),
        ]:
            vals = col(attr)
            mean = int(statistics.mean(vals))
            p50 = int(statistics.median(vals))
            mx = max(vals)
            print(f"  {label:<18} mean={mean:>6}ms  median={p50:>6}ms  max={mx:>6}ms")

        ear = col("speech_to_first_audio_ms")
        passed = sum(1 for v in ear if v <= RESPONSIVE_MS)
        print(f"\n  {passed}/{len(ear)} turns started within the "
              f"{RESPONSIVE_MS}ms responsive budget.")
        print(f"{'=' * 60}")
