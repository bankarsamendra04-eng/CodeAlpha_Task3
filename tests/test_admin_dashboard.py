"""
AI Music Studio - Admin Dashboard & Analytics Unit Tests
Tests all 11 admin intelligence requirements:
1. Total users
2. Total generations
3. Generations today
4. Successful generations
5. Failed generations
6. API usage
7. Model version
8. Dataset status
9. Recent generations
10. User feedback
11. System errors
Plus role protection (401 without token, 403 with USER role, 200 with ADMIN role).
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import patch

from backend.main import app
from backend.database.connection import SessionLocal, init_db
from backend.database.models import (
    User,
    Generation,
    Feedback,
    UsageMetric,
)
from backend.services.auth_service import hash_password, create_access_token


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Initialize DB schema before tests."""
    init_db()


@pytest.fixture
def test_users():
    """Create test admin and normal user accounts with JWT tokens."""
    db = SessionLocal()
    try:
        ts = int(datetime.now(timezone.utc).timestamp())
        admin_username = f"admin_dash_{ts}"
        admin = User(
            username=admin_username,
            email=f"{admin_username}@studio.ai",
            hashed_password=hash_password("AdminSecurePass!"),
            role="ADMIN",
        )
        user_username = f"user_dash_{ts}"
        user = User(
            username=user_username,
            email=f"{user_username}@studio.ai",
            hashed_password=hash_password("UserRegularPass!"),
            role="USER",
        )
        db.add(admin)
        db.add(user)
        db.commit()
        db.refresh(admin)
        db.refresh(user)

        admin_token, _ = create_access_token(admin.id, admin.username, "ADMIN")
        user_token, _ = create_access_token(user.id, user.username, "USER")

        return {
            "admin": admin,
            "admin_token": admin_token,
            "user": user,
            "user_token": user_token,
        }
    finally:
        db.close()


def test_admin_dashboard_security_rbac(test_users):
    """Admin dashboard must deny unauthenticated users (401) and normal users (403)."""
    client = TestClient(app)

    # 1. Unauthenticated -> 401
    res1 = client.get("/api/admin/dashboard")
    assert res1.status_code == 401

    # 2. Authenticated as regular USER -> 403 Forbidden
    res2 = client.get(
        "/api/admin/dashboard",
        headers={"Authorization": f"Bearer {test_users['user_token']}"},
    )
    assert res2.status_code == 403
    assert "Administrative privileges required" in res2.json()["detail"]

    # 3. Authenticated as ADMIN -> 200 OK
    res3 = client.get(
        "/api/admin/dashboard",
        headers={"Authorization": f"Bearer {test_users['admin_token']}"},
    )
    assert res3.status_code == 200


