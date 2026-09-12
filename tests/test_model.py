"""
AI Music Studio - Unit Tests for Core LSTM Model
Verifies:
1. Dynamic vocabulary model creation with configurable dimensions.
2. Input and output tensor shapes.
3. Softmax probability normalization.
4. Callbacks construction (checkpoint, early stopping, LR scheduling).
5. Model persistence and artifact serialization in models/lstm/v1/.
6. Inference reloadability with co-located vocabulary.
"""

import json
import pytest
import numpy as np
import tensorflow as tf
from pathlib import Path

from ml.model import (
    build_lstm_model,
    get_model_callbacks,
    save_model_artifacts,
    load_model_for_inference,
    verify_forward_pass,
)
from ml.config import LSTM_MODEL_DIR, VOCABULARY_JSON


def test_build_lstm_model_shapes():
    """Verify layer connections and parameter shapes for arbitrary vocabulary size."""
    test_vocab = 500
    test_seq_len = 32
    test_embed = 64
    test_units = 128

    model = build_lstm_model(
        vocab_size=test_vocab,
        sequence_length=test_seq_len,
        embedding_dim=test_embed,
        lstm_units=test_units,
        dropout_rate=0.2,
        learning_rate=0.001,
    )

    assert model.input_shape == (None, test_seq_len)
    assert model.output_shape == (None, test_vocab)
    assert model.loss == "sparse_categorical_crossentropy"


def test_dummy_forward_pass():
    """Verify forward pass returns a valid probability distribution over next tokens."""
    test_vocab = 200
    test_seq_len = 20
    model = build_lstm_model(vocab_size=test_vocab, sequence_length=test_seq_len)

    result = verify_forward_pass(model, sequence_length=test_seq_len, vocab_size=test_vocab, batch_size=3)
    assert result["status"] == "PASSED"
    assert result["output_shape"] == [3, test_vocab]
    assert len(result["softmax_sums"]) == 3
    for s in result["softmax_sums"]:
        assert abs(s - 1.0) < 1e-4


def test_model_callbacks_configuration(tmp_path):
    """Verify that checkpoint, early stopping, and LR reduction callbacks are constructed properly."""
    callbacks = get_model_callbacks(checkpoint_dir=tmp_path)
    assert len(callbacks) == 4

    callback_names = [type(c).__name__ for c in callbacks]
    assert "ModelCheckpoint" in callback_names
    assert "EarlyStopping" in callback_names
    assert "ReduceLROnPlateau" in callback_names
    assert "CSVLogger" in callback_names


def test_save_and_reload_for_inference(tmp_path):
    """Verify saving model, config, and vocabulary, and loading for inference."""
    test_vocab = 150
    test_seq_len = 16
    model = build_lstm_model(vocab_size=test_vocab, sequence_length=test_seq_len)

    # Save artifacts in temporary directory
    save_model_artifacts(
        model=model,
        vocab_size=test_vocab,
        sequence_length=test_seq_len,
        model_dir=tmp_path,
        vocabulary_source_path=VOCABULARY_JSON,
    )

    assert (tmp_path / "model.keras").exists()
    assert (tmp_path / "model_config.json").exists()
    assert (tmp_path / "vocabulary.json").exists()
    assert (tmp_path / "model_summary.txt").exists()

    # Load for inference
    reloaded_model, reloaded_vocab, reloaded_config = load_model_for_inference(tmp_path)
    assert reloaded_model.count_params() == model.count_params()
    assert reloaded_config["vocab_size"] == test_vocab
    assert reloaded_config["sequence_length"] == test_seq_len


def test_versioned_model_artifacts_exist():
    """Verify that models/lstm/v1/ contains all expected artifacts from initial setup."""
    assert LSTM_MODEL_DIR.exists(), f"Missing model dir: {LSTM_MODEL_DIR}"
    assert (LSTM_MODEL_DIR / "model.keras").exists()
    assert (LSTM_MODEL_DIR / "model_config.json").exists()
    assert (LSTM_MODEL_DIR / "vocabulary.json").exists()
    assert (LSTM_MODEL_DIR / "model_summary.txt").exists()

    with open(LSTM_MODEL_DIR / "model_config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    assert config["vocab_size"] == 36700
    assert config["sequence_length"] == 50
    assert config["total_parameters"] == 15049052


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
