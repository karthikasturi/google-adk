"""
backends.py — STT/TTS engine factory
=====================================
Returns the OpenRouter-based STT and TTS engines.
One API key (OPENROUTER_API_KEY) covers STT, the agent LLM, and TTS.
"""

from __future__ import annotations

import os


def make_stt():
    from stt_openrouter import OpenRouterSTT
    return OpenRouterSTT()


def make_tts():
    from tts_openrouter import OpenRouterTTS
    return OpenRouterTTS()


def stt_label() -> str:
    return f"OpenRouter STT ({os.environ.get('OPENROUTER_STT_MODEL', 'google/gemini-2.5-flash')})"


def tts_label() -> str:
    return f"OpenRouter TTS ({os.environ.get('OPENROUTER_TTS_MODEL', 'openai/gpt-audio')})"
