"""
AI Music Studio - Unit Tests for Training Pipeline
Verifies:
1. ChunkSequenceDataset batch iteration and memory safety.
2. Dataset length calculations across chunk files.
3. Training artifacts existence in models/lstm/v1/ and reports/.
4. Training history CSV and summary MD file integrity.
"""

import json
import pytest
import pandas as pd
from pathlib import Path

from ml.train import ChunkSequenceDataset
from ml.config import (
    TRAINING_DATA_DIR,
    LSTM_MODEL_DIR,
    PROJECT_ROOT,
)


def test_chunk_sequence_dataset_iteration():
    """Verify ChunkSequenceDataset provides batches of correct shape and type."""
    train_dir = TRAINING_DATA_DIR / "train"
    ds = ChunkSequenceDataset(train_dir, batch_size=256, max_batches=3)
    assert len(ds) == 3

    batch_x, batch_y = ds[0]
    assert batch_x.shape == (256, 50)
    assert batch_y.shape == (256,)
    assert batch_x.dtype == "int32" or batch_x.dtype == "int64"


def test_saved_model_and_training_artifacts():
    """Verify that models/lstm/v1 contains trained model, best model, vocabulary, and history."""
    assert (LSTM_MODEL_DIR / "model.keras").exists()
    assert (LSTM_MODEL_DIR / "best_model.keras").exists()
    assert (LSTM_MODEL_DIR / "vocabulary.json").exists()
    assert (LSTM_MODEL_DIR / "model_config.json").exists()
    assert (LSTM_MODEL_DIR / "training_history.json").exists()
    assert (LSTM_MODEL_DIR / "metrics.json").exists()

    with open(LSTM_MODEL_DIR / "metrics.json", "r") as f:
        metrics = json.load(f)
    assert metrics["epochs_completed"] >= 1
    assert "test_metrics" in metrics
    assert "loss" in metrics["test_metrics"]


def test_reports_generated():
    """Verify reports/training_history.csv and reports/training_summary.md exist."""
    csv_report = PROJECT_ROOT / "reports" / "training_history.csv"
    md_report = PROJECT_ROOT / "reports" / "training_summary.md"

    assert csv_report.exists()
    assert md_report.exists()

    df = pd.read_csv(csv_report)
    assert len(df) >= 1
    assert "loss" in df.columns
    assert "val_loss" in df.columns

    with open(md_report, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Evaluation on Held-Out Test Split" in content
    assert "Objective Performance Assessment" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
