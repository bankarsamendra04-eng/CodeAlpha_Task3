"""Unit tests for the end-to-end music generation pipeline and API endpoints."""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from backend.main import app
from backend.schemas.music import MusicParameters, LevelEnum


def test_generate_endpoint_validation_short_prompt():
    """Verify that requests without minimum length or controls are rejected (400 or 422)."""
    client = TestClient(app)
    response = client.post("/api/music/generate", json={"prompt": "hi"})
    assert response.status_code in (400, 422)


def test_generate_endpoint_mocked_generation(tmp_path: Path):
    """Test full pipeline endpoint execution with mocked LSTM generator for speed and isolation."""
    client = TestClient(app)

    mock_tokens = [
        "NOTE_60_d0.50",
        "NOTE_62_d0.50",
        "CHORD_64.67_d1.00",
        "REST_d0.50",
        "NOTE_72_d1.00",
    ]

    from backend.services.music_pipeline import get_music_pipeline
    pipeline = get_music_pipeline()
    mock_gen = MagicMock()
    mock_gen.generate.return_value = mock_tokens
    with patch.object(pipeline, "_get_generator", return_value=mock_gen):
        response = client.post(
            "/api/music/generate",
            json={
                "prompt": "Create a peaceful piano melody for meditation at 70 BPM",
                "render_audio": False,
                "random_seed": 123,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["generation_id"].startswith("gen_")
        assert data["metadata"]["prompt"] == "Create a peaceful piano melody for meditation at 70 BPM"
        assert data["metadata"]["tempo_bpm"] == 70.0
        assert data["metadata"]["instrument"] == "piano"
        assert data["metadata"]["notes_count"] == 3
        assert data["metadata"]["chords_count"] == 1
        assert data["midi_file"]["filename"].endswith(".mid")
        assert "/api/music/download/midi/" in data["midi_file"]["download_url"]
        assert data["audio_status"] == "skipped"


def test_download_midi_endpoint_not_found():
    """Verify 404 is returned when requesting a non-existent MIDI file."""
    client = TestClient(app)
    response = client.get("/api/music/download/midi/non_existent_file_12345.mid")
    assert response.status_code == 404


def test_download_audio_endpoint_not_found():
    """Verify 404 is returned when requesting a non-existent audio file."""
    client = TestClient(app)
    response = client.get("/api/music/download/audio/non_existent_file_12345.wav")
    assert response.status_code == 404


def test_openapi_schema_endpoint():
    """Verify OpenAPI specification exposes /api/music/generate with detailed schemas."""
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert "/api/music/generate" in spec["paths"]
    assert "post" in spec["paths"]["/api/music/generate"]
    assert "/api/music/download/midi/{filename}" in spec["paths"]