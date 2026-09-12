"""
Demonstration Script for Music Representation on Real MAESTRO Files
Tests token extraction on several real MAESTRO performances across multiple composers.
"""

import sys
import pathlib
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.config import DATASET_PATH, INVENTORY_PATH
from ml.music_representation import (
    extract_musical_events_from_midi,
    Vocabulary,
)


def run_demo():
    print("=" * 70)
    print("  AI Music Studio - Real MAESTRO Music Representation Demo")
    print("=" * 70)

    # Pick 3 diverse files from inventory
    if INVENTORY_PATH.exists():
        inv_df = pd.read_csv(INVENTORY_PATH)
        sample_rows = inv_df.drop_duplicates(subset=["composer"]).head(3)
        sample_files = [pathlib.Path(row["file_path"]) for _, row in sample_rows.iterrows()]
    else:
        sample_files = sorted(list(DATASET_PATH.rglob("*.midi")) + list(DATASET_PATH.rglob("*.mid")))[:3]

    all_tokens = []

    for idx, fpath in enumerate(sample_files, 1):
        if not fpath.exists():
            continue

        print(f"\n[{idx}/3] Inspecting File: {fpath.name}")
        events = extract_musical_events_from_midi(fpath)
        notes = [e for e in events if e.event_type == "NOTE"]
        chords = [e for e in events if e.event_type == "CHORD"]
        rests = [e for e in events if e.event_type == "REST"]

        print(f"     Total Events: {len(events)} | Notes: {len(notes)} | Chords: {len(chords)} | Rests: {len(rests)}")

        tokens = [e.to_token() for e in events]
        all_tokens.append(tokens)

        print("\n     First 8 Extracted Musical Events:")
        print(f"     {'Type':6s} | {'Pitches / Names':20s} | {'Offset':7s} | {'Duration':8s} | {'Vel':3s} | {'Token':25s}")
        print("     " + "-" * 78)
        for ev in events[:8]:
            p_str = f"{ev.pitches} ({ev.pitch_names})" if ev.event_type != "REST" else "REST"
            print(
                f"     {ev.event_type:6s} | {p_str[:20]:20s} | {ev.offset:6.2f}q | {ev.duration:6.2f}q | {ev.velocity:3d} | {ev.to_token():25s}"
            )

    # Build demo vocabulary
    vocab = Vocabulary()
    vocab.build_from_sequences(all_tokens)
    print("\n" + "=" * 70)
    print("  Vocabulary Summary on Sample Performances")
    print("=" * 70)
    print(f"  Total Unique Tokens in Sample: {len(vocab)}")
    print(f"  Reserved Tokens: {list(vocab.token_to_id.items())[:4]}")
    sample_tokens = list(vocab.token_to_id.keys())[4:14]
    print(f"  Sample Encoded Tokens: {sample_tokens}")
    sample_ids = vocab.encode(sample_tokens[:5])
    print(f"  Encoding [{sample_tokens[0]}...] -> Integer IDs: {sample_ids}")
    decoded_back = vocab.decode(sample_ids)
    print(f"  Decoded back -> {decoded_back}")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
