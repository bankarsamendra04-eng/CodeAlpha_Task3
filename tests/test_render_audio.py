"""Unit tests for scripts/render_audio.py audio rendering pipeline."""

import wave
import struct
from pathlib import Path
import pytest

from scripts.render_audio import (
    detect_fluidsynth,
    detect_soundfont,
    detect_ffmpeg,
    validate_wav_file,
    print_missing_setup_instructions,
    convert_midi_to_wav,
)


def create_dummy_wav(path: Path, duration_sec: float = 1.0, framerate: int = 44100):
    """Helper to create a valid minimal WAV file for testing."""
    num_frames = int(duration_sec * framerate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(framerate)
        # Write silent frames
        data = struct.pack("<" + "h" * num_frames, *([0] * num_frames))
        wf.writeframes(data)


def test_detect_functions():
    """Verify detect functions do not throw exceptions and return Path or None."""
    fs = detect_fluidsynth()
    assert fs is None or isinstance(fs, Path)

    sf = detect_soundfont()
    assert sf is None or isinstance(sf, Path)

    ff = detect_ffmpeg()
    assert ff is None or isinstance(ff, Path)


def test_validate_wav_file_valid(tmp_path: Path):
    """Verify that a properly structured WAV file passes validation."""
    wav_file = tmp_path / "valid.wav"
    create_dummy_wav(wav_file, duration_sec=1.5, framerate=44100)

    val = validate_wav_file(wav_file)
    assert val["is_valid"] is True
    assert val["num_channels"] == 1
    assert val["sample_rate_hz"] == 44100
    assert pytest.approx(val["duration_seconds"], 0.05) == 1.5
    assert val["error"] is None


def test_validate_wav_file_nonexistent(tmp_path: Path):
    """Verify non-existent file validation returns is_valid=False without crashing."""
    val = validate_wav_file(tmp_path / "nonexistent.wav")
    assert val["is_valid"] is False
    assert "does not exist" in val["error"]


def test_validate_wav_file_corrupt(tmp_path: Path):
    """Verify empty or corrupt file returns is_valid=False."""
    corrupt_file = tmp_path / "corrupt.wav"
    corrupt_file.write_bytes(b"RIFFcorruptdata")

    val = validate_wav_file(corrupt_file)
    assert val["is_valid"] is False


def test_missing_setup_instructions_content():
    """Verify informative instructions are returned when components are absent."""
    msg = print_missing_setup_instructions(fluidsynth_found=False, soundfont_found=False)
    assert "INSTALL FLUIDSYNTH" in msg
    assert "SOUNDFONT" in msg
    assert "choco install fluidsynth" in msg
    assert "docs/AUDIO_RENDERING.md" in msg


def test_convert_midi_to_wav_nonexistent_midi(tmp_path: Path):
    """Ensure graceful failure when input MIDI does not exist."""
    success, out_path, info = convert_midi_to_wav(tmp_path / "missing.mid")
    assert success is False
    assert out_path is None
    assert "not found" in info["error"]


def test_convert_midi_to_wav_missing_renderer_graceful(tmp_path: Path):
    """Ensure graceful degradation when FluidSynth / SoundFont is missing."""
    dummy_midi = tmp_path / "test.mid"
    dummy_midi.write_bytes(b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60")

    success, out_path, info = convert_midi_to_wav(
        dummy_midi,
        fluidsynth_path=Path("nonexistent/fluidsynth.exe"),
        soundfont_path=Path("nonexistent/soundfont.sf2"),
    )
    # Must NOT raise exception, must return clean status
    assert success is False
    assert out_path is None
    assert info.get("status") == "renderer_unavailable"
    assert "fluidsynth_found" in info