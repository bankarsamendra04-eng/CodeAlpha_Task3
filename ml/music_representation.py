"""
AI Music Studio - Music Representation & Tokenization Engine
Converts raw symbolic MIDI data into a structured, machine-readable token representation
suitable for training sequence models (LSTM/RNN).
Uses music21 for note, chord, duration, and stream operations.
"""

import os
import json
import pathlib
from dataclasses import dataclass
from typing import Optional, Union
import music21

# Standard musical duration quantization grid (in quarter lengths)
STANDARD_DURATIONS = [
    0.125,  # 32nd note
    0.25,   # 16th note
    0.333,  # Triplet 8th
    0.5,    # 8th note
    0.75,   # Dotted 8th
    1.0,    # Quarter note
    1.5,    # Dotted quarter
    2.0,    # Half note
    3.0,    # Dotted half
    4.0,    # Whole note
]


def quantize_duration(dur: float) -> float:
    """Quantize continuous note durations to standard musical fractions."""
    if dur <= 0:
        return 0.25
    # Find closest standard duration
    closest = min(STANDARD_DURATIONS, key=lambda d: abs(d - dur))
    # If the duration is very long, round to nearest 0.5
    if dur > 4.0:
        return round(dur * 2) / 2
    return closest


@dataclass(frozen=True)
class MusicalEvent:
    """
    Represents an atomic musical event (Note, Chord, or Rest) with
    pitch, duration, timing offset, and velocity.
    """
    event_type: str        # 'NOTE', 'CHORD', 'REST'
    pitches: tuple[int, ...]  # MIDI pitch integers, deterministically sorted
    duration: float        # Duration in quarter lengths
    offset: float          # Time offset from start in quarter lengths
    velocity: int          # MIDI velocity (0-127)

    @property
    def pitch_names(self) -> str:
        """Return human-readable pitch names (e.g., 'C4' or 'C4.E4.G4')."""
        if self.event_type == "REST":
            return "REST"
        names = [music21.pitch.Pitch(p).nameWithOctave for p in self.pitches]
        return ".".join(names)

    def to_token(self, include_duration: bool = True) -> str:
        """
        Convert the musical event to a deterministic string token.
        Examples:
            Single note:  NOTE_60_d0.50
            Chord:        CHORD_60.64.67_d1.00
            Rest:         REST_d0.50
        """
        dur_str = f"d{self.duration:.2f}"
        if self.event_type == "REST":
            return f"REST_{dur_str}" if include_duration else "REST"
        elif self.event_type == "NOTE":
            pitch_str = str(self.pitches[0])
            return f"NOTE_{pitch_str}_{dur_str}" if include_duration else f"NOTE_{pitch_str}"
        elif self.event_type == "CHORD":
            pitches_str = ".".join(str(p) for p in sorted(self.pitches))
            return f"CHORD_{pitches_str}_{dur_str}" if include_duration else f"CHORD_{pitches_str}"
        return f"UNK_{dur_str}"

    @classmethod
    def from_token(cls, token: str, offset: float = 0.0, velocity: int = 80) -> "MusicalEvent":
        """Reconstruct a MusicalEvent from a string token."""
        parts = token.split("_")
        event_type = parts[0]

        if event_type == "REST":
            dur = float(parts[1][1:]) if len(parts) > 1 and parts[1].startswith("d") else 0.5
            return cls("REST", tuple(), dur, offset, 0)

        elif event_type == "NOTE":
            pitch = int(parts[1])
            dur = float(parts[2][1:]) if len(parts) > 2 and parts[2].startswith("d") else 0.5
            return cls("NOTE", (pitch,), dur, offset, velocity)

        elif event_type == "CHORD":
            pitches = tuple(sorted(int(p) for p in parts[1].split(".") if p.isdigit()))
            dur = float(parts[2][1:]) if len(parts) > 2 and parts[2].startswith("d") else 1.0
            return cls("CHORD", pitches, dur, offset, velocity)

        else:
            return cls("NOTE", (60,), 0.5, offset, velocity)

    def to_music21(self) -> Union[music21.note.Note, music21.chord.Chord, music21.note.Rest]:
        """Convert this event to a native music21 object."""
        dur_obj = music21.duration.Duration(self.duration)
        if self.event_type == "REST":
            r = music21.note.Rest()
            r.duration = dur_obj
            r.offset = self.offset
            return r
        elif self.event_type == "CHORD":
            c = music21.chord.Chord(list(self.pitches))
            c.duration = dur_obj
            c.offset = self.offset
            c.volume.velocity = self.velocity
            return c
        else:
            n = music21.note.Note(self.pitches[0])
            n.duration = dur_obj
            n.offset = self.offset
            n.volume.velocity = self.velocity
            return n


