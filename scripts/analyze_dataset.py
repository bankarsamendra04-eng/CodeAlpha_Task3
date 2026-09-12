"""
AI Music Studio - Complete MAESTRO Dataset Analysis Script
Recursively parses all MIDI files using music21, extracting:
- Filename, Duration, Notes, Chords, Parts/Tracks, Instruments, Tempo, Time Signature, Key, and Mode.
Generates:
- dataset/maestro_analysis.csv
- dataset/dataset_summary.json
"""

import os
import sys
import time
import json
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
                    "composer": str(row.get("canonical_composer", "Unknown")),
                    "title": str(row.get("canonical_title", "Unknown")),
                    "split": str(row.get("split", "train")),
                    "year": row.get("year", ""),
                    "duration": float(row.get("duration", 0.0)),
                }
                lookup[midi_rel] = meta
                lookup[filename] = meta
            print(f"[OK] Loaded official MAESTRO metadata from {csv_path.name} ({len(df)} records)", flush=True)
            return lookup
        except Exception as e:
            print(f"[WARN] Failed to parse {csv_path}: {e}", flush=True)
    return {}


def analyze_single_midi_file(args):
    """Worker function to analyze a single MIDI file using music21."""
    fpath_str, rel_path, meta = args
    fpath = pathlib.Path(fpath_str)
    fname = fpath.name

    try:
        f_size = fpath.stat().st_size
        if f_size == 0:
            return {
                "file_path": fpath_str,
                "filename": fname,
                "relative_path": rel_path,
                "composer": meta.get("composer", "Unknown"),
                "title": meta.get("title", fpath.stem),
                "split": meta.get("split", "train"),
                "year": meta.get("year", ""),
                "duration": 0.0,
                "file_size_bytes": 0,
                "number_of_notes": 0,
                "number_of_chords": 0,
                "number_of_parts": 0,
                "instruments": "None",
                "tempo": None,
                "time_signature": "Unknown",
                "key": "Unknown",
                "mode": "Unknown",
                "key_correlation": 0.0,
                "parsing_status": "INVALID",
                "error_message": "Empty file (0 bytes)",
            }

        # 1. Read MIDI file with music21
        mf = music21.midi.MidiFile()
        mf.open(fpath_str)
        mf.read()
        mf.close()

        num_tracks = len(mf.tracks)
        if num_tracks == 0:
            return {
                "file_path": fpath_str,
                "filename": fname,
                "relative_path": rel_path,
                "composer": meta.get("composer", "Unknown"),
                "title": meta.get("title", fpath.stem),
                "split": meta.get("split", "train"),
                "year": meta.get("year", ""),
                "duration": 0.0,
                "file_size_bytes": f_size,
                "number_of_notes": 0,
                "number_of_chords": 0,
                "number_of_parts": 0,
                "instruments": "None",
                "tempo": None,
                "time_signature": "Unknown",
                "key": "Unknown",
                "mode": "Unknown",
                "key_correlation": 0.0,
                "parsing_status": "INVALID",
                "error_message": "No tracks found in MIDI file",
            }

        note_count = 0
        chord_count = 0
        detected_tempos = []
        detected_time_sigs = []
        detected_programs = set()
        all_pitches = []

        # 2. Extract musical events, tempo, time signature, instruments
        for track in mf.tracks:
            time_offset = 0
            simultaneous_notes = {}

            for ev in track.events:
                if ev.type == "DeltaTime":
                    time_offset += ev.time

                # Note On
                elif ev.type == music21.midi.ChannelVoiceMessages.NOTE_ON and getattr(ev, "velocity", 0) > 0:
                    simultaneous_notes.setdefault(time_offset, []).append(ev.pitch)
                    all_pitches.append(ev.pitch)

                # Tempo
                elif ev.type == music21.midi.MetaEvents.SET_TEMPO and ev.data:
                    try:
                        mpqn = int.from_bytes(ev.data, "big")
                        if mpqn > 0:
                            bpm = round(60000000.0 / mpqn, 1)
                            if 20 <= bpm <= 300:
                                detected_tempos.append(bpm)
                    except Exception:
                        pass

                # Time Signature
                elif ev.type == music21.midi.MetaEvents.TIME_SIGNATURE and ev.data:
                    try:
                        num = ev.data[0]
                        denom = 2 ** ev.data[1]
                        detected_time_sigs.append(f"{num}/{denom}")
                    except Exception:
                        pass

                # Instrument Program Change
                elif ev.type == music21.midi.ChannelVoiceMessages.PROGRAM_CHANGE and ev.data is not None:
                    try:
                        prog_num = ev.data if isinstance(ev.data, int) else ev.data[0]
                        detected_programs.add(prog_num)
                    except Exception:
                        pass

            # Classify single notes vs chords
            for t_step, pitches in simultaneous_notes.items():
                if len(pitches) > 1:
                    chord_count += 1
                elif len(pitches) == 1:
                    note_count += 1

        # Determine primary tempo & time signature
        primary_tempo = detected_tempos[0] if detected_tempos else 120.0
        primary_time_sig = detected_time_sigs[0] if detected_time_sigs else "4/4"

        # Determine instruments
        if detected_programs:
            inst_names = []
            for p_num in sorted(detected_programs):
                try:
                    inst_obj = music21.instrument.instrumentFromMidiProgram(p_num)
                    inst_names.append(inst_obj.instrumentName or f"Program {p_num}")
                except Exception:
                    inst_names.append(f"Program {p_num}")
            instruments_str = ", ".join(inst_names)
        else:
            instruments_str = "Acoustic Grand Piano"

        # 3. Detect Key and Mode using music21 Krumhansl-Schmuckler key analysis
        detected_key = "Unknown"
        detected_mode = "Unknown"
        key_corr = 0.0

        if all_pitches:
            try:
                # Sample up to 600 pitches across the piece for fast cognitive key analysis
                step = max(1, len(all_pitches) // 600)
                sampled_pitches = all_pitches[::step][:600]

                temp_stream = music21.stream.Stream()
                for p in sampled_pitches:
                    temp_stream.append(music21.note.Note(p))

                k = temp_stream.analyze("key")
                detected_key = f"{k.tonic.name} {k.mode}"
                detected_mode = k.mode
                key_corr = round(float(getattr(k, "correlationCoefficient", 0.0)), 3)
            except Exception:
                detected_key = "Unknown"
                detected_mode = "Unknown"

        # Determine Duration
        duration_sec = meta.get("duration", 0.0)
        if duration_sec <= 0 and detected_tempos and hasattr(mf, "ticksPerQuarterNote") and mf.ticksPerQuarterNote:
            try:
                total_ticks = max(time_offset for track in mf.tracks for time_offset in [0])
                duration_sec = round((total_ticks / mf.ticksPerQuarterNote) * (60.0 / primary_tempo), 2)
            except Exception:
                duration_sec = 0.0

        is_valid = (note_count + chord_count) > 0

        # Extract year fallback
        year = meta.get("year", "")
        if not year:
            for part in fpath.parts:
                if part.isdigit() and len(part) == 4:
                    year = int(part)
                    break

        return {
            "file_path": fpath_str,
            "filename": fname,
            "relative_path": rel_path,
            "composer": meta.get("composer", "Unknown"),
            "title": meta.get("title", fpath.stem),
            "split": meta.get("split", "train"),
            "year": year,
            "duration": round(duration_sec, 2),
            "file_size_bytes": f_size,
            "number_of_notes": note_count,
            "number_of_chords": chord_count,
            "number_of_parts": num_tracks,
            "instruments": instruments_str,
            "tempo": primary_tempo,
            "time_signature": primary_time_sig,
            "key": detected_key,
            "mode": detected_mode,
            "key_correlation": key_corr,
            "parsing_status": "VALID" if is_valid else "INVALID",
            "error_message": "" if is_valid else "No musical notes/chords found",
        }

    except Exception as exc:
        return {
            "file_path": fpath_str,
            "filename": fname,
            "relative_path": rel_path,
            "composer": meta.get("composer", "Unknown"),
            "title": meta.get("title", fpath.stem),
            "split": meta.get("split", "train"),
            "year": meta.get("year", ""),
            "duration": round(meta.get("duration", 0.0), 2),
            "file_size_bytes": fpath.stat().st_size if fpath.exists() else 0,
            "number_of_notes": 0,
            "number_of_chords": 0,
            "number_of_parts": 0,
            "instruments": "Unknown",
            "tempo": None,
            "time_signature": "Unknown",
            "key": "Unknown",
            "mode": "Unknown",
            "key_correlation": 0.0,
            "parsing_status": "INVALID",
            "error_message": str(exc),
        }


def run_complete_dataset_analysis():
    base_dir, data_dir = resolve_dataset_path()
    if not base_dir:
        print("[ERROR] Could not locate MAESTRO dataset directory. Set DATASET_PATH in .env", flush=True)
        sys.exit(1)

    print("==================================================", flush=True)
    print("  AI Music Studio - Complete Dataset Analysis     ", flush=True)
    print("==================================================", flush=True)
    print(f"Dataset root: {base_dir}\n", flush=True)

    # 1. Discover all MIDI files
    print("Discovering all MIDI files recursively...", flush=True)
    midi_files = sorted(list(base_dir.rglob("*.mid")) + list(base_dir.rglob("*.midi")))
    total_files = len(midi_files)
    print(f"Total MIDI files discovered: {total_files}\n", flush=True)

    if total_files == 0:
        print("[ERROR] No MIDI files found!", flush=True)
        sys.exit(1)

    # Load metadata
    metadata_lookup = load_maestro_metadata(base_dir)

    # Prepare jobs
    job_args = []
    for f in midi_files:
        fpath_str = str(f.resolve())
        rel_path = str(f.relative_to(base_dir)).replace("\\", "/")
        fname = f.name
        meta = metadata_lookup.get(rel_path) or metadata_lookup.get(fname) or {}
        job_args.append((fpath_str, rel_path, meta))

    workers = min(8, os.cpu_count() or 4)
    print(f"Analyzing all {total_files} files using {workers} parallel CPU workers...", flush=True)

    t_start = time.time()
    records = []
    valid_count = 0
    invalid_count = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        for idx, result in enumerate(executor.map(analyze_single_midi_file, job_args, chunksize=10), 1):
            records.append(result)
            if result["parsing_status"] == "VALID":
                valid_count += 1
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

    elapsed_total = time.time() - t_start

    # Convert to DataFrame
    df = pd.DataFrame(records)

    # Save CSV: dataset/maestro_analysis.csv
    out_dir = pathlib.Path("dataset")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "maestro_analysis.csv"
    df.to_csv(csv_path, index=False)
    print(f"\n[OK] Analysis results saved to {csv_path.resolve()}", flush=True)

    # Compute Aggregate Statistics for dataset/dataset_summary.json
    valid_df = df[df["parsing_status"] == "VALID"]
    invalid_df = df[df["parsing_status"] == "INVALID"]

    total_duration = float(valid_df["duration"].sum())
    avg_duration = float(valid_df["duration"].mean()) if not valid_df.empty else 0.0
    total_notes = int(valid_df["number_of_notes"].sum())
    avg_notes = float(valid_df["number_of_notes"].mean()) if not valid_df.empty else 0.0
    total_chords = int(valid_df["number_of_chords"].sum())
    avg_chords = float(valid_df["number_of_chords"].mean()) if not valid_df.empty else 0.0

    # Instruments distribution
    inst_series = valid_df["instruments"].str.split(", ").explode()
    available_instruments = inst_series.value_counts().to_dict()

    # Tempo distribution
    tempo_series = valid_df["tempo"].dropna()
    tempos_summary = {
        "min": float(tempo_series.min()) if not tempo_series.empty else 0.0,
        "max": float(tempo_series.max()) if not tempo_series.empty else 0.0,
        "median": float(tempo_series.median()) if not tempo_series.empty else 0.0,
        "mean": round(float(tempo_series.mean()), 1) if not tempo_series.empty else 0.0,
        "common_tempos": tempo_series.round().value_counts().head(10).to_dict(),
    }

    # Keys & Modes distribution
    key_distribution = valid_df["key"].value_counts().head(20).to_dict()
    mode_distribution = valid_df["mode"].value_counts().to_dict()

    # Time Signatures distribution
    time_sig_distribution = valid_df["time_signature"].value_counts().to_dict()

    # Parsing Errors
    parsing_errors = []
    if not invalid_df.empty:
        for _, row in invalid_df.iterrows():
            parsing_errors.append({
                "filename": row["filename"],
                "error": row["error_message"],
            })

    # Summary JSON Structure
    summary = {
        "dataset_name": "MAESTRO v3.0.0 (MIDI)",
        "dataset_path": str(base_dir),
        "total_midi_files": total_files,
        "valid_files": valid_count,
        "invalid_files": invalid_count,
        "total_duration_seconds": round(total_duration, 2),
        "total_duration_hours": round(total_duration / 3600.0, 2),
        "average_duration_seconds": round(avg_duration, 2),
        "average_duration_formatted": f"{int(avg_duration // 60)}m {int(avg_duration % 60)}s",
        "total_notes": total_notes,
        "average_notes_per_file": round(avg_notes, 1),
        "total_chords": total_chords,
        "average_chords_per_file": round(avg_chords, 1),
        "available_instruments": available_instruments,
        "available_tempos": tempos_summary,
        "available_keys": key_distribution,
        "mode_distribution": mode_distribution,
        "time_signatures": time_sig_distribution,
        "splits": valid_df["split"].value_counts().to_dict(),
        "composers_count": int(valid_df["composer"].nunique()),
        "top_composers": valid_df["composer"].value_counts().head(10).to_dict(),
        "parsing_errors": parsing_errors,
        "analysis_time_seconds": round(elapsed_total, 2),
    }

    # Save summary JSON
    json_path = out_dir / "dataset_summary.json"
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(summary, jf, indent=2)
    print(f"[OK] Summary JSON saved to {json_path.resolve()}", flush=True)

    # Print Full Console Summary
    print("\n" + "=" * 60, flush=True)
    print("           COMPLETE DATASET ANALYSIS SUMMARY            ", flush=True)
    print("=" * 60, flush=True)
    print(f"Total MIDI Files:         {total_files}", flush=True)
    print(f"Valid Files:              {valid_count} ({(valid_count/total_files)*100:.1f}%)", flush=True)
    print(f"Invalid Files:            {invalid_count}", flush=True)
    print(f"Total Performance Time:   {summary['total_duration_hours']} hours ({total_duration:,.0f} seconds)", flush=True)
    print(f"Average Duration / File:  {summary['average_duration_formatted']} ({avg_duration:.1f}s)", flush=True)
    print(f"Total Extracted Notes:    {total_notes:,}", flush=True)
    print(f"Average Notes / File:     {avg_notes:,.0f}", flush=True)
    print(f"Total Extracted Chords:   {total_chords:,}", flush=True)
    print(f"Average Chords / File:    {avg_chords:,.0f}", flush=True)
    print(f"Top 5 Composers:          {list(summary['top_composers'].items())[:5]}", flush=True)
    print(f"Tempo Range:              {tempos_summary['min']} - {tempos_summary['max']} BPM (Median: {tempos_summary['median']} BPM)", flush=True)
    print(f"Top 5 Keys:               {list(key_distribution.items())[:5]}", flush=True)
    print(f"Modes Breakdown:          {mode_distribution}", flush=True)
    print(f"Time Signatures:          {time_sig_distribution}", flush=True)
    print(f"Instruments Detected:     {list(available_instruments.keys())}", flush=True)
    print(f"Parsing Errors:           {len(parsing_errors)}", flush=True)
    print(f"Analysis Processing Time: {elapsed_total:.2f} seconds ({total_files/elapsed_total:.1f} files/s)", flush=True)
    print("=" * 60, flush=True)

    return summary


if __name__ == "__main__":
    run_complete_dataset_analysis()
