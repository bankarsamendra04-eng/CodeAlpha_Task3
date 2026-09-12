"""
AI Music Studio - Security Verification Test Suite
Tests all hardening measures across the application:
1. OWASP Secure HTTP response headers
2. Rate limiting and 429 Too Many Requests response
3. Path traversal attack prevention
4. Binary MIDI and WAV magic bytes validation
5. File upload validation endpoint
6. Input sanitization against Cross-Site Scripting (XSS)
7. Safe error responses (no stack traces or file paths leaked)
8. API key protection and environment confidentiality
9. SQL injection resistance
10. Authentication and Authorization boundaries
"""

import io
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.connection import init_db
from backend.services.security_service import (
    validate_safe_path,
    validate_midi_bytes,
    validate_wav_bytes,
    validate_file_upload,
    sanitize_user_input,
    rate_limiter,
)
from ml.config import MIDI_OUTPUT_DIR, AUDIO_OUTPUT_DIR


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


# ---------------------------------------------------------------------------
# 1. OWASP Security HTTP Headers Tests
# ---------------------------------------------------------------------------

def test_security_http_headers_present():
    """Verify that all responses include strict OWASP security headers."""
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    headers = response.headers

    # Check X-Content-Type-Options
    assert headers.get("x-content-type-options") == "nosniff"

    # Check X-Frame-Options (Clickjacking defense)
    assert headers.get("x-frame-options") == "DENY"

    # Check X-XSS-Protection
    assert headers.get("x-xss-protection") == "1; mode=block"

    # Check Referrer-Policy
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    # Check Content-Security-Policy
    csp = headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp

    # Check Permissions-Policy
    assert "geolocation=()" in headers.get("permissions-policy", "")

    # Check Strict-Transport-Security (HSTS)
    assert "max-age=" in headers.get("strict-transport-security", "")


# ---------------------------------------------------------------------------
# 2. Rate Limiting Tests
# ---------------------------------------------------------------------------

def test_rate_limiting_on_auth_login():
    """Verify rate limiter blocks excessive requests and returns 429 Too Many Requests."""
    client = TestClient(app)
    test_ip = "192.168.1.99"
    headers = {"X-Forwarded-For": test_ip}

    # Reset history
    rate_limiter.reset()

    # Make 20 permitted attempts
    for _ in range(20):
        res = client.post(
            "/api/auth/login",
            json={"username": "test_user", "password": "wrong_password"},
            headers=headers,
        )
        assert res.status_code in (401, 422)

    # 21st request must be rejected with 429 Too Many Requests
    blocked_res = client.post(
        "/api/auth/login",
        json={"username": "test_user", "password": "wrong_password"},
        headers=headers,
    )
    assert blocked_res.status_code == 429
    assert "Too many requests" in blocked_res.json()["detail"]
    assert "Retry-After" in blocked_res.headers

    # Clean up rate limiter history so subsequent tests run cleanly
    rate_limiter.reset()


# ---------------------------------------------------------------------------
# 3. Path Traversal Defense Tests
# ---------------------------------------------------------------------------

def test_path_traversal_rejection():
    """Verify directory traversal attempts in download routes are strictly rejected."""
    client = TestClient(app)

    malicious_filenames = [
        "../../etc/passwd",
        "..%2F..%2Fwindows/win.ini",
        "..\\..\\boot.ini",
        "nested/subfolder/file.mid",
        "file.mid%00.exe",
        ".hidden_file.mid",
        "malicious_script.sh",
        "exploit.exe",
    ]

    for filename in malicious_filenames:
        # Test MIDI download
        res_midi = client.get(f"/api/music/download/midi/{filename}")
        assert res_midi.status_code in (400, 404), f"Filename '{filename}' was not rejected cleanly in MIDI download"

        # Test Audio download
        res_audio = client.get(f"/api/music/download/audio/{filename}")
        assert res_audio.status_code in (400, 404), f"Filename '{filename}' was not rejected cleanly in Audio download"


def test_safe_path_validation_logic():
    """Directly test validate_safe_path utility against hostile patterns."""
    with pytest.raises(Exception):
        validate_safe_path(MIDI_OUTPUT_DIR, "../malicious.mid")

    with pytest.raises(Exception):
        validate_safe_path(MIDI_OUTPUT_DIR, "file.mid\x00.exe")

    with pytest.raises(Exception):
        validate_safe_path(MIDI_OUTPUT_DIR, "file.exe", allowed_extensions={".mid"})

    with pytest.raises(Exception):
        validate_safe_path(MIDI_OUTPUT_DIR, ".env")


