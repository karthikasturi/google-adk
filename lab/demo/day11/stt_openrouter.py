"""
stt_openrouter.py — Speech-to-text via OpenRouter (audio-input models)
=======================================================================
Sends recorded audio to an OpenRouter model that accepts audio input
(OpenAI-compatible chat completions with an `input_audio` content part)
and returns the verbatim transcription.

Default model: google/gemini-2.5-flash — multilingual (en, fr, hi, …),
same family as the agent, one API key for the whole pipeline.
Override with OPENROUTER_STT_MODEL.

Interface:
    transcribe(audio_float32_16k, language) -> Transcript
    transcribe_file(path, language)         -> Transcript
"""

from __future__ import annotations

import base64
import io
import os
import time
import wave
from dataclasses import dataclass

import numpy as np


@dataclass
class Transcript:
    text: str
    confidence: float       # 0..1 (cloud LLM gives no per-token confidence; always 1.0)
    detected_language: str
    latency_ms: int

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_SYSTEM = (
    "You are a speech-to-text transcriber. Output ONLY the exact words spoken in "
    "the audio, in the original language. No commentary, no labels, no quotation "
    "marks. If nothing is said, output an empty line."
)


def _f32_to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    pcm = np.clip(audio.astype(np.float32), -1.0, 1.0)
    pcm16 = (pcm * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm16.tobytes())
    return buf.getvalue()


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for part in content:
            if isinstance(part, str):
                out.append(part)
            elif isinstance(part, dict):
                out.append(part.get("text", ""))
        return "".join(out)
    return str(content or "")


class OpenRouterSTT:
    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        sample_rate: int = 16_000,
        timeout: float = 60.0,
    ):
        import httpx

        self.model = model or os.environ.get("OPENROUTER_STT_MODEL", "google/gemini-2.5-flash")
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key or self.api_key.startswith("your-"):
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Put your key in day11/.env "
                "(OPENROUTER_API_KEY=sk-or-...)."
            )
        self.sample_rate = sample_rate
        self._client = httpx.Client(timeout=timeout)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept-Encoding": "identity",   # avoid buffering (see tts_openrouter)
            "HTTP-Referer": "https://localhost/day11-voice-travelbot",
            "X-Title": "Day11 Voice TravelBot",
        }

    def _request(self, wav_bytes: bytes, language: str | None) -> tuple[str, int]:
        b64 = base64.b64encode(wav_bytes).decode()
        hint = f" The spoken language is {language}." if language else ""
        payload = {
            "model": self.model,
            "modalities": ["text"],
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Transcribe this audio verbatim.{hint}"},
                        {"type": "input_audio", "input_audio": {"data": b64, "format": "wav"}},
                    ],
                },
            ],
        }
        t0 = time.perf_counter()
        r = self._client.post(OPENROUTER_URL, headers=self._headers(), json=payload)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code != 200:
            raise RuntimeError(f"OpenRouter STT {r.status_code}: {r.text[:300]}")
        data = r.json()
        text = _extract_text(data["choices"][0]["message"].get("content", "")).strip()
        return text.strip().strip('"'), latency_ms

    def transcribe(self, audio: np.ndarray, language: str | None = None) -> Transcript:
        wav = _f32_to_wav_bytes(audio, self.sample_rate)
        text, latency_ms = self._request(wav, language)
        return Transcript(
            text=text,
            confidence=1.0,                 # cloud LLM gives no token-level confidence
            detected_language=language or "auto",
            latency_ms=latency_ms,
        )

    def transcribe_file(self, path: str, language: str | None = None) -> Transcript:
        with open(path, "rb") as f:
            wav = f.read()
        text, latency_ms = self._request(wav, language)
        return Transcript(
            text=text, confidence=1.0,
            detected_language=language or "auto", latency_ms=latency_ms,
        )
