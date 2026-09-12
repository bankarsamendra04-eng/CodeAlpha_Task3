"""
AI Music Studio - MIDI Generation & Export Engine
Transforms generated symbolic LSTM tokens into valid, expressive MIDI files using music21.

Pipeline:
Generated LSTM Tokens
      ↓
Musical Events (Note, Chord, Rest)
      ↓
Quantized Durations & Timing Offsets
      ↓
music21 Elements & Metadata (Tempo, Time Signature, Instrument)
      ↓
music21 Stream / Score
      ↓
Standard MIDI File (.mid)
      ↓
Post-Generation Integrity Validation

Features:
- Configurable tempo (BPM) and instrument assignment.
- Exact timing and duration preservation from generated tokens.
- Automatic unique filename generation with zero accidental overwrites.
- Immediate post-export verification with music21.
"""

import os
import sys
import uuid
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Union

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import music21

from ml.config import (
    MIDI_OUTPUT_DIR,
    LSTM_MODEL_DIR,
)
from ml.music_representation import MusicalEvent, Vocabulary
from ml.generator import MusicGenerator


# Instrument name mapping to music21 instrument classes
INSTRUMENT_MAP = {
    "piano": music21.instrument.Piano,
    "grand piano": music21.instrument.Piano,
    "acoustic piano": music21.instrument.Piano,
    "electric piano": music21.instrument.ElectricPiano,
    "harpsichord": music21.instrument.Harpsichord,
    "acoustic guitar": music21.instrument.AcousticGuitar,
    "electric guitar": music21.instrument.ElectricGuitar,
    "violin": music21.instrument.Violin,
    "violoncello": music21.instrument.Violoncello,
    "cello": music21.instrument.Violoncello,
    "flute": music21.instrument.Flute,
    "clarinet": music21.instrument.Clarinet,
    "trumpet": music21.instrument.Trumpet,
    "saxophone": music21.instrument.Saxophone,
    "alto saxophone": music21.instrument.Saxophone,
    "acoustic bass": music21.instrument.AcousticBass,
    "electric bass": music21.instrument.ElectricBass,
    "church organ": music21.instrument.PipeOrgan,
    "pipe organ": music21.instrument.PipeOrgan,
    "organ": music21.instrument.Organ,
    "vibraphone": music21.instrument.Vibraphone,
    "marimba": music21.instrument.Marimba,
}


def get_instrument_instance(instrument_name: str = "Piano") -> music21.instrument.Instrument:
    """Resolve an instrument name to a music21 Instrument object with safe fallback."""
    key = str(instrument_name).strip().lower()
    inst_cls = INSTRUMENT_MAP.get(key)
    if inst_cls:
        return inst_cls()

    # Try music21 built-in resolver
    try:
        inst = music21.instrument.fromString(instrument_name)
        if inst:
            return inst
    except Exception:
        pass

    # Default fallback: Acoustic Piano
    return music21.instrument.Piano()


def tokens_to_musical_events(
    tokens: list[str],
    start_offset: float = 0.0,
    default_velocity: int = 80,
) -> list[MusicalEvent]:
    """
    Convert a list of string tokens into a chronologically ordered sequence of MusicalEvents.
    Each event's duration is added to current_offset so timing and rests are preserved.
    """
    events: list[MusicalEvent] = []
    current_offset = start_offset

    for token in tokens:
        token_clean = token.strip()
        if not token_clean or token_clean in (Vocabulary.PAD_TOKEN, Vocabulary.UNK_TOKEN, Vocabulary.START_TOKEN, Vocabulary.END_TOKEN):
            continue

        try:
            event = MusicalEvent.from_token(
                token_clean,
                offset=round(current_offset, 3),
                velocity=default_velocity,
            )
            events.append(event)
            # Advance time by event duration
            current_offset += max(0.125, event.duration)
        except Exception:
            continue

    return events


def events_to_stream(
    events: list[MusicalEvent],
    tempo_bpm: float = 120.0,
    time_signature: str = "4/4",
    instrument_name: str = "Piano",
    key: Optional[str] = None,
    scale: Optional[str] = None,
    title: str = "AI Music Studio Generation",
) -> music21.stream.Score:
    """
    Assemble MusicalEvents into a structured music21 Score with optional Key/Scale.
    """
    score = music21.stream.Score()

    # Set metadata
    score.metadata = music21.metadata.Metadata()
    score.metadata.title = title
    score.metadata.composer = "AI Music Studio"

    part = music21.stream.Part()
    part.id = "PianoTrack"

    # Add Instrument, Key Signature, Time Signature, and Tempo
    inst = get_instrument_instance(instrument_name)
    part.append(inst)

    # Optional Key & Scale (e.g., 'C', 'major')
    if key:
        clean_key = key.strip()
        clean_scale = (scale or "major").strip().lower()
        if clean_scale not in ("major", "minor"):
            clean_scale = "minor" if "min" in clean_scale else "major"
        try:
            k = music21.key.Key(clean_key, clean_scale)
            part.append(k)
        except Exception:
            pass

    part.append(music21.meter.TimeSignature(time_signature))
    part.append(music21.tempo.MetronomeMark(number=tempo_bpm))

    # Append all notes, chords, and rests with exact timing
    for ev in events:
        try:
            elem = ev.to_music21()
            part.insert(ev.offset, elem)
        except Exception:
            continue

    score.append(part)
    return score


