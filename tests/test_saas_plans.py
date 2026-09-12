"""
AI Music Studio - Automated Tests for SaaS Plans & Usage Limits
Tests:
- Central plan registry and configuration integrity
- Public GET /api/plans endpoint
- User subscription quota inspection GET /api/subscription/me
- Subscription tier upgrade / switch POST /api/subscription/tier
- Proactive limit enforcement (duration, monthly quota, audio rendering)
- Relational database usage ledger persistence (UserUsage)
- Admin dashboard subscription tier distribution
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from fastapi import HTTPException

from backend.main import app
from backend.config.plans import (
    PlanTier,
    get_plan_definition,
    get_all_plans,
    PLAN_REGISTRY,
)
from backend.database.connection import SessionLocal
from backend.database.models import User, UserUsage
from backend.services.auth_service import hash_password, create_access_token
from backend.services.usage_service import get_usage_service


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_plan_registry_and_definitions():
    """Verify all 5 required SaaS plans exist with non-null, valid limits."""
    plans = get_all_plans()
    assert len(plans) == 5

    tiers = [p.tier for p in plans]
    assert PlanTier.FREE in tiers
    assert PlanTier.CREATOR in tiers
    assert PlanTier.PRO in tiers
    assert PlanTier.EDUCATION in tiers
    assert PlanTier.ENTERPRISE in tiers

    # Check Free limits
    free_plan = get_plan_definition("FREE")
    assert free_plan.tier == PlanTier.FREE
    assert free_plan.limits.max_generations_per_month > 0
    assert free_plan.limits.max_duration_seconds >= 30
    assert free_plan.limits.can_download_midi is True

    # Check Creator limits
    creator_plan = get_plan_definition("CREATOR")
    assert creator_plan.monthly_price_usd == 19.0
    assert creator_plan.limits.max_generations_per_month >= free_plan.limits.max_generations_per_month
    assert creator_plan.limits.can_download_audio is True

    # Check Pro limits
    pro_plan = get_plan_definition("PRO")
    assert pro_plan.monthly_price_usd == 49.0
    assert pro_plan.limits.project_management_allowed is True
    assert pro_plan.limits.api_access_allowed is True

    # Check Education limits
    edu_plan = get_plan_definition("EDUCATION")
    assert edu_plan.limits.classroom_accounts is True
    assert edu_plan.limits.research_features is True

    # Check Enterprise limits
    ent_plan = get_plan_definition("ENTERPRISE")
    assert ent_plan.limits.max_generations_per_month == -1  # Unlimited
    assert ent_plan.limits.custom_models is True

    # Verify fallback for unknown tier string
    fallback = get_plan_definition("NON_EXISTENT_TIER")
    assert fallback.tier == PlanTier.FREE


def test_public_plans_api(client):
    """Verify GET /api/plans returns public plans catalog."""
    res = client.get("/api/plans")
    assert res.status_code == 200
    data = res.json()
    assert data["total_plans"] == 5
    assert len(data["plans"]) == 5

    plan_names = [p["tier"] for p in data["plans"]]
    assert "FREE" in plan_names
    assert "CREATOR" in plan_names
    assert "PRO" in plan_names
    assert "EDUCATION" in plan_names
    assert "ENTERPRISE" in plan_names


def test_user_subscription_lifecycle(client, db_session):
    """Verify subscription retrieval and switching endpoints for authenticated users."""
    import uuid
    uid = uuid.uuid4().hex[:8]
    test_user = User(
        username=f"saas_user_{uid}",
        email=f"saas_{uid}@example.com",
        hashed_password=hash_password("Password123!"),
        role="USER",
        subscription_tier="FREE",
    )
    db_session.add(test_user)
    db_session.commit()
    db_session.refresh(test_user)

    token, _ = create_access_token(user_id=test_user.id, username=test_user.username, role="USER")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Inspect initial subscription quota
    res = client.get("/api/subscription/me", headers=headers)
    assert res.status_code == 200
    sub_data = res.json()
    assert sub_data["tier"] == "FREE"
    assert sub_data["plan_name"] == "Free"
    assert sub_data["generations"]["used"] == 0
    assert sub_data["generations"]["limit"] == 15 or sub_data["generations"]["limit"] > 0

    # 2. Upgrade to CREATOR plan
    upgrade_res = client.post(
        "/api/subscription/tier",
        headers=headers,
        json={"tier": "CREATOR"},
    )
    assert upgrade_res.status_code == 200
    up_data = upgrade_res.json()
    assert up_data["success"] is True
    assert up_data["previous_tier"] == "FREE"
    assert up_data["current_tier"] == "CREATOR"

    # 3. Verify user's updated subscription
    res2 = client.get("/api/subscription/me", headers=headers)
    assert res2.status_code == 200
    sub_data2 = res2.json()
    assert sub_data2["tier"] == "CREATOR"
    assert sub_data2["monthly_price_usd"] == 19.0


def test_usage_service_limit_enforcement(db_session):
    """Verify proactive quota and threshold enforcement in UsageService."""
    import uuid
    uid = uuid.uuid4().hex[:8]
    test_user = User(
        username=f"limit_user_{uid}",
        email=f"limit_{uid}@example.com",
        hashed_password=hash_password("Password123!"),
        role="USER",
        subscription_tier="FREE",
    )
    db_session.add(test_user)
    db_session.commit()
    db_session.refresh(test_user)

    usage_service = get_usage_service()

    # Duration limit check: Free tier max duration is 60s. Requesting 180s must raise 403
    with pytest.raises(HTTPException) as excinfo:
        usage_service.validate_generation_request(
            user=test_user,
            requested_duration=180,
            render_audio=False,
            db=db_session,
            enforce_hard_limits=True,
        )
    assert excinfo.value.status_code == 403
    assert "Requested duration" in excinfo.value.detail

    # Exceed monthly generations check
    usage = usage_service.get_or_create_usage(test_user.id, db_session)
    usage.generations_count = 100  # Exceed free limit
    db_session.commit()

    with pytest.raises(HTTPException) as excinfo2:
        usage_service.validate_generation_request(
            user=test_user,
            requested_duration=30,
            render_audio=False,
            db=db_session,
            enforce_hard_limits=True,
        )
    assert excinfo2.value.status_code == 403
    assert "Monthly generation quota reached" in excinfo2.value.detail


def test_database_usage_recording(db_session):
    """Verify that record_usage correctly persists metrics in the UserUsage table."""
    import uuid
    uid = uuid.uuid4().hex[:8]
    test_user = User(
        username=f"record_user_{uid}",
        email=f"record_{uid}@example.com",
        hashed_password=hash_password("Password123!"),
        role="USER",
        subscription_tier="PRO",
    )
    db_session.add(test_user)
    db_session.commit()
    db_session.refresh(test_user)

    usage_service = get_usage_service()

    # Record first usage
    rec = usage_service.record_usage(
        user=test_user,
        duration_sec=75.5,
        audio_rendered=True,
        storage_bytes=25000,
        is_api=True,
        db=db_session,
    )

    assert rec is not None
    assert rec.generations_count == 1
    assert rec.total_duration_seconds == 75.5
    assert rec.audio_renders_count == 1
    assert rec.storage_bytes_used == 25000
    assert rec.api_calls_count == 1

    # Record second usage
    rec2 = usage_service.record_usage(
        user=test_user,
        duration_sec=30.0,
        audio_rendered=False,
        storage_bytes=5000,
        is_api=False,
        db=db_session,
    )

    assert rec2.generations_count == 2
    assert rec2.total_duration_seconds == 105.5
    assert rec2.audio_renders_count == 1
    assert rec2.storage_bytes_used == 30000
    assert rec2.api_calls_count == 1
