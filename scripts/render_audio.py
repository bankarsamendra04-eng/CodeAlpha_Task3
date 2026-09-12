"""
AI Music Studio - MIDI to Playable Audio Rendering Engine
Converts generated MIDI files into playable WAV audio using FluidSynth (and optionally FFmpeg).

Architecture:
    MIDI File (.mid)
          ↓
    FluidSynth (with SoundFont .sf2)
          ↓
    Playable WAV Audio (.wav)
          ↓ [Optional: FFmpeg]
    High-efficiency compressed audio (e.g. MP3 / OGG / FLAC)
          ↓
    Post-Render Audio Validation (wave header integrity, duration, channel verification)

Key Features:
- Non-crashing operation: If FluidSynth or SoundFont is unavailable, reports a clean setup guide
  and gracefully allows MIDI generation & workflow to continue.
- Full auto-detection of FluidSynth binary, system SoundFonts, and environment overrides.
- Python native wave validation for exported WAV files.
- Command-line interface: python scripts/render_audio.py <midi_file> [--output <wav_path>] [--soundfont <sf2_path>]
"""

import os
import sys
import shutil
import wave
import argparse
import subprocess
import functools
from pathlib import Path
from typing import Optional, Union, Dict, Any, Tuple

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.config import (
    AUDIO_OUTPUT_DIR,
    MIDI_OUTPUT_DIR,
    FLUIDSYNTH_PATH,
    SOUNDFONT_PATH,
)

# Common default locations for SoundFonts across Windows and Linux
COMMON_SOUNDFONT_LOCATIONS = [
    # Environment variable / explicit project directories
    PROJECT_ROOT / "soundfonts",
    PROJECT_ROOT / "dataset" / "soundfonts",
    # Windows standard paths
    Path(os.environ.get("LOCALAPPDATA", "")) / "FluidSynth",
    Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "FluidSynth",
    Path("C:/soundfonts"),
    # Linux / WSL standard paths
    Path("/usr/share/sounds/sf2"),
    Path("/usr/share/soundfonts"),
    Path("/usr/local/share/soundfonts"),
]

COMMON_SOUNDFONT_FILENAMES = [
    "default.sf2",
    "FluidR3_GM.sf2",
    "FluidR3_GS.sf2",
    "GeneralUser_GS.sf2",
    "GeneralUser GS.sf2",
    "TimGM6mb.sf2",
    "soundfont.sf2",
]


@functools.lru_cache(maxsize=16)
def _cached_detect_fluidsynth(custom_path_str: Optional[str] = None) -> Optional[str]:
    # 1. Custom / config path
    path_to_test = custom_path_str or FLUIDSYNTH_PATH
    if path_to_test:
        candidate = Path(path_to_test).resolve()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
        if candidate.is_dir():
            exe_candidate = candidate / ("fluidsynth.exe" if sys.platform == "win32" else "fluidsynth")
            if exe_candidate.is_file():
                return str(exe_candidate)

    # 2. System PATH
    binary_name = "fluidsynth.exe" if sys.platform == "win32" else "fluidsynth"
    which_path = shutil.which(binary_name) or shutil.which("fluidsynth")
    if which_path:
        return str(Path(which_path).resolve())

    # 3. Known common directories on Windows
    if sys.platform == "win32":
        search_dirs = [
            Path("C:/tools/fluidsynth/bin"),
            Path("C:/fluidsynth/bin"),
            Path("C:/Program Files/FluidSynth/bin"),
            Path("C:/Program Files (x86)/FluidSynth/bin"),
            Path(os.environ.get("USERPROFILE", "C:/")) / "fluidsynth/bin",
            Path(os.environ.get("LOCALAPPDATA", "C:/")) / "Programs/fluidsynth/bin",
        ]
        for sdir in search_dirs:
            exe_file = sdir / "fluidsynth.exe"
            if exe_file.is_file():
                return str(exe_file)

    return None


