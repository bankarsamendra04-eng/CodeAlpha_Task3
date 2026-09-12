import os
import sys
import time
import requests

BASE_URL = "http://127.0.0.1:8000"

def run_rbac_tests():
    print("======================================================================")
    print("STRICT ROLE-BASED ACCESS CONTROL (RBAC) REAL BACKEND API VERIFICATION")
    print("======================================================================")

    # Setup accounts
    timestamp = int(time.time())
    user_cred = {"username": f"rbac_user_{timestamp}", "password": "UserSecure#2026", "email": f"user_{timestamp}@test.io"}
    admin_cred = {"username": "samendra_bankar", "password": "Samm@2004"}

    # 1. Register normal USER
    reg_res = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": user_cred["username"],
        "email": user_cred["email"],
        "password": user_cred["password"],
        "role": "USER"
    })
    assert reg_res.status_code == 201, f"User registration failed: {reg_res.text}"
    user_token = reg_res.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}
    print("[SETUP] Created test normal USER account.")

    # 2. Login as ADMIN
    admin_res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": admin_cred["username"],
        "password": admin_cred["password"]
    })
    assert admin_res.status_code == 200, f"Admin login failed: {admin_res.text}"
    admin_token = admin_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("[SETUP] Authenticated ADMIN account.")

    results = {}

    # TEST 1: Unauthenticated -> Admin API = DENY (401)
    print("\n--- TEST 1: Unauthenticated -> Admin API = DENY (401) ---")
    r1_dash = requests.get(f"{BASE_URL}/api/admin/dashboard")
    r1_metrics = requests.get(f"{BASE_URL}/api/admin/metrics")
    print(f"  GET /api/admin/dashboard -> Status: {r1_dash.status_code}")
    print(f"  GET /api/admin/metrics   -> Status: {r1_metrics.status_code}")
    assert r1_dash.status_code == 401, f"Expected 401, got {r1_dash.status_code}"
    assert r1_metrics.status_code == 401, f"Expected 401, got {r1_metrics.status_code}"
    results["1. Unauthenticated -> Admin API"] = "PASS (401 Unauthorized)"

    # TEST 2: USER -> Admin API = DENY (403 Forbidden)
    print("\n--- TEST 2: USER -> Admin API = DENY (403) ---")
    r2_dash = requests.get(f"{BASE_URL}/api/admin/dashboard", headers=user_headers)
    r2_metrics = requests.get(f"{BASE_URL}/api/admin/metrics", headers=user_headers)
    r2_users = requests.get(f"{BASE_URL}/api/admin/users", headers=user_headers)
    print(f"  GET /api/admin/dashboard (User Bearer) -> Status: {r2_dash.status_code}, Detail: {r2_dash.json().get('detail')}")
    print(f"  GET /api/admin/metrics   (User Bearer) -> Status: {r2_metrics.status_code}, Detail: {r2_metrics.json().get('detail')}")
    print(f"  GET /api/admin/users     (User Bearer) -> Status: {r2_users.status_code}, Detail: {r2_users.json().get('detail')}")
    assert r2_dash.status_code == 403, f"Expected 403, got {r2_dash.status_code}"
    assert r2_metrics.status_code == 403, f"Expected 403, got {r2_metrics.status_code}"
    assert r2_users.status_code == 403, f"Expected 403, got {r2_users.status_code}"
    assert "Administrative privileges required" in r2_dash.json().get("detail", "")
    results["2. USER -> Admin API"] = "PASS (403 Forbidden - Admin Required)"

    # TEST 3: ADMIN -> Admin API = ALLOW (200 OK)
    print("\n--- TEST 3: ADMIN -> Admin API = ALLOW (200) ---")
    r3_dash = requests.get(f"{BASE_URL}/api/admin/dashboard", headers=admin_headers)
    r3_metrics = requests.get(f"{BASE_URL}/api/admin/metrics", headers=admin_headers)
    print(f"  GET /api/admin/dashboard (Admin Bearer) -> Status: {r3_dash.status_code}, Users Count: {r3_dash.json().get('total_users')}")
    print(f"  GET /api/admin/metrics   (Admin Bearer) -> Status: {r3_metrics.status_code}, Model: {r3_metrics.json().get('model_status')}")
    assert r3_dash.status_code == 200, f"Expected 200, got {r3_dash.status_code}"
    assert r3_metrics.status_code == 200, f"Expected 200, got {r3_metrics.status_code}"
    results["3. ADMIN -> Admin API"] = "PASS (200 OK - Admin Granted)"

    # TEST 4: USER -> User Dashboard/Protected API = ALLOW (200 OK)
    print("\n--- TEST 4: USER -> User Protected API = ALLOW (200) ---")
    r4_me = requests.get(f"{BASE_URL}/api/auth/me", headers=user_headers)
    r4_sub = requests.get(f"{BASE_URL}/api/subscription/me", headers=user_headers)
    print(f"  GET /api/auth/me         (User Bearer) -> Status: {r4_me.status_code}, Role: {r4_me.json().get('role')}")
    print(f"  GET /api/subscription/me (User Bearer) -> Status: {r4_sub.status_code}, Tier: {r4_sub.json().get('tier')}")
    assert r4_me.status_code == 200, f"Expected 200, got {r4_me.status_code}"
    assert r4_sub.status_code == 200, f"Expected 200, got {r4_sub.status_code}"
    assert r4_me.json()["role"] == "USER"
    results["4. USER -> User Protected API"] = "PASS (200 OK - Verified User)"

    # TEST 5: Unauthenticated -> User Protected API = DENY (401)
    print("\n--- TEST 5: Unauthenticated -> User Protected API = DENY (401) ---")
    r5_me = requests.get(f"{BASE_URL}/api/auth/me")
    r5_sub = requests.get(f"{BASE_URL}/api/subscription/me")
    print(f"  GET /api/auth/me         (No Bearer) -> Status: {r5_me.status_code}, Detail: {r5_me.json().get('detail')}")
    print(f"  GET /api/subscription/me (No Bearer) -> Status: {r5_sub.status_code}, Detail: {r5_sub.json().get('detail')}")
    assert r5_me.status_code == 401, f"Expected 401, got {r5_me.status_code}"
    assert r5_sub.status_code == 401, f"Expected 401, got {r5_sub.status_code}"
    results["5. Unauthenticated -> User Protected API"] = "PASS (401 Unauthorized)"

    # TEST 6: Client Privilege Escalation Protection (registration)
    print("\n--- TEST 6: Prevent registration from selecting ADMIN without secret = DENY (403) ---")
    r6_hack = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": f"hacker_{timestamp}",
        "email": f"hacker_{timestamp}@test.io",
        "password": "HackerPass123!",
        "role": "ADMIN"  # Client claims ADMIN without verification code
    })
    print(f"  POST /api/auth/register (role=ADMIN, code=None) -> Status: {r6_hack.status_code}, Detail: {r6_hack.json().get('detail')}")
    assert r6_hack.status_code == 403, f"Expected 403, got {r6_hack.status_code}"
    results["6. Client Registration ADMIN Escalation"] = "PASS (403 Forbidden - Code Required)"

    # TEST 7: Client Token Tampering / Role Forgery Protection
    print("\n--- TEST 7: Fake/Tampered Token with forged role=ADMIN = DENY (401) ---")
    tampered_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NSIsInVzZXJuYW1lIjoiZmFrZV9hZG1pbiIsInJvbGUiOiJBRE1JTiJ9.fake_signature_that_fails_validation"
    r7_tamper = requests.get(f"{BASE_URL}/api/admin/dashboard", headers={"Authorization": f"Bearer {tampered_token}"})
    print(f"  GET /api/admin/dashboard (Forged JWT) -> Status: {r7_tamper.status_code}")
    assert r7_tamper.status_code == 401, f"Expected 401, got {r7_tamper.status_code}"
    results["7. Forged/Tampered Token Protection"] = "PASS (401 Unauthorized)"

    print("\n======================================================================")
    print("BACKEND RBAC TEST MATRIX RESULTS")
    print("======================================================================")
    for k, v in results.items():
        print(f"  {k}: {v}")
    print("======================================================================")

if __name__ == "__main__":
    run_rbac_tests()
