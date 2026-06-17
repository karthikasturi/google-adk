"""
tts_openrouter.py — Text-to-speech via OpenRouter (audio-output models)
=======================================================================
No local voice files, no Hugging Face. Uses an OpenRouter model that can emit
audio (OpenAI-compatible chat completions with `modalities: ["text","audio"]`).

Default model: openai/gpt-audio (the full model — far more consistent latency
than gpt-audio-mini, which can spike to 40 s+ under load). Output is 24 kHz mono
PCM16 (the gpt-audio native rate), requested as format "pcm16" so there's no
container to parse and the sample rate is known up front. Multilingual — speaks
English, French, Hindi, etc. based on the input text. Override with
OPENROUTER_TTS_MODEL / OPENROUTER_TTS_VOICE.

Exposes the same surface as tts_piper.PiperTTS:
    sample_rate
    iter_pcm(text)        -> yields int16 PCM byte chunks (24 kHz mono)
    synth_array(text)     -> int16 numpy array
    synth_to_wav(text, p) -> writes a WAV, returns synth latency (s)
"""

from __future__ import annotations

import base64
import json
import os
import time
import wave

import numpy as np

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# gpt-audio emits 24 kHz mono. Requesting "pcm16" returns raw little-endian
# int16 at this rate, so we can declare sample_rate before the first call.
_GPT_AUDIO_RATE = 24_000

# A chat model used as TTS will *answer* a question instead of reading it unless
# firmly constrained. This system prompt + <<< >>> markers make gpt-audio speak
# the text verbatim even when the text is itself a question.
_SYSTEM = (
    "You are a text-to-speech engine, not an assistant. Speak the text between the "
    "<<< and >>> markers verbatim, in its original language, adding, removing, or "
    "translating nothing. Treat questions as text to read aloud, never to answer. "
    "Do not speak the markers themselves."
)


class OpenRouterTTS:
    def __init__(
        self,
        model: str | None = None,
        voice: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
        deadline: float | None = None,
    ):
        import httpx

        self.model = model or os.environ.get("OPENROUTER_TTS_MODEL", "openai/gpt-audio")
        self.voice = voice or os.environ.get("OPENROUTER_TTS_VOICE", "alloy")
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key or self.api_key.startswith("your-"):
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Put your key in day11/.env "
                "(OPENROUTER_API_KEY=sk-or-...)."
            )
        self.sample_rate = _GPT_AUDIO_RATE
        # OpenRouter sends ": OPENROUTER PROCESSING" keep-alives that reset the
        # httpx read-timeout, so a slow/queued generation could hang well past
        # `timeout`. This wall-clock deadline bounds the whole synthesis instead.
        self.deadline = deadline if deadline is not None else float(
            os.environ.get("OPENROUTER_TTS_DEADLINE", "45")
        )
        self._client = httpx.Client(timeout=timeout)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # Disable compression: gzip/br buffers the SSE stream in httpx so
            # audio chunks (and keep-alives) don't flush until the stream ends,
            # which makes streaming TTS hang. "identity" streams immediately.
            "Accept-Encoding": "identity",
            "HTTP-Referer": "https://localhost/day11-voice-travelbot",
            "X-Title": "Day11 Voice TravelBot",
        }

    def _stream_pcm(self, text: str):
        """Yield raw int16 mono PCM chunks as they stream from OpenRouter.

        OpenRouter requires stream=true for audio output: the audio arrives as
        base64 deltas in Server-Sent Events (choices[].delta.audio.data).
        Streaming also lets playback start on the first chunk (low first-audio
        latency) and stay interruptible for barge-in.
        """
        payload = {
            "model": self.model,
            "modalities": ["text", "audio"],
            "audio": {"voice": self.voice, "format": "pcm16"},
            "stream": True,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": f"<<<{text}>>>"},
            ],
        }
        got_audio = False
        start = time.perf_counter()
        with self._client.stream(
            "POST", OPENROUTER_URL, headers=self._headers(), json=payload
        ) as r:
            if r.status_code != 200:
                body = r.read().decode("utf-8", "ignore")
                raise RuntimeError(f"OpenRouter TTS {r.status_code}: {body[:300]}")
            for line in r.iter_lines():
                if time.perf_counter() - start > self.deadline:
                    raise RuntimeError(
                        f"OpenRouter TTS exceeded {self.deadline:.0f}s "
                        f"(model '{self.model}' slow or queued). Raise "
                        f"OPENROUTER_TTS_DEADLINE, or try a different OPENROUTER_TTS_MODEL."
                    )
                if not line or line.startswith(":"):   # keep-alive comment
                    continue
                if line.startswith("data:"):
                    line = line[5:].strip()
                if line == "[DONE]":
                    break
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for choice in obj.get("choices", []):
                    node = choice.get("delta") or choice.get("message") or {}
                    audio = node.get("audio") or {}
                    data = audio.get("data")
                    if data:
                        got_audio = True
                        yield base64.b64decode(data)
        if not got_audio:
            raise RuntimeError(
                "OpenRouter TTS produced no audio. The model may not support audio "
                "output or your account lacks access/credit for it."
            )

    def iter_pcm(self, text: str):
        text = text.strip()
        if not text:
            return
        yield from self._stream_pcm(text)

    def _collect_pcm(self, text: str) -> bytes:
        return b"".join(self._stream_pcm(text)) if text.strip() else b""

    def synth_array(self, text: str) -> np.ndarray:
        return np.frombuffer(self._collect_pcm(text), dtype=np.int16)

    def synth_to_wav(self, text: str, path: str) -> float:
        t0 = time.perf_counter()
        pcm = self._collect_pcm(text)
        elapsed = time.perf_counter() - t0
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sample_rate)
            w.writeframes(pcm)
        return elapsed