def detect_fluidsynth(custom_path: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """Locate the FluidSynth binary with LRU caching."""
    custom_str = str(Path(custom_path).resolve()) if custom_path else None
    res = _cached_detect_fluidsynth(custom_str)
    return Path(res) if res else None


@functools.lru_cache(maxsize=16)
def _cached_detect_ffmpeg(custom_path_str: Optional[str] = None) -> Optional[str]:
    binary_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    which_path = shutil.which(binary_name) or shutil.which("ffmpeg")
    if which_path:
        return str(Path(which_path).resolve())
    return None


def detect_ffmpeg(custom_path: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """Locate FFmpeg binary with LRU caching."""
    custom_str = str(Path(custom_path).resolve()) if custom_path else None
    res = _cached_detect_ffmpeg(custom_str)
    return Path(res) if res else None


@functools.lru_cache(maxsize=16)
def _cached_detect_soundfont(custom_path_str: Optional[str] = None) -> Optional[str]:
    # 1. Custom / config path
    sf_candidate = custom_path_str or SOUNDFONT_PATH
    if sf_candidate:
        p = Path(sf_candidate).resolve()
        if p.is_file():
            return str(p)
        if p.is_dir():
            for sf_file in p.glob("*.sf2"):
                return str(sf_file)

    # 2. Search common locations
    for base_dir in COMMON_SOUNDFONT_LOCATIONS:
        if not base_dir.exists():
            continue
        for name in COMMON_SOUNDFONT_FILENAMES:
            candidate = base_dir / name
            if candidate.is_file():
                return str(candidate)
        for sf_file in base_dir.glob("*.sf2"):
            return str(sf_file)

    # 3. Search local project soundfonts/ directory
    local_sf_dir = PROJECT_ROOT / "soundfonts"
    if local_sf_dir.exists():
        for sf_file in local_sf_dir.glob("*.sf2"):
            return str(sf_file)

    return None


def detect_soundfont(custom_path: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """Locate SoundFont with LRU caching."""
    custom_str = str(Path(custom_path).resolve()) if custom_path else None
    res = _cached_detect_soundfont(custom_str)
    return Path(res) if res else None


def print_missing_setup_instructions(
    fluidsynth_found: bool,
    soundfont_found: bool,
) -> str:
    """Return a detailed and clear setup guidance message."""
    msg_lines = [
        "",
        "=================================================================",
        "        AUDIO RENDERING PREREQUISITES NOTICE",
        "=================================================================",
        "Notice: FluidSynth and/or a SoundFont (.sf2) is not configured yet.",
        "Your MIDI generation will continue to function flawlessly!",
        "To enable direct audio rendering (.wav / .mp3), follow these steps:",
        "",
    ]

    if not fluidsynth_found:
        msg_lines.extend([
            "1. INSTALL FLUIDSYNTH:",
            "   - Windows (via Chocolatey):",
            "       choco install fluidsynth",
            "   - Windows (via Scoop):",
            "       scoop install fluidsynth",
            "   - Windows (Direct Download):",
            "       https://github.com/FluidSynth/fluidsynth/releases",
            "       (Extract and add the 'bin' folder to your System PATH or .env)",
            "   - Linux (Debian/Ubuntu):",
            "       sudo apt-get install fluidsynth",
            "   - macOS (Homebrew):",
            "       brew install fluidsynth",
            "",
        ])

    if not soundfont_found:
        msg_lines.extend([
            "2. OBTAIN A GENERAL MIDI SOUNDFONT (.sf2):",
            "   FluidSynth requires a SoundFont to synthesize realistic instrument audio.",
            "   Recommended lightweight General MIDI soundfonts:",
            "   - FluidR3_GM.sf2 (~140MB, high quality orchestrations)",
            "   - GeneralUser GS (~30MB, balanced and versatile)",
            "   - TimGM6mb.sf2 (~6MB, ultra-lightweight)",
            "",
            "   Place your downloaded '.sf2' file into:",
            f"       {PROJECT_ROOT / 'soundfonts'}",
            "   or set the path in your .env file:",
            "       SOUNDFONT_PATH=C:\\path\\to\\GeneralUser_GS.sf2",
            "",
        ])

    msg_lines.extend([
        "Detailed documentation: docs/AUDIO_RENDERING.md",
        "=================================================================",
        "",
    ])
    return "\n".join(msg_lines)


def validate_wav_file(wav_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Validate that an exported WAV file has valid RIFF headers, audio channels,
    non-zero frame count, and non-zero duration.
    """
    wav_path = Path(wav_path).resolve()
    if not wav_path.exists():
        return {"is_valid": False, "error": f"WAV file does not exist: {wav_path}"}

    file_size = wav_path.stat().st_size
    if file_size < 44:  # RIFF header minimum size is 44 bytes
        return {"is_valid": False, "error": f"WAV file is truncated or empty ({file_size} bytes)"}

    try:
        with wave.open(str(wav_path), "rb") as wf:
            num_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            num_frames = wf.getnframes()
            duration = num_frames / float(framerate) if framerate > 0 else 0.0

            is_valid = num_channels in (1, 2) and framerate >= 8000 and num_frames > 0

            return {
                "is_valid": is_valid,
                "file_path": str(wav_path),
                "file_size_bytes": file_size,
                "num_channels": num_channels,
                "sample_width_bytes": sample_width,
                "sample_rate_hz": framerate,
                "total_frames": num_frames,
                "duration_seconds": round(duration, 3),
                "error": None if is_valid else "Invalid channel count or zero audio frames",
            }
    except Exception as exc:
        return {
            "is_valid": False,
            "file_path": str(wav_path),
            "file_size_bytes": file_size,
            "error": f"Wave validation error: {exc}",
        }


def render_midi_with_builtin_synth(
    midi_path: Union[str, Path],
    output_wav_path: Optional[Union[str, Path]] = None,
    sample_rate: int = 44100,
    gain: float = 0.6,
) -> Tuple[bool, Optional[Path], Dict[str, Any]]:
    """
    Built-in software audio synthesizer for AI Music Studio.
    Synthesizes musical events from a generated MIDI file into standard 16-bit 44.1kHz stereo WAV audio
    using harmonic additive synthesis with an acoustic envelope, without requiring external C++ dependencies.
    """
    import numpy as np
    import music21

    midi_path = Path(midi_path).resolve()
    if not midi_path.exists():
        return False, None, {"error": f"Input MIDI file not found: {midi_path}"}

    if output_wav_path is None:
        target_wav = AUDIO_OUTPUT_DIR / f"{midi_path.stem}.wav"
    else:
        target_wav = Path(output_wav_path).resolve()

    target_wav.parent.mkdir(parents=True, exist_ok=True)

    try:
        score = music21.converter.parse(str(midi_path))
        flat = score.flatten()

        tempo_bpm = 120.0
        for mark in flat.getElementsByClass(music21.tempo.MetronomeMark):
            tempo_bpm = mark.getQuarterBPM()
            break

        sec_per_quarter = 60.0 / max(30.0, min(300.0, tempo_bpm))
        max_time_sec = (float(flat.highestTime) * sec_per_quarter) + 1.5
        total_samples = max(int(sample_rate * 1.0), int(max_time_sec * sample_rate))

        audio_left = np.zeros(total_samples, dtype=np.float32)
        audio_right = np.zeros(total_samples, dtype=np.float32)

        for el in flat.notes:
            start_sec = float(el.offset) * sec_per_quarter
            dur_sec = float(el.quarterLength) * sec_per_quarter
            start_idx = int(start_sec * sample_rate)
            if start_idx >= total_samples:
                continue

            n_samples = int((dur_sec + 0.35) * sample_rate)
            end_idx = min(start_idx + n_samples, total_samples)
            actual_samples = end_idx - start_idx
            if actual_samples <= 0:
                continue

            pitches = el.pitches if el.isChord else [el.pitch]
            t = np.arange(actual_samples, dtype=np.float32) / sample_rate

            # Musical ADSR envelope with natural acoustic decay
            env = np.ones(actual_samples, dtype=np.float32)
            attack_len = min(int(0.015 * sample_rate), actual_samples)
            if attack_len > 0:
                env[:attack_len] = np.linspace(0.0, 1.0, attack_len, dtype=np.float32)

            release_len = min(int(0.30 * sample_rate), actual_samples)
            if release_len > 0:
                env[-release_len:] *= np.linspace(1.0, 0.0, release_len, dtype=np.float32)

            # Decay factor for prolonged notes
            decay_factor = np.exp(-1.5 * t)
            env *= decay_factor

            for p in pitches:
                freq = float(p.frequency)
                # Harmonic overtone series for rich instrument timbre
                tone = (
                    0.58 * np.sin(2.0 * np.pi * freq * t) +
                    0.24 * np.sin(2.0 * np.pi * freq * 2.0 * t) +
                    0.12 * np.sin(2.0 * np.pi * freq * 3.0 * t) +
                    0.06 * np.sin(2.0 * np.pi * freq * 4.0 * t)
                ) * env

                channel_gain = float(gain) * 0.4
                audio_left[start_idx:end_idx] += tone * channel_gain
                audio_right[start_idx:end_idx] += tone * channel_gain

        # Master peak normalization to prevent clipping distortion
        peak = max(float(np.max(np.abs(audio_left))), float(np.max(np.abs(audio_right))), 1e-6)
        if peak > 0.95:
            scale = 0.90 / peak
            audio_left *= scale
            audio_right *= scale

        # Convert to interleaved 16-bit PCM
        audio_left_int = np.clip(audio_left * 32767.0, -32768, 32767).astype(np.int16)
        audio_right_int = np.clip(audio_right * 32767.0, -32768, 32767).astype(np.int16)

        stereo_interleaved = np.empty((total_samples * 2,), dtype=np.int16)
        stereo_interleaved[0::2] = audio_left_int
        stereo_interleaved[1::2] = audio_right_int

        with wave.open(str(target_wav), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(stereo_interleaved.tobytes())

        val_info = validate_wav_file(target_wav)
        if not val_info["is_valid"]:
            return False, target_wav, {
                "error": f"WAV file validation failed: {val_info.get('error')}",
                "validation": val_info,
            }

        return True, target_wav, {
            "status": "success",
            "wav_path": str(target_wav),
            "synthesizer": "builtin_pure_python_renderer",
            "validation": val_info,
        }

    except Exception as exc:
        return False, None, {"error": f"Built-in software synthesis failed: {exc}"}


def convert_midi_to_wav(
    midi_path: Union[str, Path],
    output_wav_path: Optional[Union[str, Path]] = None,
    soundfont_path: Optional[Union[str, Path]] = None,
    fluidsynth_path: Optional[Union[str, Path]] = None,
    sample_rate: int = 44100,
    gain: float = 0.6,
    allow_builtin_fallback: bool = True,
) -> Tuple[bool, Optional[Path], Dict[str, Any]]:
    """
    Convert a MIDI file to a playable WAV audio file using FluidSynth (or built-in pure-Python synthesizer fallback).

    Returns:
        (success: bool, output_wav_path: Optional[Path], info_dict: dict)
    """
    midi_path = Path(midi_path).resolve()
    if not midi_path.exists():
        return False, None, {"error": f"Input MIDI file not found: {midi_path}"}

    # 1. Detect tools and SoundFont
    fs_exe = detect_fluidsynth(fluidsynth_path)
    sf_file = detect_soundfont(soundfont_path)

    if not fs_exe or not sf_file:
        if allow_builtin_fallback and not fluidsynth_path and not soundfont_path:
            # Fall back to high-quality built-in pure-Python synthesizer
            return render_midi_with_builtin_synth(
                midi_path=midi_path,
                output_wav_path=output_wav_path,
                sample_rate=sample_rate,
                gain=gain,
            )

        guide = print_missing_setup_instructions(
            fluidsynth_found=(fs_exe is not None),
            soundfont_found=(sf_file is not None),
        )
        return False, None, {
            "status": "renderer_unavailable",
            "fluidsynth_found": fs_exe is not None,
            "soundfont_found": sf_file is not None,
            "message": guide,
        }

    # 2. Resolve output WAV path
    if output_wav_path is None:
        target_wav = AUDIO_OUTPUT_DIR / f"{midi_path.stem}.wav"
    else:
        target_wav = Path(output_wav_path).resolve()

    target_wav.parent.mkdir(parents=True, exist_ok=True)

    # 3. Construct and invoke FluidSynth command
    # Syntax: fluidsynth -ni -g <gain> -r <sample_rate> -F <output.wav> <soundfont.sf2> <input.mid>
    cmd = [
        str(fs_exe),
        "-ni",                       # No interactive shell, no MIDI input
        "-g", str(gain),             # Master gain
        "-r", str(sample_rate),      # Sample rate (44100 Hz)
        "-F", str(target_wav),       # Fast render to file
        str(sf_file),                # SoundFont
        str(midi_path),              # Input MIDI file
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            return False, None, {
                "error": f"FluidSynth rendering failed (exit code {result.returncode})",
                "stderr": result.stderr.strip(),
                "stdout": result.stdout.strip(),
            }

        # 4. Validate output audio
        val_info = validate_wav_file(target_wav)
        if not val_info["is_valid"]:
            return False, target_wav, {
                "error": f"WAV file validation failed: {val_info.get('error')}",
                "validation": val_info,
            }

        return True, target_wav, {
            "status": "success",
            "wav_path": str(target_wav),
            "fluidsynth": str(fs_exe),
            "soundfont": str(sf_file),
            "validation": val_info,
        }

    except subprocess.TimeoutExpired:
        return False, None, {"error": "FluidSynth rendering timed out after 120 seconds"}
    except Exception as exc:
        return False, None, {"error": f"Unexpected error executing FluidSynth: {exc}"}


def render_audio_cli():
    """Command line interface for render_audio.py."""
    parser = argparse.ArgumentParser(
        description="Convert generated MIDI into playable audio using FluidSynth (AI Music Studio)."
    )
    parser.add_argument("midi_file", type=str, help="Path to the input .mid file")
    parser.add_argument("--output", "-o", type=str, default=None, help="Path to output WAV file")
    parser.add_argument("--soundfont", "-sf", type=str, default=None, help="Path to SoundFont (.sf2)")
    parser.add_argument("--fluidsynth", "-fs", type=str, default=None, help="Path to FluidSynth executable")
    parser.add_argument("--sample-rate", "-r", type=int, default=44100, help="Output sample rate (Hz)")
    parser.add_argument("--gain", "-g", type=float, default=0.6, help="Audio gain factor (0.0 to 1.0)")
    parser.add_argument("--check-only", action="store_true", help="Only check FluidSynth and SoundFont availability")

    args = parser.parse_args()

    # If check-only requested
    if args.check_only or args.midi_file == "--check":
        fs = detect_fluidsynth(args.fluidsynth)
        sf = detect_soundfont(args.soundfont)
        ff = detect_ffmpeg()
        print("=== Audio Rendering Diagnostics ===")
        print(f"  FluidSynth : {fs if fs else '[NOT DETECTED]'}")
        print(f"  SoundFont  : {sf if sf else '[NOT DETECTED]'}")
        print(f"  FFmpeg     : {ff if ff else '[NOT DETECTED]'}")
        if not fs or not sf:
            print(print_missing_setup_instructions(fs is not None, sf is not None))
        else:
            print("\n[OK] Ready for high-quality audio rendering!")
        return 0

    midi_path = Path(args.midi_file)
    if not midi_path.exists():
        print(f"Error: MIDI file not found at: {midi_path}", file=sys.stderr)
        return 1

    print("=================================================================")
    print("            AI MUSIC STUDIO - AUDIO RENDERING")
    print("=================================================================")
    print(f"Input MIDI : {midi_path}")

    success, wav_path, info = convert_midi_to_wav(
        midi_path=midi_path,
        output_wav_path=args.output,
        soundfont_path=args.soundfont,
        fluidsynth_path=args.fluidsynth,
        sample_rate=args.sample_rate,
        gain=args.gain,
    )

    if success:
        print(f"[+] Successfully converted to WAV audio!")
        print(f"    Audio Path    : {wav_path}")
        print(f"    File Size     : {info['validation']['file_size_bytes']:,} bytes")
        print(f"    Duration      : {info['validation']['duration_seconds']} seconds")
        print(f"    Sample Rate   : {info['validation']['sample_rate_hz']} Hz")
        print(f"    Channels      : {info['validation']['num_channels']}")
        print("=================================================================")
        return 0
    else:
        if info.get("status") == "renderer_unavailable":
            print(info["message"])
            print("[INFO] Audio rendering skipped gracefully (renderer unavailable).")
            print("[INFO] MIDI file remains fully intact and usable.")
            return 0
        else:
            print(f"[-] Audio rendering error: {info.get('error')}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    sys.exit(render_audio_cli())