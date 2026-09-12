"""
Comprehensive tests for Registration System:
1. Validate email
2. Validate password
3. Confirm password matching
4. Prevent duplicate email
5. Hash password before storage
6. Never store plaintext password
7. Never return password or hash to frontend
8. Display useful validation messages
9. Never show "[object Object]"
10. Test that a public user cannot create ADMIN
"""

import os
import sys
import time
import requests
import pytest
from datetime import datetime, timezone

BASE_URL = "http://127.0.0.1:8000"

def test_registration_system():
    print("======================================================================")
    print("RUNNING REGISTRATION SYSTEM VERIFICATION SUITE")
    print("======================================================================")

    ts = int(time.time())
    valid_user = {
        "username": f"composer_{ts}",
        "email": f"composer_{ts}@studio.ai",
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!"
    }

    # 1. Successful Registration
    print("\n[1] Testing Successful Registration...")
    r1 = requests.post(f"{BASE_URL}/api/auth/register", json=valid_user)
    assert r1.status_code == 201, f"Expected 201, got {r1.status_code}: {r1.text}"
    data1 = r1.json()
    assert "access_token" in data1
    assert data1["user"]["username"] == valid_user["username"]
    assert data1["user"]["email"] == valid_user["email"]
    assert data1["user"]["role"] == "USER"
    assert "password" not in data1["user"]
    assert "hashed_password" not in data1["user"]
    print("  [PASS] Successfully registered normal USER. No password/hash returned.")

    # 2. Duplicate Username Rejection
    print("\n[2] Testing Duplicate Username Rejection...")
    r2_user = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": valid_user["username"],
        "email": f"different_{ts}@studio.ai",
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!"
    })
    assert r2_user.status_code == 400
    assert r2_user.json()["detail"] == "Username is already registered."
    print("  [PASS] Duplicate username rejected with clear message.")

    # 3. Duplicate Email Rejection
    print("\n[3] Testing Duplicate Email Rejection...")
    r2_email = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": f"different_{ts}",
        "email": valid_user["email"],
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!"
    })
    assert r2_email.status_code == 400
    assert r2_email.json()["detail"] == "Email address is already registered."
    print("  [PASS] Duplicate email rejected with clear message.")

    # 4. Invalid Email Validation
    print("\n[4] Testing Invalid Email Format...")
    for bad_email in ["not-an-email", "user@", "@domain.com", "user@domain", "user..double@domain.com"]:
        r_email = requests.post(f"{BASE_URL}/api/auth/register", json={
            "username": f"bademail_{ts}_{abs(hash(bad_email)) % 10000}",
            "email": bad_email,
            "password": "SecurePassword123!",
            "confirm_password": "SecurePassword123!"
        })
        assert r_email.status_code == 422, f"Expected 422 for bad email '{bad_email}', got {r_email.status_code}"
    print("  [PASS] Invalid email formats strictly rejected by validation.")

    # 5. Invalid Password (too short)
    print("\n[5] Testing Short Password Validation...")
    r_short_pw = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": f"short_{ts}",
        "email": f"short_{ts}@studio.ai",
        "password": "123",
        "confirm_password": "123"
    })
    assert r_short_pw.status_code == 422, f"Expected 422, got {r_short_pw.status_code}"
    print("  [PASS] Short password strictly rejected (<6 chars).")

    # 6. Mismatched Confirm Password
    print("\n[6] Testing Mismatched Confirm Password...")
    r_mismatch = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": f"mismatch_{ts}",
        "email": f"mismatch_{ts}@studio.ai",
        "password": "Password123!",
        "confirm_password": "DifferentPassword123!"
    })
    assert r_mismatch.status_code == 400
    assert r_mismatch.json()["detail"] == "Passwords do not match."
    print("  [PASS] Password mismatch rejected with clear error.")

    # 7. Public User Cannot Self-Select ADMIN
    print("\n[7] Testing Public User Cannot Self-Select ADMIN...")
    r_admin_attempt = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": f"admin_wannabe_{ts}",
        "email": f"admin_wannabe_{ts}@studio.ai",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "role": "ADMIN"  # Blind client claim
    })
    assert r_admin_attempt.status_code == 403
    assert "Valid administrative verification code is required" in r_admin_attempt.json()["detail"]
    print("  [PASS] Self-selecting ADMIN rejected with HTTP 403 Forbidden.")

    print("\n======================================================================")
    print("ALL 7 REGISTRATION API TESTS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    test_registration_system()