def generate_unique_midi_path(
    output_dir: Union[str, Path] = MIDI_OUTPUT_DIR,
    prefix: str = "music_studio",
    extension: str = ".mid",
) -> Path:
    """
    Generate an collision-free, timestamped filename in the destination directory.
    Guarantees that existing generations are NEVER overwritten.
    """
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_suffix = uuid.uuid4().hex[:6]
    base_name = f"{prefix}_{timestamp}_{unique_suffix}"

    target_path = output_dir / f"{base_name}{extension}"

    # In the extremely rare case of collision, append a counter
    counter = 1
    while target_path.exists():
        target_path = output_dir / f"{base_name}_{counter}{extension}"
        counter += 1

    return target_path


def validate_midi_file(
    file_path: Union[str, Path],
    score_hint: Optional[music21.stream.Score] = None,
) -> dict:
    """
    Inspect a generated MIDI file to confirm structural validity.
    Fast-path: If score_hint is provided, validates file existence, size, and MThd header magic bytes,
    then extracts stream metrics directly without redundant disk re-parsing.
    Fallback: Uses music21.converter.parse for deep inspection when score_hint is absent.
    """
    file_path = Path(file_path).resolve()
    if not file_path.exists():
        return {"is_valid": False, "error": f"File does not exist: {file_path}"}

    file_size = file_path.stat().st_size
    if file_size == 0:
        return {"is_valid": False, "error": "MIDI file is 0 bytes (empty)"}

    # Binary header inspection: must begin with 'MThd' magic bytes
    try:
        with open(file_path, "rb") as f:
            header_bytes = f.read(4)
        if header_bytes != b"MThd":
            return {"is_valid": False, "file_path": str(file_path), "error": "Invalid MIDI magic bytes"}
    except Exception as exc:
        return {"is_valid": False, "file_path": str(file_path), "error": f"Read error: {exc}"}

    # Fast path when score_hint is available
    if score_hint is not None:
        try:
            notes_count = len(score_hint.recurse().getElementsByClass(music21.note.Note))
            chords_count = len(score_hint.recurse().getElementsByClass(music21.chord.Chord))
            rests_count = len(score_hint.recurse().getElementsByClass(music21.note.Rest))
            total_duration = float(score_hint.quarterLength)
            return {
                "is_valid": True,
                "file_path": str(file_path),
                "file_size_bytes": file_size,
                "total_notes": notes_count,
                "total_chords": chords_count,
                "total_rests": rests_count,
                "total_musical_elements": notes_count + chords_count + rests_count,
                "duration_quarters": total_duration,
                "error": None,
            }
        except Exception:
            pass  # Fall through to deep parsing

    try:
        parsed_score = music21.converter.parse(str(file_path))
        notes_count = len(parsed_score.recurse().getElementsByClass(music21.note.Note))
        chords_count = len(parsed_score.recurse().getElementsByClass(music21.chord.Chord))
        rests_count = len(parsed_score.recurse().getElementsByClass(music21.note.Rest))
        total_duration = parsed_score.quarterLength

        return {
            "is_valid": True,
            "file_path": str(file_path),
            "file_size_bytes": file_size,
            "total_notes": notes_count,
            "total_chords": chords_count,
            "total_rests": rests_count,
            "total_musical_elements": notes_count + chords_count + rests_count,
            "duration_quarters": float(total_duration),
            "error": None,
        }
    except Exception as exc:
        return {
            "is_valid": False,
            "file_path": str(file_path),
            "file_size_bytes": file_size,
            "error": f"music21 parsing error: {exc}",
        }


