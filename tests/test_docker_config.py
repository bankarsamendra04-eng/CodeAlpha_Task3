"""
AI Music Studio - Automated Docker Configuration Verification Tests
Validates:
- Presence and syntax of Dockerfiles, docker-compose.yml, nginx.conf, and .dockerignore
- Strict exclusion of raw datasets (MAESTRO) and .env secrets from images
- Correct multi-container service architecture (backend, frontend)
- Persistent volume declarations (database, output files, models)
- Configurable model location and environment variable usage
"""

import pytest
import re
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_docker_files_exist():
    """Verify all container configuration assets exist."""
    dockerfile_backend = PROJECT_ROOT / "Dockerfile"
    dockerfile_frontend = PROJECT_ROOT / "frontend" / "Dockerfile"
    nginx_conf = PROJECT_ROOT / "frontend" / "nginx.conf"
    docker_compose = PROJECT_ROOT / "docker-compose.yml"
    dockerignore = PROJECT_ROOT / ".dockerignore"
    frontend_dockerignore = PROJECT_ROOT / "frontend" / ".dockerignore"

    assert dockerfile_backend.exists(), "Root backend Dockerfile missing"
    assert dockerfile_frontend.exists(), "Frontend Dockerfile missing"
    assert nginx_conf.exists(), "Frontend nginx.conf missing"
    assert docker_compose.exists(), "docker-compose.yml missing"
    assert dockerignore.exists(), "Root .dockerignore missing"
    assert frontend_dockerignore.exists(), "Frontend .dockerignore missing"


def test_dockerignore_excludes_dataset_and_secrets():
    """Verify .dockerignore strictly excludes the MAESTRO dataset and secret files."""
    dockerignore_path = PROJECT_ROOT / ".dockerignore"
    content = dockerignore_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

    # Dataset isolation: Ensure dataset and raw MIDI files are ignored
    assert any("dataset" in l for l in lines), "dataset/ must be ignored in .dockerignore"
    assert any("*.mid" in l for l in lines), "*.mid files must be ignored in .dockerignore"

    # Secret isolation: Ensure .env is ignored
    assert any(".env" in l for l in lines), ".env must be ignored in .dockerignore"

    # Dev artifacts isolation
    assert any("venv" in l for l in lines), "venv must be ignored in .dockerignore"
    assert any("node_modules" in l for l in lines), "node_modules must be ignored in .dockerignore"
    assert any("*.db" in l for l in lines), "*.db database files must be ignored in .dockerignore"


def test_backend_dockerfile_configuration():
    """Verify backend Dockerfile layers, security user, healthcheck, and synthesis packages."""
    content = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    # Base image check
    assert "python:3.10-slim" in content, "Must use Python 3.10 slim base"

    # Audio synthesis dependencies
    assert "fluidsynth" in content, "FluidSynth package must be installed"
    assert "fluid-soundfont-gm" in content, "SoundFont package must be installed"
    assert "libsndfile1" in content, "libsndfile package must be installed"

    # OWASP least-privilege non-root user
    assert re.search(r"useradd.*studio", content), "Must define non-root user 'studio'"
    assert "USER studio" in content, "Must switch to non-root user before execution"

    # Configurable model directory environment variable
    assert "MODEL_DIR" in content, "Must specify configurable MODEL_DIR"

    # Health check & port
    assert "HEALTHCHECK" in content, "Must define health check"
    assert "EXPOSE 8000" in content, "Must expose backend port 8000"


def test_frontend_dockerfile_and_nginx():
    """Verify frontend multi-stage build and Nginx reverse proxy configuration."""
    dockerfile_content = (PROJECT_ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    nginx_content = (PROJECT_ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")

    # Multi-stage build check
    assert "AS builder" in dockerfile_content, "Frontend must use multi-stage builder"
    assert "nginx:alpine" in dockerfile_content, "Frontend runner must use nginx:alpine"
    assert "EXPOSE 80" in dockerfile_content, "Frontend must expose port 80"

    # Nginx reverse proxy routes
    assert "location /api/" in nginx_content, "nginx.conf must proxy /api/"
    assert "proxy_pass http://backend:8000/api/;" in nginx_content
    assert "location /health" in nginx_content, "nginx.conf must proxy /health"
    assert "try_files $uri $uri/ /index.html;" in nginx_content, "SPA routing fallback required"


def test_docker_compose_structure():
    """Verify docker-compose.yml defines required services, networks, and persistent volumes."""
    compose_path = PROJECT_ROOT / "docker-compose.yml"
    content = compose_path.read_text(encoding="utf-8")

    # Required services
    assert "backend:" in content, "compose must define backend service"
    assert "frontend:" in content, "compose must define frontend service"

    # Persistent volumes for database and output files
    assert "studio_data:" in content, "compose must define persistent studio_data volume"
    assert "studio_output:" in content, "compose must define persistent studio_output volume"

    # Configurable model directory mounted from host
    assert "./models:/app/models:ro" in content, "Host models directory must be mounted read-only"

    # Configurable environment variables without hardcoded secrets
    assert "MODEL_DIR" in content, "MODEL_DIR must be passed to backend"
    assert "DATABASE_URL" in content, "DATABASE_URL must be configured"
    assert "${GROQ_API_KEY" in content, "GROQ_API_KEY must use environment variable injection"
    assert "${SECRET_KEY" in content, "SECRET_KEY must use environment variable injection"

    # Service dependency
    assert "depends_on:" in content, "frontend must depend on backend"
