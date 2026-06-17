"""
audio_io.py — Microphone capture, VAD endpointing, and barge-in playback
=========================================================================
The hardware ends of the pipeline:

    microphone → [listen_utterance]  ... text ...  [speak] → speaker

  listen_utterance()  Captures one spoken utterance. Uses webrtcvad to detect
                      speech start and a trailing-silence window to detect the
                      end (endpointing), so the user doesn't press any key.

  speak()             Plays synthesized PCM while simultaneously monitoring the
                      mic. If the user starts talking (barge-in), playback stops
                      immediately and the interrupting utterance is captured and
                      returned, so the caller can treat it as the next turn.

All capture is 16 kHz mono int16 (what webrtcvad and the OpenRouter STT model expect). Playback
runs at the TTS sample rate on a separate output stream (full-duplex).
"""

from __future__ import annotations

import collections
import threading
import time
from dataclasses import dataclass

import numpy as np

SAMPLE_RATE = 16_000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000      # 480 samples
FRAME_BYTES = FRAME_SAMPLES * 2                      # 960 bytes (int16)


@dataclass
class Utterance:
    audio: np.ndarray        # float32 mono 16 kHz in [-1, 1]
    duration_s: float
    capture_end_t: float     # perf_counter() at end-of-speech (for latency math)


def _pcm_bytes_to_float32(pcm: bytes) -> np.ndarray:
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


class AudioIO:
    def __init__(
        self,
        vad_aggressiveness: int = 2,        # 0..3, higher = filters more non-speech
        input_device=None,
        output_device=None,
        start_ratio: float = 0.6,           # fraction of recent frames voiced → speech start
        end_silence_ms: int = 700,          # trailing silence that ends an utterance
        min_speech_ms: int = 250,           # ignore blips shorter than this
        bargein_speech_ms: int = 200,       # sustained speech during TTS → barge-in
    ):
        import webrtcvad

        self.vad = webrtcvad.Vad(vad_aggressiveness)
        self.input_device = input_device
        self.output_device = output_device
        self.start_ratio = start_ratio
        self.end_silence_frames = end_silence_ms // FRAME_MS
        self.min_speech_frames = min_speech_ms // FRAME_MS
        self.bargein_frames = max(1, bargein_speech_ms // FRAME_MS)

    # ── Capture ───────────────────────────────────────────────────────────────

    def listen_utterance(self, prebuffer: list[bytes] | None = None) -> Utterance:
        """Block until one full utterance is captured, then return it.

        Args:
            prebuffer: optional already-captured speech frames (e.g. the first
                       few frames of a barge-in) to prepend so no audio is lost.
        """
        import sounddevice as sd

        ring: collections.deque = collections.deque(maxlen=int(self.start_ratio * 10) + 6)
        voiced: list[bytes] = list(prebuffer or [])
        triggered = bool(voiced)
        trailing_silence = 0
        t_start = time.perf_counter()

        with sd.RawInputStream(
            samplerate=SAMPLE_RATE, blocksize=FRAME_SAMPLES, dtype="int16",
            channels=1, device=self.input_device,
        ) as stream:
            while True:
                data, _ = stream.read(FRAME_SAMPLES)
                frame = bytes(data)
                if len(frame) < FRAME_BYTES:
                    continue
                is_speech = self.vad.is_speech(frame, SAMPLE_RATE)

                if not triggered:
                    ring.append((frame, is_speech))
                    voiced_count = sum(1 for _, s in ring if s)
                    if ring.maxlen and voiced_count >= self.start_ratio * ring.maxlen:
                        triggered = True
                        voiced.extend(f for f, _ in ring)
                        ring.clear()
                else:
                    voiced.append(frame)
                    if is_speech:
                        trailing_silence = 0
                    else:
                        trailing_silence += 1
                        if (trailing_silence >= self.end_silence_frames
                                and len(voiced) >= self.min_speech_frames):
                            break

        capture_end = time.perf_counter()
        pcm = b"".join(voiced)
        audio = _pcm_bytes_to_float32(pcm)
        return Utterance(audio=audio, duration_s=capture_end - t_start, capture_end_t=capture_end)

    # ── Playback with barge-in ────────────────────────────────────────────────

    def speak(
        self,
        pcm_iter,
        sample_rate: int,
        allow_barge_in: bool = True,
    ) -> tuple[bool, float | None, Utterance | None]:
        """Play streamed int16 PCM, optionally interruptible by the user's voice.

        Args:
            pcm_iter:  iterable of int16 PCM byte chunks (from OpenRouterTTS.iter_pcm).
            sample_rate: sample rate of those chunks.
            allow_barge_in: monitor the mic and stop on sustained user speech.

        Returns:
            (completed, ttfb_s, barge_in_utterance)
              completed   — True if playback finished, False if interrupted
              ttfb_s      — time from speak() start to first audio written
              barge_in    — the interrupting Utterance (None if not interrupted)
        """
        import sounddevice as sd

        interrupted = threading.Event()
        stop_monitor = threading.Event()
        prebuf: list[bytes] = []
        prebuf_lock = threading.Lock()

        def monitor():
            try:
                with sd.RawInputStream(
                    samplerate=SAMPLE_RATE, blocksize=FRAME_SAMPLES, dtype="int16",
                    channels=1, device=self.input_device,
                ) as mic:
                    consec = 0
                    while not stop_monitor.is_set():
                        data, _ = mic.read(FRAME_SAMPLES)
                        frame = bytes(data)
                        if len(frame) < FRAME_BYTES:
                            continue
                        if self.vad.is_speech(frame, SAMPLE_RATE):
                            consec += 1
                            with prebuf_lock:
                                prebuf.append(frame)
                                if len(prebuf) > 25:
                                    prebuf.pop(0)
                            if consec >= self.bargein_frames:
                                interrupted.set()
                                return
                        else:
                            consec = 0
                            with prebuf_lock:
                                prebuf.clear()
            except Exception:
                # If a second input stream can't be opened (device busy),
                # disable barge-in gracefully rather than crash the demo.
                pass

        mon = None
        if allow_barge_in:
            mon = threading.Thread(target=monitor, daemon=True)
            mon.start()

        # Re-slice incoming PCM into ~20 ms blocks so we can check `interrupted`
        # frequently and stop within a few milliseconds of a barge-in.
        block_bytes = int(sample_rate * 0.02) * 2
        ttfb: float | None = None
        completed = True
        t0 = time.perf_counter()
        pending = b""

        with sd.RawOutputStream(
            samplerate=sample_rate, channels=1, dtype="int16",
            device=self.output_device,
        ) as out:
            for chunk in pcm_iter:
                pending += bytes(chunk)
                while len(pending) >= block_bytes:
                    if interrupted.is_set():
                        completed = False
                        break
                    block, pending = pending[:block_bytes], pending[block_bytes:]
                    if ttfb is None:
                        ttfb = time.perf_counter() - t0
                    out.write(block)
                if not completed:
                    break
            if completed and pending and not interrupted.is_set():
                if ttfb is None:
                    ttfb = time.perf_counter() - t0
                out.write(pending)

        stop_monitor.set()
        if mon:
            mon.join(timeout=0.3)

        barge_utt = None
        if not completed and interrupted.is_set():
            with prebuf_lock:
                seed = list(prebuf)
            # Capture the rest of the interrupting utterance, seeded with the
            # frames the monitor already heard so the first word isn't clipped.
            barge_utt = self.listen_utterance(prebuffer=seed)

        return completed, ttfb, barge_utt
