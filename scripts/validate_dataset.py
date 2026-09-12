"""
AI Music Studio - Full Dataset Validation Script
Validates the ENTIRE MAESTRO MIDI dataset using music21 with multi-core parallelism.
Verifies file integrity, musical event contents, note/chord extractability,
and outputs dataset/validation_report.csv.
"""

import os
import sys
import time
import pathlib
import concurrent.futures
import pandas as pd
from dotenv import load_dotenv
import music21

# Load environment variables
load_dotenv()

DEFAULT_PATHS = [
    os.getenv("DATASET_PATH"),
    r"C:\Users\banka\OneDrive\Desktop\maestro-v3.0.0-midi",
    r"C:\Users\banka\OneDrive\Desktop\maestro-v3.0.0-midi\maestro-v3.0.0",
    "dataset/midi",
]


def find_dataset_dir():
    for c in DEFAULT_PATHS:
        if c and os.path.exists(c):
            return pathlib.Path(c).resolve()
    return None


def validate_single_midi(fpath_str):
    """
    Validates a single MIDI file using music21:
    1. Attempt to open it.
    2. Verify it contains musical events.
    3. Extract notes and chords.
    4. Detect parsing errors.
    5. Return diagnostics.
    """
    fpath = pathlib.Path(fpath_str)
    try:
        f_size = os.path.getsize(fpath_str)
        if f_size == 0:
            return {
                "file_path": fpath_str,
                "filename": fpath.name,
                "file_size_bytes": 0,
                "valid": False,
                "notes": 0,
                "chords": 0,
                "events": 0,
                "tracks": 0,
                "error": "Empty file (0 bytes)",
            }

        # Step 1: Open and read with music21
        mf = music21.midi.MidiFile()
        mf.open(fpath_str)
        mf.read()
        mf.close()

        # Step 2: Verify tracks
        track_count = len(mf.tracks)
        if track_count == 0:
            return {
                "file_path": fpath_str,
                "filename": fpath.name,
                "file_size_bytes": f_size,
                "valid": False,
                "notes": 0,
                "chords": 0,
                "events": 0,
                "tracks": 0,
                "error": "No tracks found in MIDI file",
            }

        total_events = 0
        note_count = 0
        chord_count = 0

        # Step 3: Extract notes and chords
        for track in mf.tracks:
            total_events += len(track.events)
            time_offset = 0
            simultaneous_notes = {}

            for ev in track.events:
                if ev.type == "DeltaTime":
                    time_offset += ev.time
                elif ev.type == music21.midi.ChannelVoiceMessages.NOTE_ON and getattr(ev, "velocity", 0) > 0:
                    simultaneous_notes.setdefault(time_offset, []).append(ev.pitch)

            for t_step, pitches in simultaneous_notes.items():
                if len(pitches) > 1:
                    chord_count += 1
                elif len(pitches) == 1:
                    note_count += 1

        # Step 4: Verify musical content
        is_valid = (note_count + chord_count) > 0
        err_msg = "" if is_valid else "No note_on events found (empty musical stream)"

        return {
            "file_path": fpath_str,
            "filename": fpath.name,
            "file_size_bytes": f_size,
            "valid": is_valid,
            "notes": note_count,
            "chords": chord_count,
            "events": total_events,
            "tracks": track_count,
            "error": err_msg,
        }

    except Exception as exc:
        # Step 5: Detect parsing errors
        return {
            "file_path": fpath_str,
            "filename": fpath.name,
            "file_size_bytes": os.path.getsize(fpath_str) if os.path.exists(fpath_str) else 0,
            "valid": False,
            "notes": 0,
            "chords": 0,
            "events": 0,
            "tracks": 0,
            "error": f"music21 parse error: {str(exc)}",
        }


