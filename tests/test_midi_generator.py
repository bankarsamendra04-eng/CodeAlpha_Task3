"""Unit tests for the MIDI generation module ml/midi_generator.py."""

from pathlib import Path
import pytest
import music21

from ml.midi_generator import (
    tokens_to_musical_events,
    events_to_stream,
    tokens_to_midi_file,
    validate_midi_file,
    generate_unique_midi_path,
    INSTRUMENT_MAP,
)


def test_tokens_to_musical_events():
    """Verify that LSTM tokens convert cleanly into structured MusicalEvents."""
    tokens = [
        "NOTE_60_d1.00",
        "CHORD_60.64.67_d0.50",
        "REST_d0.25",
        "NOTE_62_d2.00",
    ]
    events = tokens_to_musical_events(tokens)
    assert len(events) == 4

    # Note
    assert events[0].event_type == "NOTE"
    assert events[0].pitches == (60,)
    assert pytest.approx(events[0].duration) == 1.0

    # Chord
    assert events[1].event_type == "CHORD"
    assert events[1].pitches == (60, 64, 67)
    assert pytest.approx(events[1].duration) == 0.5

    # Rest
    assert events[2].event_type == "REST"
    assert pytest.approx(events[2].duration) == 0.25

    # Note
    assert events[3].event_type == "NOTE"
    assert events[3].pitches == (62,)
    assert pytest.approx(events[3].duration) == 2.0


def test_events_to_stream():
    """Verify conversion of events to a music21 Stream with tempo and instrument."""
    tokens = ["NOTE_60_d1.00", "CHORD_64.67_d1.00", "REST_d0.50", "NOTE_72_d0.50"]
    events = tokens_to_musical_events(tokens)

    stream = events_to_stream(
        events=events,
        tempo_bpm=140.0,
        instrument_name="Acoustic Guitar",
        title="Test Composition",
    )

    assert isinstance(stream, music21.stream.Score)
    notes = list(stream.recurse().getElementsByClass("Note"))
    chords = list(stream.recurse().getElementsByClass("Chord"))
    rests = list(stream.recurse().getElementsByClass("Rest"))
    tempos = list(stream.recurse().getElementsByClass("MetronomeMark"))
    instruments = list(stream.recurse().getElementsByClass("Instrument"))

    assert len(notes) == 2
    assert len(chords) == 1
    assert len(rests) == 1
    assert len(tempos) >= 1
    assert tempos[0].number == 140.0
    assert len(instruments) >= 1


def test_tokens_to_midi_file_and_validation(tmp_path: Path):
    """Test generating a MIDI file on disk and validating it with music21."""
    tokens = [
        "NOTE_60_d0.50",
        "NOTE_62_d0.50",
        "NOTE_64_d0.50",
        "CHORD_65.69.72_d1.00",
        "REST_d0.50",
        "NOTE_72_d1.00",
    ]

    out_file = tmp_path / "test_piece.mid"
    exported_path, val_info = tokens_to_midi_file(
        tokens=tokens,
        output_path=out_file,
        tempo_bpm=110.0,
        instrument_name="Violin",
        title="Test Piece",
    )

    assert exported_path.exists()
    assert exported_path.stat().st_size > 0

    assert val_info["is_valid"] is True
    assert val_info["total_notes"] == 4
    assert val_info["total_chords"] == 1
    assert val_info["total_rests"] == 1
    assert val_info["duration_quarters"] > 0

    # Also independently validate with music21
    direct_val = validate_midi_file(exported_path)
    assert direct_val["is_valid"] is True
    assert direct_val["total_notes"] == 4


def test_unique_filename_collision_avoidance(tmp_path: Path):
    """Ensure generate_unique_midi_path never overwrites existing files."""
    p1 = generate_unique_midi_path(tmp_path, prefix="test")
    p1.touch()

    p2 = generate_unique_midi_path(tmp_path, prefix="test")
    assert p1 != p2
    assert not p2.exists()


def test_special_tokens_handled_gracefully():
    """Verify that special tokens (PAD, UNK, START, END) are safely filtered out."""
    tokens = [
        "<PAD>",
        "NOTE_70_d0.50",
        "<START>",
        "CHORD_60.72_d1.00",
        "<END>",
    ]
    events = tokens_to_musical_events(tokens)
    assert len(events) == 2
    assert events[0].pitches == (70,)
    assert events[1].pitches == (60, 72)