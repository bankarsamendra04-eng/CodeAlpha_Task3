"""Unit tests for Database operations, SQLAlchemy models, and generation history endpoints."""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.connection import SessionLocal, init_db, engine
from backend.database.models import (
    User,
    Project,
    Generation,
    GeneratedFile,
    Feedback,
    UsageMetric,
)


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Ensure database schema is created for test run."""
    init_db()


def test_models_crud_operations():
    """Verify CRUD operations across all six core SQLAlchemy models."""
    db = SessionLocal()
    try:
        # 1. User
        user = User(
            username=f"test_user_{datetime.now(timezone.utc).timestamp()}",
            email=f"user_{datetime.now(timezone.utc).timestamp()}@test.com",
            hashed_password="mock_hashed_secret_password_for_testing",
            role="USER",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.id is not None
        assert user.is_active is True
        assert user.hashed_password is not None
        assert user.role == "USER"

        # 2. Project
        project = Project(
            user_id=user.id,
            title="Meditation Album",
            description="Calm piano compositions",
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        assert project.id is not None
        assert project.user_id == user.id

        # 3. Generation
        gen = Generation(
            generation_id=f"gen_db_test_{int(datetime.now(timezone.utc).timestamp())}",
            user_id=user.id,
            project_id=project.id,
            prompt="Peaceful piano melody",
            prompt_parser="fallback_heuristics",
            interpreted_parameters={"mood": "peaceful", "instrument": "piano", "tempo": 70.0},
            model_version="lstm_v1",
            tempo_bpm=70.0,
            instrument="piano",
            musical_key="C",
            scale="major",
            temperature=0.65,
            num_events_generated=32,
            duration_quarter_lengths=8.0,
            generation_status="completed",
            generation_duration_ms=2500,
            midi_file_name="test.mid",
            midi_file_url="/api/music/download/midi/test.mid",
            midi_size_bytes=420,
            audio_status="skipped",
        )
        db.add(gen)
        db.commit()
        db.refresh(gen)
        assert gen.id is not None
        assert gen.generation_id.startswith("gen_db_test_")

        # 4. GeneratedFile
        gen_file = GeneratedFile(
            generation_id=gen.id,
            file_type="midi",
            filename="test.mid",
            download_url="/api/music/download/midi/test.mid",
            file_size_bytes=420,
            mime_type="audio/midi",
        )
        db.add(gen_file)
        db.commit()
        db.refresh(gen_file)
        assert gen_file.id is not None

        # 5. Feedback
        feedback = Feedback(
            generation_id=gen.id,
            user_id=user.id,
            rating=5,
            is_liked=True,
            comment="Wonderful soothing harmonics!",
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        assert feedback.rating == 5

        # 6. UsageMetric
        metric = UsageMetric(
            event_type="generation_completed",
            generation_duration_ms=2500,
            metadata_json={"instrument": "piano"},
        )
        db.add(metric)
        db.commit()
        db.refresh(metric)
        assert metric.event_type == "generation_completed"

    finally:
        db.close()


def test_api_generate_saves_to_database():
    """Verify that calling POST /api/music/generate records into database table."""
    client = TestClient(app)

    mock_tokens = ["NOTE_60_d0.50", "NOTE_62_d0.50", "NOTE_64_d1.00"]

    with patch("backend.services.music_pipeline.MusicGenerator") as mock_gen_cls:
        instance = mock_gen_cls.return_value
        instance.generate.return_value = mock_tokens

        response = client.post(
            "/api/music/generate",
            json={
                "prompt": "Test database persistence generation",
                "instrument": "violin",
                "tempo": 110.0,
                "render_audio": False,
            },
        )

        assert response.status_code == 200
        gen_id = response.json()["generation_id"]

        # Check in database
        db = SessionLocal()
        try:
            record = db.query(Generation).filter(Generation.generation_id == gen_id).first()
            assert record is not None
            assert record.instrument == "violin"
            assert record.tempo_bpm == 110.0
            assert record.generation_status == "completed"
            assert record.generation_duration_ms > 0
            assert record.midi_file_name.endswith(".mid")
        finally:
            db.close()


def test_get_generations_history_endpoint():
    """Verify GET /api/generations returns a paginated list of history records."""
    client = TestClient(app)
    response = client.get("/api/generations?page=1&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert data["page"] == 1
    assert data["limit"] == 10
    assert isinstance(data["items"], list)
    assert len(data["items"]) >= 1

    first_item = data["items"][0]
    assert "generation_id" in first_item
    assert "tempo_bpm" in first_item
    assert "midi_file" in first_item


def test_get_single_generation_by_id():
    """Verify GET /api/generations/{id} returns full detail of record."""
    client = TestClient(app)
    # First get latest from list
    list_res = client.get("/api/generations?limit=1")
    latest_gen_id = list_res.json()["items"][0]["generation_id"]

    # Query single
    res = client.get(f"/api/generations/{latest_gen_id}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["generation_id"] == latest_gen_id
    assert "interpreted_parameters" in detail
    assert "model_version" in detail


def test_get_single_generation_not_found():
    """Verify 404 is returned when querying a non-existent generation id."""
    client = TestClient(app)
    response = client.get("/api/generations/non_existent_gen_id_99999")
    assert response.status_code == 404