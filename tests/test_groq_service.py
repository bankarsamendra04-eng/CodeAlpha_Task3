"""Unit tests for Groq prompt interpretation service and music schemas."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.schemas.music import (
    MusicPromptRequest,
    MusicParameters,
    MusicPromptResponse,
    LevelEnum,
)
from backend.services.groq_service import GroqMusicService
from backend.main import app


def test_music_parameters_validation_and_sanitization():
    """Verify MusicParameters sanitizes tempos, instruments, and durations."""
    # Test extreme tempo clamping
    params = MusicParameters(
        mood="peaceful",
        instrument="Electric Piano",
        style="meditation",
        tempo=350.0,  # Exceeds max 240
        duration_seconds=900,  # Exceeds max 600
    )
    assert params.tempo == 240.0
    assert params.duration_seconds == 600
    assert params.instrument == "electric piano"

    # Test lower bound clamping
    params_low = MusicParameters(
        tempo=15.0,  # Below min 40
        duration_seconds=2,  # Below min 10
    )
    assert params_low.tempo == 40.0
    assert params_low.duration_seconds == 10


def test_groq_service_fallback_heuristic_peaceful():
    """Verify fallback parser extracts mood, tempo, and instrument from natural text."""
    service = GroqMusicService(api_key=None)
    prompt = "Create a peaceful piano melody for meditation at 70 BPM."
    response = service.interpret_prompt(prompt)

    assert response.success is True
    assert response.parameters.mood == "peaceful"
    assert response.parameters.instrument == "piano"
    assert response.parameters.tempo == 70.0
    assert response.parameters.complexity == LevelEnum.LOW
    assert response.suggested_temperature < 0.8
    assert response.fallback_used is True


def test_groq_service_fallback_heuristic_energetic_guitar():
    """Verify fallback parser handles fast energetic tempo and instruments."""
    service = GroqMusicService(api_key=None)
    prompt = "A fast and energetic acoustic guitar solo with complex virtuoso rhythm at 140 bpm for 90 seconds"
    response = service.interpret_prompt(prompt)

    assert response.success is True
    assert response.parameters.mood == "energetic"
    assert "guitar" in response.parameters.instrument
    assert response.parameters.tempo == 140.0
    assert response.parameters.complexity == LevelEnum.HIGH
    assert response.parameters.duration_seconds == 90
    assert response.suggested_temperature >= 0.9


def test_groq_service_api_mock():
    """Verify that when Groq returns valid JSON, it is parsed and validated cleanly."""
    mock_json = """
    {
        "mood": "mysterious",
        "instrument": "violin",
        "style": "cinematic",
        "tempo": 84,
        "complexity": "medium",
        "energy": "medium",
        "duration_seconds": 45
    }
    """
    service = GroqMusicService(api_key="gsk_mock_test_key_12345")
    service._client = MagicMock()
    with patch.object(service, "_call_groq_api", return_value=mock_json):
        res = service.interpret_prompt("A mysterious cinematic violin soundtrack")

        assert res.success is True
        assert res.parameters.mood == "mysterious"
        assert res.parameters.instrument == "violin"
        assert res.parameters.style == "cinematic"
        assert res.parameters.tempo == 84.0
        assert res.parameters.duration_seconds == 45
        assert res.fallback_used is False


def test_groq_service_graceful_on_api_exception():
    """Verify that an API error safely triggers fallback parser without raising unhandled exceptions."""
    service = GroqMusicService(api_key="gsk_mock_test_key_12345")
    service._client = MagicMock()
    with patch.object(service, "_call_groq_api", side_effect=RuntimeError("Groq Rate Limit Exceeded")):
        res = service.interpret_prompt("A peaceful flute tune at 75 BPM")

        assert res.success is True
        assert res.parameters.instrument == "flute"
        assert res.parameters.tempo == 75.0
        assert res.fallback_used is True


def test_api_endpoint_interpret():
    """Test FastAPI /api/prompt/interpret endpoint."""
    client = TestClient(app)
    response = client.post(
        "/api/prompt/interpret",
        json={"prompt": "Create a peaceful piano melody for meditation at 70 BPM."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["parameters"]["tempo"] == 70.0
    assert data["parameters"]["instrument"] == "piano"
    assert "suggested_temperature" in data