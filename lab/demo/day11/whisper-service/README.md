# Whisper STT Microservice

A self-contained Docker service that wraps **faster-whisper** (small model, CPU int8)
as a REST API. Any client — including `pipeline.py` — can transcribe audio by
posting a WAV file over HTTP, with no Python ML dependencies on the client side.

```
your machine:  pipeline.py → stt_whisper_service.py → POST /transcribe
docker:        whisper-service → faster-whisper → {"text": "…", "latency_ms": 450}
```

---

## Quickstart

```bash
cd lab/demo/day11/whisper-service

docker compose up -d          # build image + start service (model downloads on first run)
docker compose logs -f        # watch until you see "model ready"
```

First startup downloads the `small` model (~480 MB) from HuggingFace into the
`whisper-models` Docker volume. Subsequent restarts reuse the cached model.

```bash
# Smoke test
curl http://localhost:8001/health
# → {"status":"ok","model":"small"}

# Transcribe a WAV file
curl -X POST http://localhost:8001/transcribe \
     -F "file=@/path/to/audio.wav" \
     -F "language=en"
# → {"text":"…","detected_language":"en","confidence":0.95,"latency_ms":450}
```

---

## API

### `GET /health`
Returns service status.
```json
{"status": "ok", "model": "small"}
```

### `POST /transcribe`
| Field | Type | Description |
|-------|------|-------------|
| `file` | multipart file | WAV audio (mono; any sample rate — ffmpeg resamples to 16 kHz) |
| `language` | form string | optional language hint: `en`, `fr`, `hi`, … |

Response:
```json
{
  "text": "Where is my flight from Mumbai to Dubai tomorrow",
  "detected_language": "en",
  "confidence": 0.97,
  "latency_ms": 430
}
```

---

## Plug into pipeline.py

Replace `OpenRouterSTT` with `WhisperServiceSTT` in `pipeline.py`:

```python
# Before (cloud STT):
from stt_openrouter import OpenRouterSTT
stt = OpenRouterSTT()

# After (local Docker service):
from stt_whisper_service import WhisperServiceSTT
stt = WhisperServiceSTT()          # points at http://localhost:8001 by default
```

The wrapper (`../stt_whisper_service.py`) exposes the same interface:
```python
stt.transcribe(audio_np, language="en")      # → Transcript
stt.transcribe_file("/path/to.wav", "en")    # → Transcript
```

Set `WHISPER_SERVICE_URL` in `.env` if the service runs on a different host/port:
```
WHISPER_SERVICE_URL=http://192.168.1.10:8001
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_MODEL` | `small` | Model size: `tiny` / `base` / `small` / `medium` / `large-v3` |
| `HF_ENDPOINT` | — | HuggingFace mirror URL (if huggingface.co is blocked) |
| `HF_HOME` | `/models` | Where models are cached inside the container |

Change the model size in `docker-compose.yml`:
```yaml
environment:
  WHISPER_MODEL: medium   # better accuracy, needs ~1.5 GB RAM
```

---

## Model size reference

| Model | Size | English WER | Relative speed |
|-------|------|-------------|----------------|
| `tiny` | 75 MB | ~10% | fastest |
| `base` | 145 MB | ~7% | fast |
| `small` | 480 MB | ~4% | **recommended** |
| `medium` | 1.5 GB | ~3% | slower |
| `large-v3` | 3 GB | ~2% | slowest |

---

## Stop / reset

```bash
docker compose down          # stop, keep model cache
docker compose down -v       # stop + delete model volume (re-downloads next start)
```