# ---------------------------------------------------------------------------
# 4. Binary File Validation Tests (Magic Bytes)
# ---------------------------------------------------------------------------

def test_validate_midi_bytes():
    """Verify MIDI magic header b'MThd' validation."""
    # Valid MIDI minimal header
    valid_midi_header = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x01\xe0"
    is_valid, error = validate_midi_bytes(valid_midi_header)
    assert is_valid is True
    assert error is None

    # Invalid header
    invalid_header = b"NOT_A_MIDI_FILE_DATA_HERE"
    is_valid, error = validate_midi_bytes(invalid_header)
    assert is_valid is False
    assert "MThd" in error

    # Truncated header
    is_valid, error = validate_midi_bytes(b"MThd")
    assert is_valid is False


def test_validate_wav_bytes():
    """Verify WAV magic header b'RIFF' and b'WAVE' validation."""
    # Construct minimal 44-byte WAV header
    valid_wav_header = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x02\x00\x44\xac\x00\x00\x10\xb1\x02\x00\x04\x00\x10\x00data\x00\x00\x00\x00"
    is_valid, error = validate_wav_bytes(valid_wav_header)
    assert is_valid is True
    assert error is None

    # Corrupted header
    corrupted = b"RIFF\x24\x00\x00\x00XXXXfmt \x10\x00\x00\x00" + b"\x00" * 30
    is_valid, error = validate_wav_bytes(corrupted)
    assert is_valid is False
    assert "WAVE" in error


# ---------------------------------------------------------------------------
# 5. File Upload Validation API Tests
# ---------------------------------------------------------------------------

def test_file_upload_validation_endpoint():
    """Test /api/music/validate-upload against valid and malicious uploads."""
    client = TestClient(app)

    # 1. Valid MIDI upload
    valid_midi_data = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x01\xe0"
    files = {"file": ("test_piece.mid", io.BytesIO(valid_midi_data), "audio/midi")}
    res = client.post("/api/music/validate-upload?file_type=midi", files=files)
    assert res.status_code == 200
    assert res.json()["valid"] is True

    # 2. Reject executable disguised as midi
    exe_data = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
    files = {"file": ("malware.mid", io.BytesIO(exe_data), "audio/midi")}
    res = client.post("/api/music/validate-upload?file_type=midi", files=files)
    assert res.status_code == 400
    assert "MThd" in res.json()["detail"]

    # 3. Reject executable extension
    files = {"file": ("script.exe", io.BytesIO(b"fake data"), "application/octet-stream")}
    res = client.post("/api/music/validate-upload?file_type=midi", files=files)
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# 6. Input Sanitization & XSS Protection Tests
# ---------------------------------------------------------------------------

def test_input_sanitization():
    """Verify HTML and JavaScript tags are stripped from user text inputs."""
    dirty_input = "<script>alert('pwned')</script>Peaceful Piano<img src=x onerror=alert(1)>"
    cleaned = sanitize_user_input(dirty_input)

    assert "<script>" not in cleaned
    assert "</script>" not in cleaned
    assert "onerror=" not in cleaned
    assert "Peaceful Piano" in cleaned


# ---------------------------------------------------------------------------
# 7. Safe Error Responses Tests
# ---------------------------------------------------------------------------

def test_safe_error_messages_no_stacktrace():
    """Verify that unhandled server exceptions do not leak stack traces or server paths."""
    client = TestClient(app)

    # Call a non-existent generation ID
    res = client.get("/api/generations/non-existent-guid-99999")
    assert res.status_code == 404
    data = res.json()
    assert "Traceback" not in str(data)
    assert "C:\\" not in str(data)
    assert "/home/" not in str(data)


# ---------------------------------------------------------------------------
# 8. Secret Confidentiality Tests
# ---------------------------------------------------------------------------

def test_api_keys_and_passwords_never_exposed():
    """Verify health and public endpoints never return API keys or database secrets."""
    client = TestClient(app)

    health_res = client.get("/health")
    assert health_res.status_code == 200
    health_str = str(health_res.json())

    assert "gsk_" not in health_str
    assert "GROQ_API_KEY" not in health_str
    assert "SECRET_KEY" not in health_str
    assert "password" not in health_str


# ---------------------------------------------------------------------------
# 9. SQL Injection Resistance Tests
# ---------------------------------------------------------------------------

def test_sql_injection_resistance():
    """Verify malicious SQL payloads are properly parameterized and safely handled."""
    client = TestClient(app)
    sql_payload = "' OR '1'='1"

    # Attempt injection via generation search
    res = client.get(f"/api/generations/{sql_payload}")
    assert res.status_code in (404, 400)
    assert "syntax error" not in str(res.json()).lower()
