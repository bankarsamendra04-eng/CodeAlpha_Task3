"""
Tests for generated music playback persistence, database storage, and edge cases.
Verifies the end-to-end pipeline:
    Generation record -> Generation ID -> Stored media -> Playable media URL -> Streaming
Across:
- Real music generation & parameter storage
- Storage in SQLite without binary blobs
- Server restart / DB session disposal
- Browser refresh / history re-fetch
- Playback of real generated WAV audio
- Automatic on-demand re-synthesis when WAV is deleted
- Graceful 404 when media is completely missing
- Path traversal and invalid URL prevention
"""

import os
import sys
import wave
import pytest
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.database.connection import SessionLocal, engine
from backend.database.models import Generation, GeneratedFile
from backend.schemas.music import MusicGenerateRequest
from backend.services.music_pipeline import get_music_pipeline
from ml.config import MIDI_OUTPUT_DIR, AUDIO_OUTPUT_DIR


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


def test_real_generation_persists_in_database_without_audio_blobs(client, db_session: Session):
    """
    Generate a real piece of music using the pipeline with audio rendering.
    Verify:
    1. Generation record & GeneratedFile records are created in SQLite.
    2. No binary audio blobs are stored in the database columns.
    3. The generated MIDI and WAV files exist on disk in output directories.
    """
    pipeline = get_music_pipeline()
    request = MusicGenerateRequest(
        prompt="Calm piano nocturne in C major",
        tempo=72.0,
        instrument="piano",
        key="C",
        scale="major",
        render_audio=True,
        random_seed=42,
    )

    result = pipeline.generate_music(request, db=db_session, current_user=None)
    assert result.success is True
    assert result.generation_id.startswith("gen_")
    assert result.midi_file is not None
    assert result.audio_file is not None

    gen_id = result.generation_id
    wav_filename = result.audio_file.filename
    midi_filename = result.midi_file.filename

    # 1. Verify files exist on disk
    midi_path = MIDI_OUTPUT_DIR / midi_filename
    wav_path = AUDIO_OUTPUT_DIR / wav_filename
    assert midi_path.exists(), f"MIDI file not found on disk: {midi_path}"
    assert wav_path.exists(), f"WAV file not found on disk: {wav_path}"
    assert midi_path.stat().st_size > 0
    assert wav_path.stat().st_size > 0

    # 2. Verify database record
    gen_row = db_session.query(Generation).filter(Generation.generation_id == gen_id).first()
    assert gen_row is not None
    assert gen_row.generation_id == gen_id
    assert gen_row.instrument == "piano"
    assert gen_row.tempo_bpm == 72.0
    assert gen_row.musical_key == "C"
    assert gen_row.scale == "major"
    assert gen_row.midi_file_name == midi_filename
    assert gen_row.audio_file_name == wav_filename
    assert gen_row.audio_status == "rendered"

    # 3. Verify no binary BLOB columns exist in Generation table
    for col in Generation.__table__.columns:
        # Check column types: should be String, Integer, Float, Boolean, DateTime, Text, JSON
        type_str = str(col.type).upper()
        assert "BLOB" not in type_str and "BYTEA" not in type_str and "VARBINARY" not in type_str, (
            f"Unexpected binary blob column in Generation model: {col.name} ({col.type})"
        )

    # 4. Verify GeneratedFile child records
    file_records = db_session.query(GeneratedFile).filter(GeneratedFile.generation_id == gen_row.id).all()
    assert len(file_records) >= 2
    types = [f.file_type for f in file_records]
    assert "midi" in types
    assert "audio_wav" in types
    for fr in file_records:
        assert fr.download_url.startswith("/api/music/download/")


def test_history_endpoint_returns_playable_url_and_metadata(client):
    """
    Verify GET /api/generations returns records with valid playable media URLs and metadata.
    """
    res = client.get("/api/generations?limit=6")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) > 0

    item = data["items"][0]
    assert "generation_id" in item
    assert "midi_file" in item and item["midi_file"] is not None
    assert "audio_file" in item and item["audio_file"] is not None
    assert item["audio_file"]["download_url"].startswith("/api/music/download/audio/")
    assert item["audio_file"]["filename"].endswith(".wav")


