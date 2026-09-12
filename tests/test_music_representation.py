"""
Unit Tests for Music Representation & Tokenization
Tests:
- Note extraction
- Chord extraction
- Duration extraction & quantization
- Tokenization (to_token and from_token)
- Vocabulary creation (bidirectional mapping, encode/decode, save/load)
- Extraction on a real MAESTRO file
"""

import sys
import os
import pathlib
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.music_representation import (
    MusicalEvent,
    Vocabulary,
    quantize_duration,
    extract_musical_events_from_midi,
    midi_to_tokens,
    STANDARD_DURATIONS,
)
from ml.config import DATASET_PATH


def test_note_extraction_and_properties():
    """Test Note creation, pitch names, and token format."""
    # Middle C (MIDI 60)
    note_event = MusicalEvent("NOTE", (60,), duration=1.0, offset=0.0, velocity=80)
    assert note_event.event_type == "NOTE"
    assert note_event.pitches == (60,)
    assert note_event.pitch_names == "C4"
    assert note_event.duration == 1.0
    assert note_event.velocity == 80
    assert note_event.to_token() == "NOTE_60_d1.00"


def test_chord_extraction_and_sorting():
    """Test Chord creation with multiple pitches sorted deterministically."""
    # C Major Triad: C4 (60), E4 (64), G4 (67)
    chord_event = MusicalEvent("CHORD", (60, 64, 67), duration=2.0, offset=1.0, velocity=90)
    assert chord_event.event_type == "CHORD"
    assert chord_event.pitches == (60, 64, 67)
    assert chord_event.pitch_names == "C4.E4.G4"
    assert chord_event.to_token() == "CHORD_60.64.67_d2.00"

    # Verify deterministic sorting of pitches
    unsorted_chord = MusicalEvent("CHORD", tuple(sorted([67, 60, 64])), 1.0, 0.0, 80)
    assert unsorted_chord.pitches == (60, 64, 67)
    assert unsorted_chord.to_token() == "CHORD_60.64.67_d1.00"


def test_duration_quantization():
    """Test that continuous durations are mapped to standard musical fractions."""
    # Close to eighth note (0.5)
    assert quantize_duration(0.48) == 0.5
    assert quantize_duration(0.52) == 0.5

    # Close to 16th note (0.25)
    assert quantize_duration(0.23) == 0.25

    # Close to quarter note (1.0)
    assert quantize_duration(0.98) == 1.0

    # Rest duration quantization
    rest_event = MusicalEvent("REST", tuple(), duration=0.5, offset=2.0, velocity=0)
    assert rest_event.to_token() == "REST_d0.50"


def test_tokenization_bidirectional_roundtrip():
    """Test that MusicalEvents can be converted to tokens and reconstructed accurately."""
    # 1. Note roundtrip
    original_note = MusicalEvent("NOTE", (72,), 0.5, offset=4.0, velocity=85)
    token_str = original_note.to_token()
    reconstructed_note = MusicalEvent.from_token(token_str, offset=4.0, velocity=85)
    assert reconstructed_note.event_type == original_note.event_type
    assert reconstructed_note.pitches == original_note.pitches
    assert reconstructed_note.duration == original_note.duration

    # 2. Chord roundtrip
    original_chord = MusicalEvent("CHORD", (48, 55, 60), 1.5, offset=8.0, velocity=75)
    chord_token = original_chord.to_token()
    reconstructed_chord = MusicalEvent.from_token(chord_token, offset=8.0, velocity=75)
    assert reconstructed_chord.event_type == original_chord.event_type
    assert reconstructed_chord.pitches == original_chord.pitches
    assert reconstructed_chord.duration == original_chord.duration

    # 3. Rest roundtrip
    original_rest = MusicalEvent("REST", tuple(), 0.5, offset=12.0, velocity=0)
    rest_token = original_rest.to_token()
    reconstructed_rest = MusicalEvent.from_token(rest_token, offset=12.0, velocity=0)
    assert reconstructed_rest.event_type == "REST"
    assert reconstructed_rest.duration == 0.5


def test_vocabulary_creation_and_mapping(tmp_path):
    """Test vocabulary building, token-to-integer, integer-to-token, and persistence."""
    sequences = [
        ["NOTE_60_d0.50", "NOTE_64_d0.50", "NOTE_67_d1.00", "REST_d0.50"],
        ["CHORD_60.64.67_d1.00", "NOTE_60_d0.50", "NOTE_72_d0.50"],
    ]

    vocab = Vocabulary()
    vocab.build_from_sequences(sequences)

    # Check special tokens
    assert vocab.token_to_id["<PAD>"] == 0
    assert vocab.token_to_id["<UNK>"] == 1
    assert vocab.token_to_id["<START>"] == 2
    assert vocab.token_to_id["<END>"] == 3

    # Check frequent tokens added
    assert "NOTE_60_d0.50" in vocab.token_to_id
    assert "CHORD_60.64.67_d1.00" in vocab.token_to_id

    # Test encoding
    test_seq = ["NOTE_60_d0.50", "CHORD_60.64.67_d1.00", "UNKNOWN_NONEXISTENT_TOKEN"]
    encoded = vocab.encode(test_seq)
    assert len(encoded) == 3
    assert encoded[2] == vocab.token_to_id["<UNK>"]  # Unknown token mapped to <UNK>

    # Test decoding
    decoded = vocab.decode(encoded)
    assert decoded[0] == "NOTE_60_d0.50"
    assert decoded[1] == "CHORD_60.64.67_d1.00"
    assert decoded[2] == "<UNK>"

    # Test save and load
    vocab_file = tmp_path / "test_vocab.json"
    vocab.save(vocab_file)
    assert vocab_file.exists()

    loaded_vocab = Vocabulary.load(vocab_file)
    assert len(loaded_vocab) == len(vocab)
    assert loaded_vocab.token_to_id == vocab.token_to_id
    assert loaded_vocab.id_to_token == vocab.id_to_token


def test_extraction_on_real_maestro_file():
    """Test extraction of real events from an actual MAESTRO MIDI file."""
    midi_files = list(DATASET_PATH.rglob("*.mid")) + list(DATASET_PATH.rglob("*.midi"))
    if not midi_files:
        pytest.skip("MAESTRO dataset not found on local path")

    sample_file = midi_files[0]
    events = extract_musical_events_from_midi(sample_file)

    assert len(events) > 0
    note_events = [e for e in events if e.event_type == "NOTE"]
    chord_events = [e for e in events if e.event_type == "CHORD"]

    assert len(note_events) > 0
    assert len(chord_events) > 0

    # Verify first few events have valid pitches and durations
    for e in events[:20]:
        assert e.duration > 0
        assert e.offset >= 0
        if e.event_type in ("NOTE", "CHORD"):
            assert len(e.pitches) >= 1
            for p in e.pitches:
                assert 21 <= p <= 108  # Standard 88-key piano range