def extract_musical_events_from_midi(
    file_path: Union[str, pathlib.Path],
    chord_threshold_quarters: float = 0.05,
    include_rests: bool = True,
    min_rest_duration: float = 0.25,
) -> list[MusicalEvent]:
    """
    Parse a MIDI file using music21 and extract a deterministically ordered list of MusicalEvents.
    
    Handles:
    - Note pitch & octave
    - Chords (deterministic ascending pitch ordering)
    - Quantized duration
    - Exact timing offset
    - Velocity
    - Rests between notes/chords
    - Safe handling of corrupted/unsupported events
    """
    file_path = pathlib.Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"MIDI file not found: {file_path}")

    mf = music21.midi.MidiFile()
    mf.open(str(file_path))
    mf.read()
    mf.close()

    tpq = mf.ticksPerQuarterNote or 480

    # Step 1: Gather all note-on and note-off events with start/end ticks
    active_notes: dict[tuple[int, int], list[tuple[int, int]]] = {}
    completed_notes: list[dict] = []

    for track in mf.tracks:
        current_tick = 0
        for ev in track.events:
            if ev.type == "DeltaTime":
                current_tick += ev.time
            elif ev.type == music21.midi.ChannelVoiceMessages.NOTE_ON and getattr(ev, "velocity", 0) > 0:
                active_notes.setdefault((ev.channel, ev.pitch), []).append((current_tick, ev.velocity))
            elif (ev.type == music21.midi.ChannelVoiceMessages.NOTE_OFF) or (
                ev.type == music21.midi.ChannelVoiceMessages.NOTE_ON and getattr(ev, "velocity", 0) == 0
            ):
                key = (ev.channel, ev.pitch)
                if key in active_notes and active_notes[key]:
                    start_tick, vel = active_notes[key].pop(0)
                    dur_ticks = max(1, current_tick - start_tick)
                    completed_notes.append({
                        "pitch": ev.pitch,
                        "offset_quarters": start_tick / tpq,
                        "duration_quarters": dur_ticks / tpq,
                        "velocity": vel,
                    })

    if not completed_notes:
        return []

    # Step 2: Sort chronologically by start offset, then by pitch
    completed_notes.sort(key=lambda x: (x["offset_quarters"], x["pitch"]))

    # Step 3: Group near-simultaneous notes into Chords
    events: list[MusicalEvent] = []
    current_group: list[dict] = []
    last_end_offset = 0.0

    for note in completed_notes:
        if not current_group:
            current_group.append(note)
        elif abs(note["offset_quarters"] - current_group[0]["offset_quarters"]) <= chord_threshold_quarters:
            current_group.append(note)
        else:
            # Emit current group
            group_offset = round(current_group[0]["offset_quarters"], 3)

            # Insert rest if there is a gap
            if include_rests and (group_offset - last_end_offset) >= min_rest_duration:
                rest_dur = quantize_duration(group_offset - last_end_offset)
                events.append(MusicalEvent("REST", tuple(), rest_dur, last_end_offset, 0))

            # Build Note or Chord
            unique_pitches = tuple(sorted(set(n["pitch"] for n in current_group)))
            avg_dur = sum(n["duration_quarters"] for n in current_group) / len(current_group)
            quant_dur = quantize_duration(avg_dur)
            avg_vel = int(sum(n["velocity"] for n in current_group) / len(current_group))

            if len(unique_pitches) == 1:
                events.append(MusicalEvent("NOTE", unique_pitches, quant_dur, group_offset, avg_vel))
            else:
                events.append(MusicalEvent("CHORD", unique_pitches, quant_dur, group_offset, avg_vel))

            last_end_offset = max(last_end_offset, group_offset + quant_dur)
            current_group = [note]

    # Emit final group
    if current_group:
        group_offset = round(current_group[0]["offset_quarters"], 3)
        if include_rests and (group_offset - last_end_offset) >= min_rest_duration:
            rest_dur = quantize_duration(group_offset - last_end_offset)
            events.append(MusicalEvent("REST", tuple(), rest_dur, last_end_offset, 0))

        unique_pitches = tuple(sorted(set(n["pitch"] for n in current_group)))
        avg_dur = sum(n["duration_quarters"] for n in current_group) / len(current_group)
        quant_dur = quantize_duration(avg_dur)
        avg_vel = int(sum(n["velocity"] for n in current_group) / len(current_group))

        if len(unique_pitches) == 1:
            events.append(MusicalEvent("NOTE", unique_pitches, quant_dur, group_offset, avg_vel))
        else:
            events.append(MusicalEvent("CHORD", unique_pitches, quant_dur, group_offset, avg_vel))

    return events


