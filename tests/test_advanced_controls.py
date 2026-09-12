"""Unit tests for Advanced Music Generation Controls and overriding logic."""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch

from backend.main import app
from backend.schemas.music import MusicParameters, LevelEnum


def test_schema_clamping_and_validation():
    """Verify backend sanitization strictly clamps out-of-bounds numbers."""
    params = MusicParameters(
        tempo=450.0,            # Beyond 240
        duration_seconds=1200,  # Beyond 600
        key="G#",
        scale="minor",
        complexity=LevelEnum.HIGH,
    )
    assert params.tempo == 240.0
    assert params.duration_seconds == 600
    assert params.key == "G#"
    assert params.scale == "minor"

    # Lower bounds
    params_low = MusicParameters(
        tempo=10.0,
        duration_seconds=2,
    )
    assert params_low.tempo == 40.0
    assert params_low.duration_seconds == 10


def test_explicit_user_controls_override_prompt_suggestions():
    """Verify that explicit controls take priority over Groq/prompt parsed values."""
    client = TestClient(app)

    mock_tokens = ["NOTE_60_d0.50", "NOTE_62_d0.50", "CHORD_64.67_d1.00"]

    with patch("backend.services.music_pipeline.MusicGenerator") as mock_gen_cls:
        instance = mock_gen_cls.return_value
        instance.generate.return_value = mock_tokens

        # User prompt asks for guitar at 60 bpm, but explicitly requests violin at 145 bpm in D minor!
        response = client.post(
            "/api/music/generate",
            json={
                "prompt": "Peaceful acoustic guitar at 60 BPM",
                "instrument": "violin",
                "tempo": 145.0,
                "key": "D",
                "scale": "minor",
                "complexity": "high",
                "temperature": 1.25,
                "random_seed": 777,
                "render_audio": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Explicit overrides must be reflected
        assert data["metadata"]["instrument"] == "violin"
        assert data["metadata"]["tempo_bpm"] == 145.0
        assert data["metadata"]["key"] == "D"
        assert data["metadata"]["scale"] == "minor"
        assert data["metadata"]["temperature_used"] == 1.25

        overrides = data["metadata"]["user_overrides_applied"]
        assert overrides["instrument"] == "violin"
        assert overrides["tempo"] == 145.0
        assert overrides["key"] == "D"
        assert overrides["scale"] == "minor"
        assert overrides["temperature"] == 1.25


def test_pure_controls_without_prompt():
    """Verify music can be generated using advanced controls alone (Option B)."""
    client = TestClient(app)

    mock_tokens = ["NOTE_65_d1.00", "NOTE_67_d1.00"]

    with patch("backend.services.music_pipeline.MusicGenerator") as mock_gen_cls:
        instance = mock_gen_cls.return_value
        instance.generate.return_value = mock_tokens

        response = client.post(
            "/api/music/generate",
            json={
                "mood": "mysterious",
                "instrument": "pipe organ",
                "tempo": 90.0,
                "key": "A",
                "scale": "minor",
                "render_audio": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metadata"]["instrument"] == "pipe organ"
        assert data["metadata"]["interpreted_parameters"]["mood"] == "mysterious"
        assert data["metadata"]["key"] == "A"
        assert data["metadata"]["scale"] == "minor"
        assert data["metadata"]["prompt_parser"] == "manual_controls_only"


def test_empty_request_rejected():
    """Verify that an empty request with neither prompt nor controls is rejected."""
    client = TestClient(app)
    response = client.post("/api/music/generate", json={})
    assert response.status_code == 400