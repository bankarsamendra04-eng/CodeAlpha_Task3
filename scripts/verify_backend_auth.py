"""
Real API Verification for Backend Authentication System.
Covers all requested test scenarios:
1. Successful registration (USER)
2. Duplicate registration (400 Bad Request)
3. Invalid credentials login (401 Unauthorized)
4. Successful user login (200 OK + JWT)
5. Successful admin login (200 OK + JWT)
6. Unauthorized protected request (401 / 403)
7. Authenticated user request (200 OK)
8. Authenticated admin request (200 OK to /api/admin/metrics & /api/admin/dashboard)
9. Server-side ADMIN role privilege escalation prevention without code (403 Forbidden)
"""

import sys
import time
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    print("=" * 70)
    print("BACKEND AUTHENTICATION REAL API VERIFICATION")
    print("=" * 70)

    results = {}
    ts = int(time.time())
    new_username = f"creator_{ts}"
    new_email = f"creator_{ts}@musicstudio.io"
    new_password = "CreatorSecret#2026"

    # -------------------------------------------------------------------------
    # 1. Successful Registration (USER)
    # -------------------------------------------------------------------------
    print("\n[1] Testing Successful Registration (USER)...")
    reg_res = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": new_username,
        "email": new_email,
        "password": new_password,
        "role": "USER",
    })
    print(f"  Status: {reg_res.status_code}")
    reg_json = reg_res.json()
    assert reg_res.status_code == 201, f"Expected 201, got {reg_res.status_code}: {reg_json}"
    assert "access_token" in reg_json
    assert reg_json["user"]["username"] == new_username
    assert reg_json["user"]["role"] == "USER"
    assert "hashed_password" not in reg_json["user"]
    print(f"  Registered User ID: {reg_json['user']['id']}, Role: {reg_json['user']['role']}")
    print(f"  Token: {reg_json['access_token'][:25]}... (length: {len(reg_json['access_token'])})")
    results["1. Successful Registration"] = f"PASS (Status 201, Role: {reg_json['user']['role']})"

    # -------------------------------------------------------------------------
    # 2. Duplicate Registration
    # -------------------------------------------------------------------------
    print("\n[2] Testing Duplicate Registration Rejection...")
    dup_res = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": new_username,
        "email": new_email,
        "password": new_password,
    })
    print(f"  Status: {dup_res.status_code}, Body: {dup_res.json()}")
    assert dup_res.status_code == 400
    assert "already registered" in dup_res.json().get("detail", "")
    results["2. Duplicate Registration"] = f"PASS (Status 400: '{dup_res.json()['detail']}')"

    # -------------------------------------------------------------------------
    # 3. Invalid Credentials
    # -------------------------------------------------------------------------
    print("\n[3] Testing Invalid Credentials Login...")
    inv_res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": new_username,
        "password": "WrongPassword#123",
    })
    print(f"  Status: {inv_res.status_code}, Body: {inv_res.json()}")
    assert inv_res.status_code == 401
    assert "Invalid username or password" in inv_res.json().get("detail", "")
    results["3. Invalid Credentials"] = f"PASS (Status 401: '{inv_res.json()['detail']}')"

    # -------------------------------------------------------------------------
    # 4. Successful User Login
    # -------------------------------------------------------------------------
    print("\n[4] Testing Successful User Login...")
    user_login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": new_username,
        "password": new_password,
    })
    print(f"  Status: {user_login_res.status_code}")
    user_login_json = user_login_res.json()
    assert user_login_res.status_code == 200
    user_token = user_login_json["access_token"]
    assert user_login_json["user"]["role"] == "USER"
    results["4. Successful User Login"] = f"PASS (Status 200, Role: USER, Token issued)"

    # -------------------------------------------------------------------------
    # 5. Successful Admin Login
    # -------------------------------------------------------------------------
    print("\n[5] Testing Successful Admin Login...")
    admin_login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "AdminPass123!",
    })
    print(f"  Status: {admin_login_res.status_code}")
    admin_login_json = admin_login_res.json()
    assert admin_login_res.status_code == 200
    admin_token = admin_login_json["access_token"]
    assert admin_login_json["user"]["role"] == "ADMIN"
    results["5. Successful Admin Login"] = f"PASS (Status 200, Role: ADMIN, Token issued)"

    # -------------------------------------------------------------------------
    # 6. Unauthorized Protected Request
    # -------------------------------------------------------------------------
    print("\n[6] Testing Unauthorized Protected Request...")
    # A. No token to protected /api/auth/me -> 401
    anon_res = requests.get(f"{BASE_URL}/api/auth/me")
    print(f"  Unauthenticated /api/auth/me: Status {anon_res.status_code}")
    assert anon_res.status_code == 401

    # B. Regular user token to admin endpoint -> 403 Forbidden
    forbidden_res = requests.get(f"{BASE_URL}/api/admin/metrics", headers={"Authorization": f"Bearer {user_token}"})
    print(f"  User token to /api/admin/metrics: Status {forbidden_res.status_code}, Body: {forbidden_res.json()}")
    assert forbidden_res.status_code == 403
    results["6. Unauthorized Protected Request"] = f"PASS (Status 401 for anon, Status 403 for user on admin API)"

    # -------------------------------------------------------------------------
    # 7. Authenticated User Request
    # -------------------------------------------------------------------------
    print("\n[7] Testing Authenticated User Request...")
    me_res = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {user_token}"})
    print(f"  Status: {me_res.status_code}, Profile: {me_res.json()}")
    assert me_res.status_code == 200
    assert me_res.json()["username"] == new_username
    assert "hashed_password" not in me_res.json()
    results["7. Authenticated User Request"] = f"PASS (Status 200: /api/auth/me for {new_username})"

    # -------------------------------------------------------------------------
    # 8. Authenticated Admin Request
    # -------------------------------------------------------------------------
    print("\n[8] Testing Authenticated Admin Request...")
    admin_metrics_res = requests.get(f"{BASE_URL}/api/admin/metrics", headers={"Authorization": f"Bearer {admin_token}"})
    print(f"  /api/admin/metrics Status: {admin_metrics_res.status_code}")
    assert admin_metrics_res.status_code == 200
    assert "total_generations" in admin_metrics_res.json()

    admin_dash_res = requests.get(f"{BASE_URL}/api/admin/dashboard", headers={"Authorization": f"Bearer {admin_token}"})
    print(f"  /api/admin/dashboard Status: {admin_dash_res.status_code}")
    assert admin_dash_res.status_code == 200
    assert "model_info" in admin_dash_res.json()
    results["8. Authenticated Admin Request"] = f"PASS (Status 200: /api/admin/metrics & /api/admin/dashboard)"

    # -------------------------------------------------------------------------
    # 9. Server-Side ADMIN Privilege Escalation Protection
    # -------------------------------------------------------------------------
    print("\n[9] Testing Server-Side ADMIN Privilege Escalation Protection...")
    # Client sends role="ADMIN" without verification code -> MUST be rejected with 403
    escalate_res = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": f"hacker_{ts}",
        "email": f"hacker_{ts}@domain.com",
        "password": "HackerPassword123!",
        "role": "ADMIN",
        # Missing or invalid admin_invite_code
    })
    print(f"  Attempted unverified ADMIN registration: Status {escalate_res.status_code}, Body: {escalate_res.json()}")
    assert escalate_res.status_code == 403
    assert "administrative verification code is required" in escalate_res.json().get("detail", "")
    results["9. Admin Escalation Protection"] = f"PASS (Status 403: Role escalation rejected by server)"

    print("\n" + "=" * 70)
    print("FINAL TEST RESULTS MATRIX")
    print("=" * 70)
    for k, v in results.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    run_tests()