def midi_to_tokens(file_path: Union[str, pathlib.Path], include_duration: bool = True) -> list[str]:
    """Convert a MIDI file directly into a list of string tokens."""
    events = extract_musical_events_from_midi(file_path)
    return [ev.to_token(include_duration=include_duration) for ev in events]


class Vocabulary:
    """
    Bidirectional mapping between tokens and integers for model input/output.
    Includes reserved tokens for padding, unknown, start, and end.
    """
    PAD_TOKEN = "<PAD>"
    UNK_TOKEN = "<UNK>"
    START_TOKEN = "<START>"
    END_TOKEN = "<END>"

    def __init__(self):
        self.token_to_id: dict[str, int] = {
            self.PAD_TOKEN: 0,
            self.UNK_TOKEN: 1,
            self.START_TOKEN: 2,
            self.END_TOKEN: 3,
        }
        self.id_to_token: dict[int, str] = {i: t for t, i in self.token_to_id.items()}

    def __len__(self) -> int:
        return len(self.token_to_id)

    def add_token(self, token: str) -> int:
        if token not in self.token_to_id:
            idx = len(self.token_to_id)
            self.token_to_id[token] = idx
            self.id_to_token[idx] = token
            return idx
        return self.token_to_id[token]

    def build_from_sequences(self, sequences: list[list[str]], min_frequency: int = 1) -> "Vocabulary":
        """Build vocabulary from an iterable of token lists."""
        counts: dict[str, int] = {}
        for seq in sequences:
            for token in seq:
                counts[token] = counts.get(token, 0) + 1

        for token, count in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
            if count >= min_frequency:
                self.add_token(token)
        return self

    def encode(self, tokens: list[str]) -> list[int]:
        """Convert tokens to integer IDs (using UNK for unseen tokens)."""
        unk_id = self.token_to_id[self.UNK_TOKEN]
        return [self.token_to_id.get(t, unk_id) for t in tokens]

    def decode(self, ids: list[int]) -> list[str]:
        """Convert integer IDs back to string tokens."""
        return [self.id_to_token.get(idx, self.UNK_TOKEN) for idx in ids]

    def save(self, file_path: Union[str, pathlib.Path]):
        """Save vocabulary to JSON."""
        file_path = pathlib.Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.token_to_id, f, indent=2)

    @classmethod
    def load(cls, file_path: Union[str, pathlib.Path]) -> "Vocabulary":
        """Load vocabulary from JSON."""
        vocab = cls()
        with open(file_path, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        vocab.token_to_id = {k: int(v) for k, v in mapping.items()}
        vocab.id_to_token = {int(v): k for k, v in vocab.token_to_id.items()}
        return vocab


def events_to_midi_file(
    events: list[MusicalEvent],
    output_path: Union[str, pathlib.Path],
    tempo_bpm: float = 120.0,
    time_signature: str = "4/4",
):
    """
    Assemble a list of MusicalEvents into a music21 stream and write to standard MIDI.
    """
    output_path = pathlib.Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    s = music21.stream.Stream()
    s.append(music21.meter.TimeSignature(time_signature))
    s.append(music21.tempo.MetronomeMark(number=tempo_bpm))
    s.append(music21.instrument.Piano())

    for ev in events:
        try:
            m21_elem = ev.to_music21()
            s.append(m21_elem)
        except Exception:
            continue

    s.write("midi", fp=str(output_path))
