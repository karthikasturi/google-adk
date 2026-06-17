"""
stt_whisper_service.py — STT via the local Whisper Docker microservice
=======================================================================
Drop-in replacement for OpenRouterSTT. Calls the faster-whisper FastAPI
service running at WHISPER_SERVICE_URL (default http://localhost:8001)
instead of sending audio to the cloud.

Start the service first:
    cd whisper-service && docker compose up -d

Same interface as OpenRouterSTT:
    transcribe(audio_float32_16k, language) -> Transcript
    transcribe_file(path, language)         -> Transcript

Swap in pipeline.py:
    from stt_whisper_service import WhisperServiceSTT
    stt = WhisperServiceSTT()
"""

from __future__ import annotations

import io
import os
import time
import wave

import httpx
import numpy as np

from stt_openrouter import Transcript   # shared dataclass

_DEFAULT_URL = "http://localhost:8001"


class WhisperServiceSTT:
    def __init__(self, url: str | None = None, timeout: float = 60.0):
        self.url = (url or os.environ.get("WHISPER_SERVICE_URL", _DEFAULT_URL)).rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _f32_to_wav_bytes(audio: np.ndarray, sample_rate: int = 16_000) -> bytes:
        pcm16 = (np.clip(audio.astype(np.float32), -1.0, 1.0) * 32767.0).astype("<i2")
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(pcm16.tobytes())
        return buf.getvalue()

    def _post(self, wav_bytes: bytes, language: str | None) -> tuple[str, str, float, int]:
        """POST to /transcribe. Returns (text, detected_language, confidence, latency_ms)."""
        t0 = time.perf_counter()
        resp = self._client.post(
            f"{self.url}/transcribe",
            files={"file": ("audio.wav", wav_bytes, "audio/wav")},
            data={"language": language} if language else {},
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Whisper service returned {resp.status_code}: {resp.text[:300]}\n"
                f"Is the service running?  cd whisper-service && docker compose up -d"
            )
        d = resp.json()
        return d["text"], d.get("detected_language", language or "auto"), d.get("confidence", 1.0), latency_ms

    # ── public interface (matches OpenRouterSTT) ──────────────────────────────

    def transcribe(self, audio: np.ndarray, language: str | None = None) -> Transcript:
        wav = self._f32_to_wav_bytes(audio)
        text, lang, conf, latency_ms = self._post(wav, language)
        return Transcript(text=text, confidence=conf, detected_language=lang, latency_ms=latency_ms)

    def transcribe_file(self, path: str, language: str | None = None) -> Transcript:
        with open(path, "rb") as f:
            wav = f.read()
        text, lang, conf, latency_ms = self._post(wav, language)
        return Transcript(text=text, confidence=conf, detected_language=lang, latency_ms=latency_ms)
