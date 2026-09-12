"""Unit tests for User Authentication, Password Hashing, JWT Tokens, and RBAC."""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.connection import SessionLocal, init_db
from backend.database.models import User, Generation
from backend.services.auth_service import hash_password, verify_password


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


def test_password_hashing_security():
    """Verify passwords are never stored plaintext and verify correctly with bcrypt."""
    pw = "SuperSecret#2026"
    hashed = hash_password(pw)
    assert hashed != pw
    assert hashed.startswith("$2b$")
    assert verify_password(pw, hashed) is True
    assert verify_password("IncorrectPassword", hashed) is False


def test_user_registration_and_login_flow():
    """Test full registration, login, and JWT retrieval flow."""
    client = TestClient(app)
    ts = int(datetime.now(timezone.utc).timestamp())
    username = f"creator_{ts}"
    email = f"creator_{ts}@musicstudio.io"
    password = "CreatorSecretPass123"

    # 1. Register
    reg_res = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "role": "USER",
        },
    )
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert "access_token" in reg_data
    assert reg_data["user"]["username"] == username
    assert reg_data["user"]["role"] == "USER"
    assert "hashed_password" not in reg_data["user"]

    # 2. Duplicate Registration Rejection
    dup_res = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )
    assert dup_res.status_code == 400

    # 3. Login with correct credentials
    login_res = client.post(
        "/api/auth/login",
        json={
            "username": username,
            "password": password,
        },
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    assert token is not None

    # 4. Login with invalid password
    bad_login = client.post(
        "/api/auth/login",
        json={
            "username": username,
            "password": "WrongPassword!",
        },
    )
    assert bad_login.status_code == 401

    # 5. Access Protected Profile /api/auth/me
    profile_res = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert profile_res.status_code == 200
    assert profile_res.json()["username"] == username


def test_rbac_admin_endpoint_protection():
    """Verify that USER role is forbidden from ADMIN endpoints, and ADMIN role is allowed."""
    client = TestClient(app)
    ts = int(datetime.now(timezone.utc).timestamp())

    # Create normal USER
    user_res = client.post(
        "/api/auth/register",
        json={
            "username": f"regular_{ts}",
            "email": f"regular_{ts}@test.com",
            "password": "Pass12345Password",
            "role": "USER",
        },
    )
    user_token = user_res.json()["access_token"]

    # Attempt to create ADMIN user without code -> 403 Forbidden
    unauthorized_admin = client.post(
        "/api/auth/register",
        json={
            "username": f"fake_admin_{ts}",
            "email": f"fake_admin_{ts}@test.com",
            "password": "AdminPass12345!",
            "role": "ADMIN",
        },
    )
    assert unauthorized_admin.status_code == 403

    # Create verified ADMIN user with valid code
    admin_res = client.post(
        "/api/auth/register",
        json={
            "username": f"admin_{ts}",
            "email": f"admin_{ts}@test.com",
            "password": "AdminPass12345!",
            "role": "ADMIN",
            "admin_invite_code": "AdminStudioSecret#2026",
        },
    )
    assert admin_res.status_code == 201
    admin_token = admin_res.json()["access_token"]
    assert admin_res.json()["user"]["role"] == "ADMIN"

    # 1. Unauthenticated request to /api/admin/metrics -> 401
    unauth = client.get("/api/admin/metrics")
    assert unauth.status_code == 401

    # 2. Regular user request to /api/admin/metrics -> 403 Forbidden
    forbidden = client.get(
        "/api/admin/metrics",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert forbidden.status_code == 403

    # 3. Admin user request to /api/admin/metrics -> 200 OK
    allowed = client.get(
        "/api/admin/metrics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert allowed.status_code == 200
    metrics = allowed.json()
    assert metrics["admin_username"] == f"admin_{ts}"
    assert "total_generations" in metrics


def test_user_generation_isolation():
    """Verify that users can only view their own generation records."""
    client = TestClient(app)
    ts = int(datetime.now(timezone.utc).timestamp())

    # User A
    user_a = client.post(
        "/api/auth/register",
        json={"username": f"usera_{ts}", "email": f"usera_{ts}@t.com", "password": "Pass123Password"},
    ).json()
    token_a = user_a["access_token"]
    id_a = user_a["user"]["id"]

    # User B
    user_b = client.post(
        "/api/auth/register",
        json={"username": f"userb_{ts}", "email": f"userb_{ts}@t.com", "password": "Pass123Password"},
    ).json()
    token_b = user_b["access_token"]

    # Create a generation belonging directly to User A
    db = SessionLocal()
    gen_a_id = f"gen_isolation_{ts}"
    try:
        gen = Generation(
            generation_id=gen_a_id,
            user_id=id_a,
            prompt="User A private piece",
            tempo_bpm=120.0,
            instrument="piano",
            generation_status="completed",
        )
        db.add(gen)
        db.commit()
    finally:
        db.close()

    # User A accesses their own generation -> 200 OK
    res_a = client.get(
        f"/api/generations/{gen_a_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_a.status_code == 200

    # User B attempts to access User A's generation -> 403 Forbidden
    res_b = client.get(
        f"/api/generations/{gen_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b.status_code == 403

    # Unauthenticated user accesses User A's generation -> 401 Unauthorized
    res_anon = client.get(f"/api/generations/{gen_a_id}")
    assert res_anon.status_code == 401