def run_dataset_validation():
    dataset_dir = find_dataset_dir()
    if not dataset_dir:
        print("[ERROR] Could not locate MAESTRO dataset directory. Set DATASET_PATH in .env", flush=True)
        sys.exit(1)

    print("==================================================", flush=True)
    print("  AI Music Studio - Full Dataset Validation       ", flush=True)
    print("==================================================", flush=True)
    print(f"Target MAESTRO path: {dataset_dir}\n", flush=True)

    print("Discovering all MIDI files recursively...", flush=True)
    midi_files = sorted([str(f.resolve()) for f in (list(dataset_dir.rglob("*.mid")) + list(dataset_dir.rglob("*.midi")))])
    total_files = len(midi_files)
    print(f"Found {total_files} total MIDI files across all subdirectories.\n", flush=True)

    if total_files == 0:
        print("[ERROR] No MIDI files found to validate!", flush=True)
        sys.exit(1)

    workers = min(8, os.cpu_count() or 4)
    print(f"Validating ENTIRE dataset with music21 using {workers} parallel CPU workers...", flush=True)
    t0 = time.time()

    valid_files = 0
    invalid_files = 0
    problematic = []
    total_notes = 0
    total_chords = 0
    total_bytes = 0
    results = []

    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        for idx, diag in enumerate(executor.map(validate_single_midi, midi_files, chunksize=10), 1):
            total_bytes += diag["file_size_bytes"]

            if diag["valid"]:
                valid_files += 1
                total_notes += diag["notes"]
                total_chords += diag["chords"]
                status = "VALID"
            else:
                invalid_files += 1
                problematic.append((diag["file_path"], diag["error"]))
                status = "INVALID"

            results.append({
                "file_path": diag["file_path"],
                "filename": diag["filename"],
                "file_size_bytes": diag["file_size_bytes"],
                "number_of_notes": diag["notes"],
                "number_of_chords": diag["chords"],
                "total_events": diag["events"],
                "tracks": diag["tracks"],
                "status": status,
                "error_message": diag["error"],
            })

            # Progress every 100 files or at completion
            if idx % 100 == 0 or idx == total_files:
                pct = (idx / total_files) * 100
                elapsed = time.time() - t0
                rate = idx / elapsed if elapsed > 0 else 0
                print(
                    f"  [Progress {idx:4d}/{total_files} ({pct:5.1f}%)] "
                    f"Valid: {valid_files:4d} | Invalid: {invalid_files:2d} | "
                    f"Speed: {rate:5.1f} files/s | Elapsed: {elapsed:4.1f}s",
                    flush=True,
                )

    elapsed_total = time.time() - t0

    # Save validation report
    output_dir = pathlib.Path("dataset")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_csv = output_dir / "validation_report.csv"
    pd.DataFrame(results).to_csv(report_csv, index=False)
    print(f"\n[OK] Validation report saved to {report_csv}", flush=True)

    print("\n" + "=" * 55, flush=True)
    print("           DATASET VALIDATION SUMMARY            ", flush=True)
    print("=" * 55, flush=True)
    print(f"1. Dataset Path:           {dataset_dir}", flush=True)
    print(f"2. Total Files Discovered: {total_files}", flush=True)
    print(f"3. Valid Files:            {valid_files}", flush=True)
    print(f"4. Invalid Files:          {invalid_files}", flush=True)
    print(f"5. Total Dataset Size:     {total_bytes / (1024 * 1024):.2f} MB", flush=True)
    print(f"6. Successfully Parsed:    {valid_files} / {total_files} ({(valid_files/total_files)*100:.1f}%)", flush=True)
    print(f"7. Total Notes Extracted:  {total_notes:,}", flush=True)
    print(f"8. Total Chords Extracted: {total_chords:,}", flush=True)
    print(f"9. Problematic Files:      {len(problematic)}", flush=True)
    if problematic:
        for p_file, p_err in problematic[:10]:
            print(f"    - {pathlib.Path(p_file).name}: {p_err}", flush=True)
    else:
        print("    - None! 100% of MIDI files are valid and healthy.", flush=True)
    print(f"10. Validation Time:       {elapsed_total:.2f} seconds ({total_files/elapsed_total:.1f} files/s)", flush=True)
    print("=" * 55, flush=True)


if __name__ == "__main__":
    run_dataset_validation()
