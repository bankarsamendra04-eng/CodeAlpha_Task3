"""
AI Music Studio - Unit & Integration Tests for Dataset Splits
Verifies:
1. Split CSV files existence and structure.
2. 80% / 10% / 10% ratio adherence.
3. Strict zero-overlap / disjointness between train, validation, and test splits.
4. Completeness (100% of MAESTRO files accounted for).
5. Split summary JSON metrics (files, percentages, durations, events).
"""

import json
import pytest
import pandas as pd
from pathlib import Path

from ml.config import (
    SPLITS_DIR,
    TRAIN_SPLIT_CSV,
    VAL_SPLIT_CSV,
    TEST_SPLIT_CSV,
    SPLIT_SUMMARY_JSON,
    INVENTORY_PATH,
)


def test_split_files_exist():
    """Verify that train.csv, validation.csv, and test.csv exist on disk."""
    assert TRAIN_SPLIT_CSV.exists(), f"Missing {TRAIN_SPLIT_CSV}"
    assert VAL_SPLIT_CSV.exists(), f"Missing {VAL_SPLIT_CSV}"
    assert TEST_SPLIT_CSV.exists(), f"Missing {TEST_SPLIT_CSV}"
    assert SPLIT_SUMMARY_JSON.exists(), f"Missing {SPLIT_SUMMARY_JSON}"


def test_split_row_counts_and_percentages():
    """Verify that file counts follow the 80/10/10 ratio."""
    df_train = pd.read_csv(TRAIN_SPLIT_CSV)
    df_val = pd.read_csv(VAL_SPLIT_CSV)
    df_test = pd.read_csv(TEST_SPLIT_CSV)

    total_files = len(df_train) + len(df_val) + len(df_test)
    assert total_files == 1276, f"Expected 1276 files, got {total_files}"

    train_pct = len(df_train) / total_files
    val_pct = len(df_val) / total_files
    test_pct = len(df_test) / total_files

    # 80% ± 0.5%, 10% ± 0.5%
    assert abs(train_pct - 0.80) < 0.005, f"Train percentage {train_pct:.4f} is not ~80%"
    assert abs(val_pct - 0.10) < 0.005, f"Validation percentage {val_pct:.4f} is not ~10%"
    assert abs(test_pct - 0.10) < 0.005, f"Test percentage {test_pct:.4f} is not ~10%"

    assert len(df_train) == 1020
    assert len(df_val) == 128
    assert len(df_test) == 128


def test_zero_file_overlap_disjointness():
    """Verify strictly zero overlap between any pairs of splits."""
    df_train = pd.read_csv(TRAIN_SPLIT_CSV)
    df_val = pd.read_csv(VAL_SPLIT_CSV)
    df_test = pd.read_csv(TEST_SPLIT_CSV)

    train_set = set(df_train["relative_path"])
    val_set = set(df_val["relative_path"])
    test_set = set(df_test["relative_path"])

    assert len(train_set) == len(df_train), "Duplicate files found within train set"
    assert len(val_set) == len(df_val), "Duplicate files found within validation set"
    assert len(test_set) == len(df_test), "Duplicate files found within test set"

    train_val = train_set & val_set
    train_test = train_set & test_set
    val_test = val_set & test_set

    assert len(train_val) == 0, f"Train and Validation sets have {len(train_val)} overlapping files: {train_val}"
    assert len(train_test) == 0, f"Train and Test sets have {len(train_test)} overlapping files: {train_test}"
    assert len(val_test) == 0, f"Validation and Test sets have {len(val_test)} overlapping files: {val_test}"

    union_all = train_set | val_set | test_set
    assert len(union_all) == 1276, f"Union of splits {len(union_all)} does not cover all 1276 files"


def test_split_summary_metrics():
    """Verify split_summary.json contains files, percentages, durations, events."""
    with open(SPLIT_SUMMARY_JSON, "r", encoding="utf-8") as f:
        summary = json.load(f)

    for split in ("train", "validation", "test"):
        assert split in summary, f"Missing '{split}' section in summary"
        data = summary[split]
        assert "number_of_files" in data
        assert "percentage" in data
        assert "total_duration_seconds" in data
        assert "total_duration_hours" in data
        assert "number_of_events" in data

        assert data["number_of_files"] > 0
        assert data["percentage"] > 0
        assert data["total_duration_seconds"] > 0
        assert data["number_of_events"] > 0

    assert summary["verification"]["is_disjoint"] is True
    assert summary["verification"]["train_val_overlap"] == 0
    assert summary["verification"]["train_test_overlap"] == 0
    assert summary["verification"]["val_test_overlap"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