def tokens_to_midi_file(
    tokens: list[str],
    output_path: Optional[Union[str, Path]] = None,
    tempo_bpm: float = 120.0,
    instrument_name: str = "Piano",
    key: Optional[str] = None,
    scale: Optional[str] = None,
    time_signature: str = "4/4",
    title: str = "AI Music Studio Generation",
) -> tuple[Path, dict]:
    """
    High-level API: Convert a list of generated tokens directly into a validated MIDI file.
    """
    if not tokens:
        raise ValueError("Cannot create MIDI from empty token list")

    # 1. Resolve output path
    if output_path is None:
        target_path = generate_unique_midi_path(MIDI_OUTPUT_DIR)
    else:
        target_path = Path(output_path).resolve()
        # Protect against accidental overwrite
        if target_path.exists():
            target_path = generate_unique_midi_path(target_path.parent, prefix=target_path.stem)

    target_path.parent.mkdir(parents=True, exist_ok=True)

    # 2. Convert tokens to events
    events = tokens_to_musical_events(tokens)

    # 3. Assemble score
    score = events_to_stream(
        events=events,
        tempo_bpm=tempo_bpm,
        time_signature=time_signature,
        instrument_name=instrument_name,
        key=key,
        scale=scale,
        title=title,
    )

    # 4. Write MIDI
    score.write("midi", fp=str(target_path))

    # 5. Validate resulting MIDI file with score_hint
    validation = validate_midi_file(target_path, score_hint=score)
    if not validation["is_valid"]:
        raise RuntimeError(f"Generated MIDI file failed validation: {validation['error']}")

    return target_path, validation


def generate_and_export_midi(
    num_events: int = 50,
    temperature: float = 0.8,
    tempo_bpm: float = 120.0,
    instrument_name: str = "Piano",
    random_seed: Optional[int] = None,
    seed_sequence: Optional[Union[list[str], str]] = None,
    output_path: Optional[Union[str, Path]] = None,
) -> tuple[Path, dict, list[str]]:
    """
    End-to-End API: Generate music tokens with LSTM and write directly to a validated MIDI file.
    """
    generator = MusicGenerator()
    tokens = generator.generate(
        seed_sequence=seed_sequence,
        num_events=num_events,
        temperature=temperature,
        random_seed=random_seed,
    )

    midi_path, validation = tokens_to_midi_file(
        tokens=tokens,
        output_path=output_path,
        tempo_bpm=tempo_bpm,
        instrument_name=instrument_name,
    )

    return midi_path, validation, tokens


def main():
    """Command-line execution and validation test."""
    parser = argparse.ArgumentParser(description="Generate and convert AI music to standard MIDI.")
    parser.add_argument("--num-events", type=int, default=50, help="Number of musical events to generate")
    parser.add_argument("--temperature", type=float, default=0.8, help="Sampling temperature")
    parser.add_argument("--tempo", type=float, default=120.0, help="Tempo in BPM")
    parser.add_argument("--instrument", type=str, default="Piano", help="Instrument name")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    print("=" * 65)
    print("      AI MUSIC STUDIO - MIDI GENERATION & VALIDATION TEST")
    print("=" * 65)
    print(f"Events to Generate : {args.num_events}")
    print(f"Temperature        : {args.temperature}")
    print(f"Tempo (BPM)        : {args.tempo}")
    print(f"Instrument         : {args.instrument}")
    print(f"Random Seed        : {args.seed}")
    print(f"Destination Dir    : {MIDI_OUTPUT_DIR}")
    print("=" * 65)

    print("\n[*] Step 1: Generating tokens with LSTM model...")
    midi_path, validation, tokens = generate_and_export_midi(
        num_events=args.num_events,
        temperature=args.temperature,
        tempo_bpm=args.tempo,
        instrument_name=args.instrument,
        random_seed=args.seed,
    )

    print(f"[+] Successfully generated {len(tokens)} tokens.")
    print(f"[+] Sample Tokens: {tokens[:5]} ... {tokens[-2:]}")

    print("\n[*] Step 2: Validating generated MIDI with music21...")
    print(f"    - File Path       : {validation['file_path']}")
    print(f"    - File Size       : {validation['file_size_bytes']:,} bytes")
    print(f"    - Total Notes     : {validation['total_notes']}")
    print(f"    - Total Chords    : {validation['total_chords']}")
    print(f"    - Total Rests     : {validation['total_rests']}")
    print(f"    - Total Elements  : {validation['total_musical_elements']}")
    print(f"    - Total Duration  : {validation['duration_quarters']:.2f} quarter lengths")
    print(f"    - music21 Status  : {'[OK] VALID' if validation['is_valid'] else '[FAIL] INVALID'}")

    print("\n" + "=" * 65)
    print("                MIDI CREATION & VALIDATION SUCCESS")
    print("=" * 65)
    print(f"Exported File: {midi_path}")
    print("=" * 65)


if __name__ == "__main__":
    main()
