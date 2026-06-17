FROM python:3.12-slim

# ffmpeg — faster-whisper uses it to resample audio to 16 kHz when needed
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Model cache lives here — mount a volume to persist downloads across restarts
ENV HF_HOME=/models
# Set to a HuggingFace mirror if huggingface.co is blocked on your network:
# ENV HF_ENDPOINT=https://hf-mirror.com

ENV WHISPER_MODEL=small

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
