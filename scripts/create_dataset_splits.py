"""
AI Music Studio - Dataset Split Generator
Creates reproducible, file-level splits for the MAESTRO dataset:
- 80% Training
- 10% Validation
- 10% Testing

Splits are strictly at the MIDI-file level so sequences from the same piece never leak across splits.
Uses a fixed random seed for 100% reproducibility.
Saves:
- dataset/splits/train.csv
- dataset/splits/validation.csv
- dataset/splits/test.csv
- dataset/splits/split_summary.json
"""

import sys
import json
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

from ml.config import (
    INVENTORY_PATH,
    ANALYSIS_PATH,
    SPLITS_DIR,
    TRAIN_SPLIT_CSV,
    VAL_SPLIT_CSV,
    TEST_SPLIT_CSV,
    SPLIT_SUMMARY_JSON,
    RANDOM_SEED,
)


def format_duration(seconds: float) -> str:
    """Convert seconds to human-readable hours, minutes, seconds."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    return f"{minutes}m {secs}s"


def create_splits(
    inventory_path: Path = INVENTORY_PATH,
    analysis_path: Path = ANALYSIS_PATH,
    splits_dir: Path = SPLITS_DIR,
    random_seed: int = RANDOM_SEED,
    train_ratio: float = 0.80,
    val_ratio: float = 0.10,
    test_ratio: float = 0.10,
) -> dict:
    """
    Generate reproducible file-level splits of the MAESTRO dataset.
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, "Ratios must sum to 1.0"

    print("=" * 65)
    print("       AI MUSIC STUDIO - DATASET SPLIT GENERATOR")
    print("=" * 65)
    print(f"Target Split Ratio : {train_ratio*100:.0f}% Train | {val_ratio*100:.0f}% Val | {test_ratio*100:.0f}% Test")
    print(f"Random Seed        : {random_seed}")
    print(f"Splits Directory   : {splits_dir}")
    print("=" * 65)

    # 1. Load dataset metadata from inventory and analysis CSVs
    if not inventory_path.exists():
        raise FileNotFoundError(f"Inventory file not found: {inventory_path}")

    df_inv = pd.read_csv(inventory_path)
    print(f"[*] Loaded inventory: {len(df_inv)} rows")

    # If analysis file exists, merge note/chord/event counts if not already present
    if analysis_path.exists():
        df_ana = pd.read_csv(analysis_path)
        # Check if we should merge any missing columns
        cols_to_use = [c for c in df_ana.columns if c not in df_inv.columns or c == "relative_path"]
        if len(cols_to_use) > 1:
            df_inv = df_inv.merge(df_ana[cols_to_use], on="relative_path", how="left")

    # Sort deterministically by relative_path to eliminate any OS filesystem ordering differences
    df = df_inv.sort_values(by="relative_path").reset_index(drop=True)
    total_files = len(df)
    print(f"[+] Total files to split: {total_files}")

    # 2. Perform reproducible file-level split
    # Step A: 80% train, 20% temp (val + test)
    val_test_ratio = val_ratio + test_ratio
    train_df, temp_df = train_test_split(
        df,
        test_size=val_test_ratio,
        random_state=random_seed,
        shuffle=True,
    )

    # Step B: Split temp equally (50% val, 50% test of the 20% remainder -> 10% each of total)
    val_df, test_df = train_test_split(
        temp_df,
        test_size=0.5,
        random_state=random_seed,
        shuffle=True,
    )

    # Sort each split for determinism
    train_df = train_df.sort_values(by="relative_path").reset_index(drop=True)
    val_df = val_df.sort_values(by="relative_path").reset_index(drop=True)
    test_df = test_df.sort_values(by="relative_path").reset_index(drop=True)

    train_count = len(train_df)
    val_count = len(val_df)
    test_count = len(test_df)

    print(f"[+] Train set      : {train_count} files ({train_count/total_files*100:.2f}%)")
    print(f"[+] Validation set : {val_count} files ({val_count/total_files*100:.2f}%)")
    print(f"[+] Test set       : {test_count} files ({test_count/total_files*100:.2f}%)")

    # 3. Verify strict zero-overlap between splits
    train_files = set(train_df["relative_path"])
    val_files = set(val_df["relative_path"])
    test_files = set(test_df["relative_path"])

    train_val_overlap = len(train_files & val_files)
    train_test_overlap = len(train_files & test_files)
    val_test_overlap = len(val_files & test_files)
    union_count = len(train_files | val_files | test_files)

    print("\n[*] Verifying split isolation and disjointness...")
    print(f"    Train & Val overlap   : {train_val_overlap}")
    print(f"    Train & Test overlap  : {train_test_overlap}")
    print(f"    Val & Test overlap    : {val_test_overlap}")
    print(f"    Union count           : {union_count} / {total_files}")

    assert train_val_overlap == 0, f"Error: {train_val_overlap} overlapping files between train and val"
    assert train_test_overlap == 0, f"Error: {train_test_overlap} overlapping files between train and test"
    assert val_test_overlap == 0, f"Error: {val_test_overlap} overlapping files between val and test"
    assert union_count == total_files, f"Error: Union ({union_count}) does not match total files ({total_files})"
    print("[OK] VERIFIED: Zero file overlap between train, validation, and test sets!")

    # 4. Save CSV files
    splits_dir.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(TRAIN_SPLIT_CSV, index=False)
    val_df.to_csv(VAL_SPLIT_CSV, index=False)
    test_df.to_csv(TEST_SPLIT_CSV, index=False)

    print(f"[+] Saved train split to      : {TRAIN_SPLIT_CSV}")
    print(f"[+] Saved validation split to : {VAL_SPLIT_CSV}")
    print(f"[+] Saved test split to       : {TEST_SPLIT_CSV}")

    # 5. Compute aggregate metrics
    def compute_metrics(split_df: pd.DataFrame) -> dict:
        n_files = len(split_df)
        pct = round((n_files / total_files) * 100, 2)
        total_dur_sec = round(float(split_df["duration"].sum()), 2)
        total_dur_hr = round(total_dur_sec / 3600, 2)

        # Total events (notes + chords or total_musical_events)
        if "total_musical_events" in split_df.columns:
            total_events = int(split_df["total_musical_events"].sum())
        elif "number_of_notes" in split_df.columns and "number_of_chords" in split_df.columns:
            total_events = int(split_df["number_of_notes"].sum() + split_df["number_of_chords"].sum())
        else:
            total_events = int(split_df["number_of_notes"].sum())

        total_notes = int(split_df["number_of_notes"].sum()) if "number_of_notes" in split_df.columns else 0
        total_chords = int(split_df["number_of_chords"].sum()) if "number_of_chords" in split_df.columns else 0

        return {
            "number_of_files": n_files,
            "percentage": pct,
            "total_duration_seconds": total_dur_sec,
            "total_duration_hours": total_dur_hr,
            "total_duration_formatted": format_duration(total_dur_sec),
            "number_of_events": total_events,
            "number_of_notes": total_notes,
            "number_of_chords": total_chords,
        }

    train_metrics = compute_metrics(train_df)
    val_metrics = compute_metrics(val_df)
    test_metrics = compute_metrics(test_df)

    summary = {
        "dataset_name": "MAESTRO v3.0.0",
        "random_seed": random_seed,
        "split_ratios": {
            "train": train_ratio,
            "validation": val_ratio,
            "test": test_ratio,
        },
        "total_files": total_files,
        "train": train_metrics,
        "validation": val_metrics,
        "test": test_metrics,
        "verification": {
            "train_val_overlap": train_val_overlap,
            "train_test_overlap": train_test_overlap,
            "val_test_overlap": val_test_overlap,
            "total_files_accounted_for": union_count,
            "is_disjoint": True,
        },
    }

    with open(SPLIT_SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"[+] Saved split summary to    : {SPLIT_SUMMARY_JSON}")
    print("\n" + "=" * 65)
    print("                     SPLIT SUMMARY")
    print("=" * 65)
    print(f"Train Set      : {train_metrics['number_of_files']} files ({train_metrics['percentage']}%), {train_metrics['total_duration_formatted']} ({train_metrics['total_duration_hours']}h), {train_metrics['number_of_events']:,} events")
    print(f"Validation Set : {val_metrics['number_of_files']} files ({val_metrics['percentage']}%), {val_metrics['total_duration_formatted']} ({val_metrics['total_duration_hours']}h), {val_metrics['number_of_events']:,} events")
    print(f"Test Set       : {test_metrics['number_of_files']} files ({test_metrics['percentage']}%), {test_metrics['total_duration_formatted']} ({test_metrics['total_duration_hours']}h), {test_metrics['number_of_events']:,} events")
    print("=" * 65)

    return summary


if __name__ == "__main__":
    create_splits()