def test_audio_streaming_returns_valid_wav_bytes(client):
    """
    Hit the playable audio media URL and verify:
    - HTTP 200
    - Content-Type: audio/wav
    - Accept-Ranges: bytes
    - Content-Disposition: inline
    - Valid WAV header (RIFF ... WAVE)
    """
    # Get latest generation
    res = client.get("/api/generations?limit=1")
    assert res.status_code == 200
    latest = res.json()["items"][0]
    audio_url = latest["audio_file"]["download_url"]

    stream_res = client.get(audio_url)
    assert stream_res.status_code == 200
    assert stream_res.headers["content-type"] == "audio/wav"
    assert stream_res.headers.get("accept-ranges") == "bytes"
    assert "inline" in stream_res.headers.get("content-disposition", "")

    content = stream_res.content
    assert len(content) > 44
    assert content[:4] == b"RIFF"
    assert content[8:12] == b"WAVE"


def test_persistence_across_server_restart_and_browser_refresh(client):
    """
    Simulate:
    1. Server restart (dispose SQLAlchemy connection pool, fresh session)
    2. Browser refresh (client re-queries GET /api/generations)
    3. Re-playing historical track (client streams audio from playable URL)
    """
    # Simulate server restart by disposing the connection pool
    engine.dispose()

    # Fresh client query simulating browser page refresh
    res = client.get("/api/generations?limit=6")
    assert res.status_code == 200
    history = res.json()["items"]
    assert len(history) > 0

    # User clicks "Load & Play" on the top historical track
    target = history[0]
    audio_url = target["audio_file"]["download_url"]
    assert audio_url is not None

    stream_res = client.get(audio_url)
    assert stream_res.status_code == 200
    assert stream_res.headers["content-type"] == "audio/wav"
    assert len(stream_res.content) > 100
    assert stream_res.content[:4] == b"RIFF"


def test_on_demand_synthesis_when_cached_wav_is_deleted(client):
    """
    Simulate a scenario where disk cleanup or cache eviction deleted the .wav file,
    but the .mid file is preserved.
    The backend should automatically synthesize the WAV on-demand when requested.
    """
    res = client.get("/api/generations?limit=1")
    assert res.status_code == 200
    item = res.json()["items"][0]
    wav_filename = item["audio_file"]["filename"]
    midi_filename = item["midi_file"]["filename"]

    wav_path = AUDIO_OUTPUT_DIR / wav_filename
    midi_path = MIDI_OUTPUT_DIR / midi_filename

    assert midi_path.exists(), "Underlying MIDI file must exist for this test"

    # Delete the WAV file from disk
    if wav_path.exists():
        wav_path.unlink()
    assert not wav_path.exists()

    # Request the audio stream again (as if user clicks Load & Play)
    stream_res = client.get(f"/api/music/download/audio/{wav_filename}")
    assert stream_res.status_code == 200
    assert stream_res.headers["content-type"] == "audio/wav"
    assert wav_path.exists(), "On-demand synthesis should recreate the WAV on disk"
    assert len(stream_res.content) > 100


def test_missing_files_returns_graceful_404_not_crash(client):
    """
    When both the .wav and .mid files are missing, the endpoint returns a clean 404,
    not an unhandled 500 error or crash.
    """
    stream_res = client.get("/api/music/download/audio/nonexistent_gen_000000000000_piano.wav")
    assert stream_res.status_code == 404
    err_json = stream_res.json()
    assert "detail" in err_json
    assert "not found" in err_json["detail"].lower()


def test_path_traversal_and_invalid_filenames_return_400(client):
    """
    Verify directory traversal attempts and dangerous extensions are rejected with 400 Bad Request.
    """
    # Directory traversal with '..'
    r1 = client.get("/api/music/download/audio/..%2f..%2fetc%2fpasswd")
    assert r1.status_code in (400, 404)

    # Disallowed extension (.exe)
    r2 = client.get("/api/music/download/audio/malicious_file.exe")
    assert r2.status_code == 400
    assert "Unsupported file extension" in r2.json()["detail"]

    # Traversal in MIDI endpoint
    r3 = client.get("/api/music/download/midi/test..mid")
    assert r3.status_code == 400


def test_midi_download_persistence(client):
    """
    Verify MIDI file download remains intact and delivers valid Standard MIDI File bytes (b'MThd').
    """
    res = client.get("/api/generations?limit=1")
    assert res.status_code == 200
    item = res.json()["items"][0]
    midi_url = item["midi_file"]["download_url"]

    midi_res = client.get(midi_url)
    assert midi_res.status_code == 200
    assert midi_res.headers["content-type"] == "audio/midi"
    assert midi_res.content[:4] == b"MThd"
