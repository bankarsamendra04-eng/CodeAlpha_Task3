# Production Deployment & Dockerization Guide — AI Music Studio

## 1. Overview

This document provides complete instructions for deploying **AI Music Studio** using Docker, Docker Compose, and traditional systemd/Nginx configurations. The architecture is engineered for low latency, reproducible environments, secure credential handling, and persistent data retention across container lifecycles.

---

## 2. Infrastructure & Container Topology

```
                       [ Host Browser / Client (Port 80) ]
                                        │
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │        Frontend Nginx Container         │
                   │    (Alpine Linux: Static SPA + Proxy)   │
                   └────────────┬────────────────────────────┘
                                │
                                │ /api/*, /health, /docs (Docker bridge network)
                                ▼
                   ┌─────────────────────────────────────────┐
                   │        Backend FastAPI Container        │
                   │    (Python 3.10-slim + FluidSynth)      │
                   └───────┬───────────────────┬─────────────┘
                           │                   │
           Persistent Data │                   │ Persistent Media & Models
                           ▼                   ▼
                  ┌─────────────────┐ ┌───────────────────────────┐
                  │ Volume: data    │ │ Volume: output            │
                  │ /app/data/*.db  │ │ /app/output/midi & audio  │
                  └─────────────────┘ └───────────────────────────┘
                                              ▲
                                              │ Host Mount (read-only)
                                      ┌───────┴───────────────────┐
                                      │ Host: ./models            │
                                      │ /app/models (Configurable)│
                                      └───────────────────────────┘
```

### Key Architectural Tenets
1. **Zero Dataset Bloat in Images**: The MAESTRO classical dataset (1,276 raw MIDI files and preprocessed arrays) is strictly ignored via `.dockerignore`. The image size remains lean (~600 MB vs > 10 GB).
2. **Zero Secret Leakage**: `.env` and credential files are strictly excluded from container images. Configurations are injected at runtime via Docker Compose environment variables.
3. **Configurable Model Location**: Models are decoupled from the build and mounted from the host system (`./models:/app/models:ro`), governed by the `MODEL_DIR` environment variable.
4. **Persistent State**: Compositions (`output/`) and the SQLite database (`data/`) live in dedicated Docker named volumes surviving container restarts and rebuilds.

---

## 3. Local Docker Commands & Quick Start

### 3.1 Prerequisites
- Docker Engine 24.0+
- Docker Compose v2.20+

### 3.2 Build and Launch Containers

```bash
# Clone the repository
git clone https://github.com/your-org/AI-Music-Studio.git
cd AI-Music-Studio

# Build Docker images
docker compose build

# Start services in the background (detached mode)
docker compose up -d
```

### 3.3 Verify Container Status & Health

```bash
# Check running containers and healthcheck states
docker compose ps

# Inspect live backend service logs
docker compose logs -f backend

# Inspect live frontend Nginx logs
docker compose logs -f frontend

# Test backend healthcheck from host
curl -i http://localhost:8000/health

# Test frontend web interface from host
curl -i http://localhost/
```

Access endpoints in your browser:
- **Web Studio Interface**: `http://localhost`
- **Interactive OpenAPI Documentation**: `http://localhost:8000/docs` or `http://localhost/docs`
- **System Healthcheck**: `http://localhost:8000/health` or `http://localhost/health`

### 3.4 Stopping & Maintenance

```bash
# Stop running containers gracefully
docker compose stop

# Stop and remove containers and network (preserves volumes)
docker compose down

# Stop and remove containers, networks, AND persistent volumes (clean wipe)
docker compose down -v
```

---

## 4. Container Files Deep Dive

### 4.1 Backend Dockerfile (`Dockerfile`)
- **Base**: `python:3.10-slim-bullseye`
- **System Dependencies**: `fluidsynth`, `fluid-soundfont-gm`, `ffmpeg`, `libsndfile1`, `curl`, `build-essential`.
- **Security**: Creates non-root system user `studio` (UID 1000) and executes with dropped privileges.
- **Process Manager**: Runs Gunicorn with Uvicorn worker threads (`uvicorn.workers.UvicornWorker`).
- **Healthcheck**: Regular HTTP GET probes to `/health` with automatic failure restarts.

