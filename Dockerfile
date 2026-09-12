# ==============================================================================
# AI Music Studio — Backend Dockerfile
# Hardened Python 3.10 runtime with FluidSynth & SoundFont synthesis engines.
# ==============================================================================

FROM python:3.10-slim-bullseye

# Set environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    DATABASE_URL=sqlite:////app/data/ai_music_studio.db \
    MODEL_DIR=/app/models \
    SOUNDFONT_PATH=/usr/share/sounds/sf2/default-GM.sf2 \
    FLUIDSYNTH_PATH=/usr/bin/fluidsynth \
    APP_ENV=production

# Install essential audio synthesis libraries and system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    fluidsynth \
    fluid-soundfont-gm \
    ffmpeg \
    libsndfile1 \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create secure non-root user (UID 1000)
RUN useradd -m -u 1000 studio
WORKDIR /app

# Install Python requirements and production ASGI server (Gunicorn)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application source code (ignoring datasets, .env, and caches per .dockerignore)
COPY backend/ ./backend/
COPY ml/ ./ml/
COPY scripts/ ./scripts/

# Create runtime directories for persistent volumes with proper ownership
RUN mkdir -p /app/output/midi /app/output/audio /app/data /app/models \
    && chown -R studio:studio /app

# Switch to non-root user
USER studio

# Expose backend REST API port
EXPOSE 8000

# Health check against live endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production entrypoint with Uvicorn ASGI workers
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "2", "-b", "0.0.0.0:8000", "backend.main:app"]
