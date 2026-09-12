"""
Security Review Test Suite for Audio Playback and Media Endpoints.
Verifies defense-in-depth across:
1. Path traversal & directory traversal prevention
2. Arbitrary filesystem access prevention
3. Unauthorized multi-user access (tenant isolation)
4. Invalid generation IDs and nonexistent files
5. Unsupported extensions rejection
6. Zero server filesystem paths exposed in responses
7. Correct MIME types & X-Content-Type-Options: nosniff
8. Rate limiting on media endpoints
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.main import app
from backend.database.connection import SessionLocal
from backend.database.models import User, Generation
from backend.schemas.music import MusicGenerateRequest
from backend.services.music_pipeline import get_music_pipeline
from backend.services.security_service import rate_limiter
from ml.config import AUDIO_OUTPUT_DIR, MIDI_OUTPUT_DIR


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    rate_limiter.reset()
    yield
    rate_limiter.reset()


def test_valid_generation_playback_and_download(client):
    """
    Verify legitimate generation can be streamed (played) and downloaded.
    Checks:
    - HTTP 200
    - Proper Content-Type
    - Accept-Ranges: bytes
    - Content-Disposition: inline
    """
    # 1. Create a guest composition
    pipeline = get_music_pipeline()
    db = SessionLocal()
    try:
        req = MusicGenerateRequest(
            prompt="Soft lullaby in F major for security test",
            instrument="piano",
            tempo=80.0,
            key="F",
            scale="major",
            render_audio=True,
            random_seed=101,
        )
        res = pipeline.generate_music(req, db=db, current_user=None)
        wav_file = res.audio_file.filename
        midi_file = res.midi_file.filename
    finally:
        db.close()

    # 2. Test Playback / Streaming
    play_res = client.get(f"/api/music/download/audio/{wav_file}")
    assert play_res.status_code == 200
    assert play_res.headers["content-type"] == "audio/wav"
    assert play_res.headers.get("accept-ranges") == "bytes"
    assert "inline" in play_res.headers.get("content-disposition", "")
    assert play_res.content[:4] == b"RIFF"

    # 3. Test MIDI Download
    midi_res = client.get(f"/api/music/download/midi/{midi_file}")
    assert midi_res.status_code == 200
    assert midi_res.headers["content-type"] == "audio/midi"
    assert midi_res.content[:4] == b"MThd"


def test_invalid_generation_id_and_nonexistent_file(client):
    """Verify requesting non-existent files returns 404 with safe details."""
    res_audio = client.get("/api/music/download/audio/nonexistent_gen_999999999999_piano.wav")
    assert res_audio.status_code == 404
    detail = res_audio.json().get("detail", "")
    assert "not found" in detail.lower()
    # Ensure full server paths are NOT in detail
    assert "C:" not in detail
    assert "/" not in detail and "\\" not in detail

    res_midi = client.get("/api/music/download/midi/nonexistent_gen_999999999999_piano.mid")
    assert res_midi.status_code == 404
    detail_midi = res_midi.json().get("detail", "")
    assert "not found" in detail_midi.lower()
    assert "C:" not in detail_midi


def test_path_traversal_attempts_rejected(client):
    """Verify multiple malicious path traversal patterns are strictly rejected."""
    malicious_payloads = [
        "../../etc/passwd",
        "..%2F..%2Fwindows/win.ini",
        "..\\..\\boot.ini",
        "subfolder/secret.wav",
        "nested/path/audio.wav",
        ".env",
        ".git/config",
        "file.wav%00.exe",
        "malicious.sh",
        "exploit.exe",
    ]

    for payload in malicious_payloads:
        # Audio endpoint
        r_audio = client.get(f"/api/music/download/audio/{payload}")
        assert r_audio.status_code in (400, 404), f"Audio payload '{payload}' was not rejected cleanly: {r_audio.status_code}"
        if r_audio.status_code == 400:
            assert "detail" in r_audio.json()

        # MIDI endpoint
        r_midi = client.get(f"/api/music/download/midi/{payload}")
        assert r_midi.status_code in (400, 404), f"MIDI payload '{payload}' was not rejected cleanly: {r_midi.status_code}"


def test_multi_user_tenant_isolation_on_media_endpoints(client):
    """
    Verify that an authenticated user's generated media CANNOT be accessed by other users
    or unauthenticated guests.
    """
    ts = int(datetime.now(timezone.utc).timestamp())
    # 1. Register User Alice
    alice_res = client.post(
        "/api/auth/register",
        json={"username": f"alice_{ts}", "email": f"alice_{ts}@studio.io", "password": "AlicePassword123!"},
    )
    assert alice_res.status_code == 201
    alice_token = alice_res.json()["access_token"]
    alice_id = alice_res.json()["user"]["id"]

    # 2. Register User Bob
    bob_res = client.post(
        "/api/auth/register",
        json={"username": f"bob_{ts}", "email": f"bob_{ts}@studio.io", "password": "BobPassword123!"},
    )
    assert bob_res.status_code == 201
    bob_token = bob_res.json()["access_token"]

    # 3. Create a private generation for Alice with real physical files
    gen_id = f"gen_sec_alice_{ts}"
    wav_filename = f"{gen_id}_piano.wav"
    midi_filename = f"{gen_id}_piano.mid"

    # Write dummy valid files on disk in output directories
    wav_path = AUDIO_OUTPUT_DIR / wav_filename
    midi_path = MIDI_OUTPUT_DIR / midi_filename
    wav_path.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
    midi_path.write_bytes(b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x01\xe0")

    db = SessionLocal()
    try:
        alice_gen = Generation(
            generation_id=gen_id,
            user_id=alice_id,
            prompt="Alice private melody",
            tempo_bpm=100.0,
            instrument="piano",
            generation_status="completed",
            audio_file_name=wav_filename,
            audio_file_url=f"/api/music/download/audio/{wav_filename}",
            midi_file_name=midi_filename,
            midi_file_url=f"/api/music/download/midi/{midi_filename}",
        )
        db.add(alice_gen)
        db.commit()
    finally:
        db.close()

    try:
        # A. Unauthenticated guest attempts to access Alice's audio -> 401 Unauthorized
        res_guest_audio = client.get(f"/api/music/download/audio/{wav_filename}")
        assert res_guest_audio.status_code == 401
        assert "Authentication required" in res_guest_audio.json()["detail"]

        # B. User Bob attempts to access Alice's audio -> 403 Forbidden
        res_bob_audio = client.get(
            f"/api/music/download/audio/{wav_filename}",
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert res_bob_audio.status_code == 403
        assert "permission" in res_bob_audio.json()["detail"].lower()

        # C. User Alice accesses her own audio via Authorization header -> 200 OK
        res_alice_header = client.get(
            f"/api/music/download/audio/{wav_filename}",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert res_alice_header.status_code == 200

        # D. User Alice accesses her own audio via ?token= query parameter (HTML5 <audio>) -> 200 OK
        res_alice_query = client.get(f"/api/music/download/audio/{wav_filename}?token={alice_token}")
        assert res_alice_query.status_code == 200

        # E. User Bob attempts via ?token= query parameter -> 403 Forbidden
        res_bob_query = client.get(f"/api/music/download/audio/{wav_filename}?token={bob_token}")
        assert res_bob_query.status_code == 403

        # F. Unauthenticated guest attempts to access Alice's MIDI -> 401 Unauthorized
        res_guest_midi = client.get(f"/api/music/download/midi/{midi_filename}")
        assert res_guest_midi.status_code == 401

        # G. User Bob attempts to access Alice's MIDI -> 403 Forbidden
        res_bob_midi = client.get(
            f"/api/music/download/midi/{midi_filename}",
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert res_bob_midi.status_code == 403

        # H. User Alice accesses her own MIDI -> 200 OK
        res_alice_midi = client.get(
            f"/api/music/download/midi/{midi_filename}",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert res_alice_midi.status_code == 200
    finally:
        # Cleanup test files
        if wav_path.exists():
            wav_path.unlink()
        if midi_path.exists():
            midi_path.unlink()


def test_unsupported_extensions_and_mime_protection(client):
    """Verify that unsupported extensions are rejected and nosniff header is present."""
    bad_exts = ["test.exe", "script.sh", "code.py", "database.sqlite", "data.json"]
    for ext in bad_exts:
        r = client.get(f"/api/music/download/audio/{ext}")
        assert r.status_code == 400
        assert "Unsupported file extension" in r.json().get("detail", "")

    # Check security headers on response
    res = client.get("/health")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"


def test_no_server_filesystem_paths_exposed(client):
    """Verify that error messages never leak absolute server directories."""
    paths_to_test = [
        "/api/music/download/audio/nonexistent_file_test.wav",
        "/api/music/download/midi/nonexistent_file_test.mid",
        "/api/generations/invalid-guid-12345",
    ]

    for p in paths_to_test:
        res = client.get(p)
        body = res.text
        assert "C:\\" not in body
        assert "Users" not in body
        assert "Desktop" not in body
        assert "AI-Music-Studio" not in body


def test_media_rate_limiting(client):
    """Verify that excessive requests to /api/music/download are bounded."""
    # We configured 120 per minute. Flooding 125 requests should trigger 429.
    triggered_429 = False
    for _ in range(125):
        res = client.get("/api/music/download/audio/nonexistent_flood.wav")
        if res.status_code == 429:
            triggered_429 = True
            assert "Retry-After" in res.headers
            break

    assert triggered_429 is True, "Rate limiter did not throttle excessive media requests"