### 4.2 Frontend Dockerfile (`frontend/Dockerfile`)
- **Multi-Stage Build**:
  - *Builder Stage*: Compiles the React SPA using `node:20-alpine` and `npm run build`.
  - *Runner Stage*: Deploys compiled assets into minimal `nginx:alpine` image.
- **Reverse Proxy**: Includes [`frontend/nginx.conf`](file:///c:/Users/banka/OneDrive/Desktop/CodAlpha%20Task%203/AI-Music-Studio/frontend/nginx.conf) to proxy `/api/` traffic directly to the internal `backend:8000` service without CORS friction.

### 4.3 Root Ignore Rules (`.dockerignore`)
Guarantees clean image layers by omitting:
```
dataset/               # Complete MAESTRO MIDI dataset (1,276 files)
*.mid, *.midi, *.npz   # Raw music tokens and audio
.env, .env.*           # Passwords, tokens, API keys
*.db, output/, data/   # Local databases and runtime outputs
venv/, node_modules/   # Host machine dependencies
__pycache__/, .git/    # Python bytecode and version control history
```

### 4.4 Multi-Container Orchestration (`docker-compose.yml`)
- **Services**:
  - `backend`: Exposes port 8000, runs ASGI server, mounts models and persistence volumes.
  - `frontend`: Exposes port 80, depends on `backend` healthy condition.
- **Volumes**:
  - `studio_data`: Maps to `/app/data` (holds `ai_music_studio.db`).
  - `studio_output`: Maps to `/app/output` (holds `midi/` and `audio/`).
  - Host mount `./models`: Maps to `/app/models:ro` (enables model hot-swapping).

---

## 5. Environment Variables & Model Path Configuration

All runtime variables can be set via `.env` or passed directly to Docker Compose:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite:////app/data/ai_music_studio.db` | Path to persistent SQLite file or PostgreSQL URI |
| `MODEL_DIR` | `/app/models` | Root directory for trained LSTM weights |
| `MODEL_VERSION` | `v1` | Version subfolder (loads `/app/models/lstm/v1/best_model.keras`) |
| `GROQ_API_KEY` | *(None / Fallback)* | Optional Groq Cloud API key for natural language understanding |
| `SECRET_KEY` | *(Generated string)* | HMAC-SHA256 signing key for JWT tokens |
| `ADMIN_EMAIL` | `admin@aimusicstudio.internal` | Auto-seeded admin user email |
| `ADMIN_PASSWORD`| `AdminSecurePassword123!` | Auto-seeded admin password |
| `SOUNDFONT_PATH`| `/usr/share/sounds/sf2/default-GM.sf2`| Container path to SoundFont GM bank |
| `FLUIDSYNTH_PATH`| `/usr/bin/fluidsynth` | Path to FluidSynth CLI executable |
| `ENFORCE_USAGE_LIMITS` | `true` | Enforces SaaS tier quotas |

---

## 6. Testing Container Configurations

Automated configuration and syntax tests are implemented in [`tests/test_docker_config.py`](file:///c:/Users/banka/OneDrive/Desktop/CodAlpha%20Task%203/AI-Music-Studio/tests/test_docker_config.py):

```bash
# Run Docker configuration verification tests
python -m pytest tests/test_docker_config.py -v
```

Tests verify:
1. All required container assets exist (`Dockerfile`, `frontend/Dockerfile`, `nginx.conf`, `docker-compose.yml`, `.dockerignore`).
2. `.dockerignore` strictly isolates `dataset/`, `*.mid`, and `.env` secrets.
3. Backend Dockerfile enforces non-root UID 1000 execution, FluidSynth libraries, and healthchecks.
4. Frontend Dockerfile uses multi-stage builds with Nginx reverse proxying.
5. Docker Compose specifies required services, persistent named volumes, and host-mounted model directories.
