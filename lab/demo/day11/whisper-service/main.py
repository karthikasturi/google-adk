"""
main.py — Whisper STT microservice (FastAPI)
============================================
Wraps faster-whisper as an HTTP service so any client can transcribe audio
without needing Python or ML packages installed locally.

Endpoints
    GET  /health       → {"status": "ok", "model": "small"}
    POST /transcribe   → multipart: file=<wav>, language=<optional lang code>
                         returns {"text", "detected_language", "confidence", "latency_ms"}

The model is loaded once at startup (downloaded from HuggingFace on first run,
then cached in $HF_HOME — mount a volume there to persist across restarts).

Environment variables
    WHISPER_MODEL    model size: tiny | base | small (default) | medium | large-v3
    HF_ENDPOINT      HuggingFace mirror, e.g. https://hf-mirror.com
"""

from __future__ import annotations

import io
import math
import os
import tempfile
import time
import wave
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from faster_whisper import WhisperModel

_model: WhisperModel | None = None
_model_size: str = os.environ.get("WHISPER_MODEL", "small")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model
    print(f"[whisper] loading model '{_model_size}' (device=cpu, compute=int8)…", flush=True)
    _model = WhisperModel(_model_size, device="cpu", compute_type="int8")
    print("[whisper] model ready", flush=True)
    yield


app = FastAPI(title="Whisper STT Service", version="1.0", lifespan=lifespan)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "model": _model_size}


# ── Transcribe ────────────────────────────────────────────────────────────────

@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(..., description="WAV audio file (mono, any sample rate)"),
    language: Optional[str] = Form(None, description="language code hint, e.g. 'en', 'fr', 'hi'"),
):
    """Transcribe an uploaded WAV file and return the text + timing."""
    if _model is None:
        raise HTTPException(503, "Model not loaded yet — try again in a moment")

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(400, "Empty audio file")

    # Write to a temp file so faster-whisper can resample via ffmpeg if needed
    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        t0 = time.perf_counter()
        segments, info = _model.transcribe(
            tmp_path,
            language=language or None,
            beam_size=1,
            vad_filter=False,               # VAD is handled upstream
            condition_on_previous_text=False,
        )
        segments = list(segments)           # consume generator before timing ends
        latency_ms = int((time.perf_counter() - t0) * 1000)
    finally:
        os.unlink(tmp_path)

    text = "".join(s.text for s in segments).strip()

    # Approximate confidence from per-segment log-probability
    logprobs = [s.avg_logprob for s in segments if s.avg_logprob is not None]
    if logprobs:
        confidence = float(math.exp(sum(logprobs) / len(logprobs)))
    else:
        confidence = float(getattr(info, "language_probability", 0.8) or 0.8)
    confidence = round(max(0.0, min(1.0, confidence)), 3)

    return JSONResponse({
        "text": text,
        "detected_language": info.language,
        "confidence": confidence,
        "latency_ms": latency_ms,
    })
