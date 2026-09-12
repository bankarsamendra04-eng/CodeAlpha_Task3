"""
AI Music Studio - High-Performance Dataset Preparation Script
Recursively discovers, validates, and indexes the entire MAESTRO MIDI dataset.
Uses multi-process parallelism across CPU cores for maximum throughput.
Generates dataset/maestro_inventory.csv with official MAESTRO metadata joined.
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


def resolve_dataset_path():
    """Locate the MAESTRO dataset directory."""
    for path_str in DEFAULT_PATHS:
        if path_str and os.path.exists(path_str):
            p = pathlib.Path(path_str).resolve()
            sub = p / "maestro-v3.0.0"
            if sub.exists() and (sub / "maestro-v3.0.0.csv").exists():
                return p, sub
            return p, p
    return None, None


def load_maestro_metadata(search_dir):
    """Load official MAESTRO CSV metadata if available."""
    csv_candidates = list(search_dir.rglob("maestro-v3.0.0.csv"))
    if csv_candidates:
        csv_path = csv_candidates[0]
        try:
            df = pd.read_csv(csv_path)
            lookup = {}
            for _, row in df.iterrows():
                midi_rel = str(row.get("midi_filename", "")).replace("\\", "/")
                filename = pathlib.Path(midi_rel).name
                meta = {
                    "composer": row.get("canonical_composer", "Unknown"),
                    "title": row.get("canonical_title", "Unknown"),
                    "split": row.get("split", "train"),
                    "year": row.get("year", ""),
                    "duration": row.get("duration", 0.0),
                }
                lookup[midi_rel] = meta
                lookup[filename] = meta
            print(f"[OK] Loaded official MAESTRO metadata from {csv_path.name} ({len(df)} records)", flush=True)
            return lookup
        except Exception as e:
            print(f"[WARN] Failed to parse {csv_path}: {e}", flush=True)
    return {}


def analyze_single_file(args):
    """Worker function for concurrent processing of a single MIDI file."""
    fpath_str, rel_path, metadata = args
    fpath = pathlib.Path(fpath_str)

    try:
        f_size = fpath.stat().st_size
        if f_size == 0:
            return {
                "file_path": fpath_str,
                "filename": fpath.name,
                "relative_path": rel_path,
                "composer": metadata.get("composer", "Unknown"),
                "title": metadata.get("title", fpath.stem),
                "split": metadata.get("split", "train"),
                "year": metadata.get("year", ""),
                "duration": round(metadata.get("duration", 0.0), 2),
                "file_size_bytes": f_size,
                "number_of_notes": 0,
                "number_of_chords": 0,
                "total_musical_events": 0,
                "parsing_status": "INVALID",
                "error_message": "Empty file (0 bytes)",
            }

        mf = music21.midi.MidiFile()
        mf.open(fpath_str)
        mf.read()
        mf.close()

        if not mf.tracks:
            return {
                "file_path": fpath_str,
                "filename": fpath.name,
                "relative_path": rel_path,
                "composer": metadata.get("composer", "Unknown"),
                "title": metadata.get("title", fpath.stem),
                "split": metadata.get("split", "train"),
                "year": metadata.get("year", ""),
                "duration": round(metadata.get("duration", 0.0), 2),
                "file_size_bytes": f_size,
                "number_of_notes": 0,
                "number_of_chords": 0,
                "total_musical_events": 0,
                "parsing_status": "INVALID",
                "error_message": "No tracks found in MIDI file",
            }

        note_count = 0
        chord_count = 0
        total_events = 0

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
                else:
                    note_count += 1

        is_valid = (note_count + chord_count) > 0
        status = "VALID" if is_valid else "INVALID"
        err_msg = "" if is_valid else "No musical note/chord events in MIDI file"

        # Year fallback from directory name if not in metadata
        year = metadata.get("year", "")
        if not year:
            for p in fpath.parts:
                if p.isdigit() and len(p) == 4:
                    year = int(p)
                    break

        return {
            "file_path": fpath_str,
            "filename": fpath.name,
            "relative_path": rel_path,
            "composer": metadata.get("composer", "Unknown"),
            "title": metadata.get("title", fpath.stem),
            "split": metadata.get("split", "train"),
            "year": year,
            "duration": round(metadata.get("duration", 0.0), 2),
            "file_size_bytes": f_size,
            "number_of_notes": note_count,
            "number_of_chords": chord_count,
            "total_musical_events": total_events,
            "parsing_status": status,
            "error_message": err_msg,
        }

    except Exception as exc:
        return {
            "file_path": fpath_str,
            "filename": fpath.name,
            "relative_path": rel_path,
            "composer": metadata.get("composer", "Unknown"),
            "title": metadata.get("title", fpath.stem),
            "split": metadata.get("split", "train"),
            "year": metadata.get("year", ""),
            "duration": round(metadata.get("duration", 0.0), 2),
            "file_size_bytes": os.path.getsize(fpath_str) if os.path.exists(fpath_str) else 0,
            "number_of_notes": 0,
            "number_of_chords": 0,
            "total_musical_events": 0,
            "parsing_status": "INVALID",
            "error_message": str(exc),
        }


def prepare_maestro_dataset():
    base_dir, data_dir = resolve_dataset_path()
    if not base_dir:
        print("[ERROR] Could not locate MAESTRO dataset. Please set DATASET_PATH in .env", flush=True)
        sys.exit(1)

    print("==================================================", flush=True)
    print("  AI Music Studio - MAESTRO Dataset Preparation   ", flush=True)
    print("==================================================", flush=True)
    print(f"Dataset root directory: {base_dir}", flush=True)

    # Discover all MIDI files
    print("Discovering all MIDI files recursively...", flush=True)
    midi_files = sorted(list(base_dir.rglob("*.mid")) + list(base_dir.rglob("*.midi")))
    total_files = len(midi_files)
    print(f"Discovered total MIDI files: {total_files}", flush=True)

    if total_files == 0:
        print("[ERROR] No .mid or .midi files found in directory!", flush=True)
        sys.exit(1)

    metadata_lookup = load_maestro_metadata(base_dir)

    # Prepare job items
    job_args = []
    for fpath in midi_files:
        fpath_str = str(fpath.resolve())
        rel_path = str(fpath.relative_to(base_dir)).replace("\\", "/")
        fname = fpath.name
        meta = metadata_lookup.get(rel_path) or metadata_lookup.get(fname) or {}
        job_args.append((fpath_str, rel_path, meta))

    workers = min(8, os.cpu_count() or 4)
    print(f"\nProcessing all {total_files} files using {workers} parallel CPU workers...", flush=True)

    t_start = time.time()
    records = []
    valid_count = 0
    invalid_count = 0
    total_notes = 0
    total_chords = 0
    total_duration_secs = 0.0
    total_bytes = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        for idx, result in enumerate(executor.map(analyze_single_file, job_args, chunksize=10), 1):
            records.append(result)
            total_bytes += result["file_size_bytes"]

            if result["parsing_status"] == "VALID":
                valid_count += 1
                total_notes += result["number_of_notes"]
                total_chords += result["number_of_chords"]
                total_duration_secs += result["duration"]
            else:
                invalid_count += 1

            if idx % 100 == 0 or idx == total_files:
                elapsed = time.time() - t_start
                rate = idx / elapsed if elapsed > 0 else 0
                pct = (idx / total_files) * 100
                print(
                    f"  [Progress {idx:4d}/{total_files} ({pct:5.1f}%)] "
                    f"Valid: {valid_count:4d} | Invalid: {invalid_count:2d} | "
                    f"Speed: {rate:5.1f} files/s | Elapsed: {elapsed:4.1f}s",
                    flush=True,
                )

    # Save to CSV
    inventory_df = pd.DataFrame(records)
    inventory_file = pathlib.Path("dataset/maestro_inventory.csv")
    inventory_file.parent.mkdir(parents=True, exist_ok=True)
    inventory_df.to_csv(inventory_file, index=False)
    print(f"\n[SUCCESS] Saved inventory to {inventory_file.resolve()}", flush=True)

    elapsed_total = time.time() - t_start
    total_duration_hours = total_duration_secs / 3600.0

    print("\n" + "=" * 55, flush=True)
    print("       MAESTRO DATASET PREPARATION SUMMARY        ", flush=True)
    print("=" * 55, flush=True)
    print(f"Dataset Path:             {base_dir}", flush=True)
    print(f"Total MIDI Files:         {total_files}", flush=True)
    print(f"Valid MIDI Files:         {valid_count}", flush=True)
    print(f"Invalid MIDI Files:       {invalid_count}", flush=True)
    print(f"Total Dataset Size:       {total_bytes / (1024 * 1024):.2f} MB", flush=True)
    print(f"Total Notes Extracted:    {total_notes:,}", flush=True)
    print(f"Total Chords Extracted:   {total_chords:,}", flush=True)
    print(f"Total Duration:           {total_duration_hours:.2f} hours ({total_duration_secs:,.0f} seconds)", flush=True)
    print(f"Processing Time:          {elapsed_total:.2f} seconds ({total_files/elapsed_total:.1f} files/s)", flush=True)
    print("=" * 55, flush=True)


if __name__ == "__main__":
    prepare_maestro_dataset()