def test_admin_dashboard_live_data_integrity(test_users):
    """
    Verify all 11 requested items return authentic database information:
    1. Total users
    2. Total generations
    3. Generations today
    4. Successful generations
    5. Failed generations
    6. API usage
    7. Model version
    8. Dataset status
    9. Recent generations
    10. User feedback
    11. System errors
    """
    client = TestClient(app)
    db = SessionLocal()

    # Seed one test generation, one error generation, and one feedback entry
    gen_success_id = f"gen_dash_ok_{int(datetime.now(timezone.utc).timestamp())}"
    gen_failed_id = f"gen_dash_err_{int(datetime.now(timezone.utc).timestamp())}"
    try:
        ok_gen = Generation(
            generation_id=gen_success_id,
            user_id=test_users["user"].id,
            prompt="Sunny acoustic guitar melody",
            prompt_parser="groq_llm",
            interpreted_parameters={"mood": "cheerful", "instrument": "acoustic guitar"},
            model_version="lstm_v1",
            tempo_bpm=110.0,
            instrument="acoustic guitar",
            generation_status="completed",
            generation_duration_ms=1850,
            midi_file_name="guitar_ok.mid",
            midi_file_url="/api/music/download/midi/guitar_ok.mid",
            audio_status="skipped",
        )
        fail_gen = Generation(
            generation_id=gen_failed_id,
            user_id=test_users["user"].id,
            prompt="Experimental polytonal organ",
            prompt_parser="fallback_heuristics",
            interpreted_parameters={"instrument": "pipe organ"},
            model_version="lstm_v1",
            tempo_bpm=90.0,
            instrument="pipe organ",
            generation_status="failed",
            generation_duration_ms=450,
            error_info="Simulated LSTM token inference out-of-bounds error",
        )
        db.add(ok_gen)
        db.add(fail_gen)
        db.commit()
        db.refresh(ok_gen)

        # Seed feedback
        fb = Feedback(
            generation_id=ok_gen.id,
            user_id=test_users["user"].id,
            rating=5,
            is_liked=True,
            comment="Exemplary harmonization and guitar acoustics!",
        )
        db.add(fb)

        # Seed usage metric
        metric = UsageMetric(
            event_type="download_midi",
            metadata_json={"filename": "guitar_ok.mid"},
        )
        db.add(metric)
        db.commit()
    finally:
        db.close()

    # Query admin dashboard
    response = client.get(
        "/api/admin/dashboard",
        headers={"Authorization": f"Bearer {test_users['admin_token']}"},
    )
    assert response.status_code == 200
    data = response.json()

    # Item 1: Total users
    assert data["total_users"] >= 2

    # Items 2, 3, 4, 5: Generation counts
    stats = data["generations_stats"]
    assert stats["total"] >= 2
    assert stats["today"] >= 2
    assert stats["successful"] >= 1
    assert stats["failed"] >= 1
    assert 0.0 <= stats["success_rate_percent"] <= 100.0

    # Item 6: API Usage
    api_use = data["api_usage"]
    assert api_use["total_api_calls"] >= 2
    assert api_use["midi_downloads"] >= 1

    # Item 7: Model Version
    model = data["model_info"]
    assert model["version"] == "v1"
    assert "LSTM" in model["architecture"]
    assert model["vocabulary_tokens"] > 0
    assert model["training_status"] == "trained_and_deployed"

    # Item 8: Dataset Status
    dataset = data["dataset_status"]
    assert "MAESTRO" in dataset["name"]
    assert dataset["status"] == "healthy"
    assert dataset["total_midi_files"] == 1276
    assert dataset["total_notes"] == 6512506
    assert "train" in dataset["splits"]

    # Item 9: Recent Generations
    recent = data["recent_generations"]
    assert len(recent) >= 2
    found_ok = any(r["generation_id"] == gen_success_id for r in recent)
    assert found_ok is True

    # Item 10: User Feedback (STEP 24 Detailed Assertions)
    feedback_list = data["feedback"]
    assert len(feedback_list) >= 1
    assert any(f["rating"] == 5 for f in feedback_list)
    assert data["avg_rating"] is not None
    assert data["total_feedback_count"] >= 1
    assert data["likes_count"] >= 1
    assert "dislikes_count" in data
    assert isinstance(data["common_feedback_words"], list)
    # Check that common terms from 'Exemplary harmonization and guitar acoustics!' are extracted
    extracted_words = [w["word"].lower() for w in data["common_feedback_words"]]
    assert any(term in extracted_words for term in ["harmonization", "guitar", "acoustics", "exemplary"])

    # Item 11: System Errors
    errors = data["system_errors"]
    assert len(errors) >= 1
    found_err = any(e["generation_id"] == gen_failed_id for e in errors)
    assert found_err is True
    assert any("out-of-bounds" in e["error_info"] for e in errors)

    # Basic Charts & Statistics
    assert len(data["daily_trend"]) == 7
    assert len(data["instrument_distribution"]) >= 1


def test_feedback_submission_endpoint(test_users):
    """Verify POST /api/feedback saves user review and reflects in admin dashboard."""
    client = TestClient(app)

    # First fetch a valid generation id
    dash_res = client.get(
        "/api/admin/dashboard",
        headers={"Authorization": f"Bearer {test_users['admin_token']}"},
    )
    gen_id = dash_res.json()["recent_generations"][0]["generation_id"]

    res = client.post(
        "/api/feedback",
        headers={"Authorization": f"Bearer {test_users['user_token']}"},
        json={
            "generation_id": gen_id,
            "rating": 4,
            "is_liked": True,
            "comment": "Very relaxing tempo and good phrasing.",
        },
    )
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert "feedback_id" in res.json()
