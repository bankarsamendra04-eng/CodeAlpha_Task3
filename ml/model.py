"""
AI Music Studio - Core LSTM Music Generation Model
Builds, configures, serializes, and verifies the deep sequential LSTM model for symbolic music generation.

Initial Architecture:
Input (Sequence Length)
→ Embedding (Dynamic Vocabulary Size → Embedding Dim)
→ LSTM Layer 1 (Return Sequences = True)
→ Dropout
→ LSTM Layer 2 (Return Sequences = False)
→ Dropout
→ Dense Output (Dynamic Vocabulary Size)
→ Softmax (Next-token probability distribution)

Requirements & Features:
1. Dynamic vocabulary size (adapts to training vocabulary).
2. Configurable sequence length and dimensional hyperparameters.
3. Sparse categorical crossentropy for next-token prediction.
4. Adam optimizer with configurable learning rate.
5. Model checkpointing, early stopping, and ReduceLROnPlateau scheduling.
6. Versioned model artifacts storage (models/lstm/v1/).
7. Co-located vocabulary and JSON model configuration for inference.
8. Dummy forward pass verification.
"""

import os
import sys
import io
import json
import shutil
from pathlib import Path
from typing import Optional, Union

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import tensorflow as tf
import keras
from keras import layers, callbacks

from ml.config import (
    VOCABULARY_JSON,
    LSTM_MODEL_DIR,
    MODEL_PATH,
    CHECKPOINT_DIR,
    SEQUENCE_LENGTH,
    EMBEDDING_DIM,
    LSTM_UNITS,
    DROPOUT_RATE,
    LEARNING_RATE,
    RANDOM_SEED,
    ENABLE_GPU_GROWTH,
    ENABLE_MIXED_PRECISION,
    TF_INTRA_OP_THREADS,
    TF_INTER_OP_THREADS,
)
from ml.music_representation import Vocabulary


def configure_hardware_acceleration() -> dict:
    """
    Detects hardware capabilities and applies performance optimizations:
    1. GPU Memory Growth: Prevents TensorFlow from allocating 100% of GPU memory up-front.
    2. Mixed Precision: Optional FP16 training when supported by GPU compute capabilities.
    3. CPU Thread Pools: Tunes intra/inter-op parallelism threads when running on multi-core CPUs.
    4. Safe Fallback: Operates stably on CPU if no supported GPU runtime is available.

    Returns:
        dict summarizing the hardware configuration status.
    """
    status = {
        "gpu_available": False,
        "gpus_detected": [],
        "memory_growth_enabled": False,
        "mixed_precision": False,
        "cpu_threads_configured": False,
        "device_strategy": "CPU",
    }
    try:
        gpus = tf.config.list_physical_devices("GPU")
        if gpus:
            status["gpu_available"] = True
            status["gpus_detected"] = [gpu.name for gpu in gpus]
            status["device_strategy"] = f"GPU ({len(gpus)} device(s))"
            for gpu in gpus:
                try:
                    tf.config.experimental.set_memory_growth(gpu, True)
                    status["memory_growth_enabled"] = True
                except Exception:
                    pass
            if ENABLE_MIXED_PRECISION:
                try:
                    from keras import mixed_precision
                    mixed_precision.set_global_policy("mixed_float16")
                    status["mixed_precision"] = True
                except Exception:
                    pass
        else:
            status["device_strategy"] = "CPU (Optimized Multi-Threading)"
            if TF_INTRA_OP_THREADS > 0:
                tf.config.threading.set_intra_op_parallelism_threads(TF_INTRA_OP_THREADS)
                status["cpu_threads_configured"] = True
            if TF_INTER_OP_THREADS > 0:
                tf.config.threading.set_inter_op_parallelism_threads(TF_INTER_OP_THREADS)
                status["cpu_threads_configured"] = True
    except Exception as exc:
        status["error"] = str(exc)
    return status


def build_lstm_model(
    vocab_size: int,
    sequence_length: int = SEQUENCE_LENGTH,
    embedding_dim: int = EMBEDDING_DIM,
    lstm_units: int = LSTM_UNITS,
    dropout_rate: float = DROPOUT_RATE,
    learning_rate: float = LEARNING_RATE,
) -> keras.Model:
    """
    Build and compile the sequential LSTM music generation model.

    Args:
        vocab_size: Total number of unique musical tokens in vocabulary (dynamic).
        sequence_length: Context window length in musical events.
        embedding_dim: Dimensionality of token embedding space.
        lstm_units: Hidden units for recurrent LSTM layers.
        dropout_rate: Dropout fraction for regularization.
        learning_rate: Initial learning rate for Adam optimizer.

    Returns:
        Compiled keras.Model instance.
    """
    if vocab_size <= 0:
        raise ValueError(f"Vocabulary size must be positive, got {vocab_size}")
    if sequence_length <= 0:
        raise ValueError(f"Sequence length must be positive, got {sequence_length}")

    model = keras.Sequential(
        [
            layers.Input(shape=(sequence_length,), name="token_sequence_input"),
            layers.Embedding(
                input_dim=vocab_size,
                output_dim=embedding_dim,
                name="token_embedding",
            ),
            layers.LSTM(
                lstm_units,
                return_sequences=True,
                name="lstm_layer_1",
            ),
            layers.Dropout(dropout_rate, name="dropout_1"),
            layers.LSTM(
                lstm_units,
                return_sequences=False,
                name="lstm_layer_2",
            ),
            layers.Dropout(dropout_rate, name="dropout_2"),
            layers.Dense(vocab_size, activation="softmax", name="output_probabilities"),
        ],
        name="AI_Music_Studio_LSTM",
    )

    optimizer = keras.optimizers.Adam(learning_rate=learning_rate)
    model.compile(
        optimizer=optimizer,
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    return model


def get_model_callbacks(
    checkpoint_dir: Path = CHECKPOINT_DIR,
    monitor_metric: str = "val_loss",
    early_stopping_patience: int = 5,
    reduce_lr_patience: int = 2,
    reduce_lr_factor: float = 0.5,
    min_lr: float = 1e-6,
) -> list[callbacks.Callback]:
    """
    Construct standard training callbacks:
    - ModelCheckpoint: Saves the best model based on validation loss.
    - EarlyStopping: Halts training when validation loss stops improving.
    - ReduceLROnPlateau: Decays learning rate upon learning plateaus.
    - CSVLogger: Logs epoch-level metrics.
    """
    checkpoint_dir = Path(checkpoint_dir).resolve()
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    best_model_path = checkpoint_dir / "best_model.keras"
    log_file_path = checkpoint_dir / "training_history.csv"

    callback_list = [
        # 1. Model Checkpoint (Save Best Model)
        callbacks.ModelCheckpoint(
            filepath=str(best_model_path),
            monitor=monitor_metric,
            save_best_only=True,
            mode="min",
            verbose=1,
        ),
        # 2. Early Stopping
        callbacks.EarlyStopping(
            monitor=monitor_metric,
            patience=early_stopping_patience,
            restore_best_weights=True,
            mode="min",
            verbose=1,
        ),
        # 3. Learning Rate Reduction on Plateau
        callbacks.ReduceLROnPlateau(
            monitor=monitor_metric,
            factor=reduce_lr_factor,
            patience=reduce_lr_patience,
            min_lr=min_lr,
            mode="min",
            verbose=1,
        ),
        # 4. Training metrics logger
        callbacks.CSVLogger(
            filename=str(log_file_path),
            separator=",",
            append=False,
        ),
    ]

    return callback_list


def get_model_summary_string(model: keras.Model) -> str:
    """Capture model.summary() output as a string."""
    stream = io.StringIO()
    model.summary(print_fn=lambda x: stream.write(x + "\n"))
    return stream.getvalue()


def save_model_artifacts(
    model: keras.Model,
    vocab_size: int,
    sequence_length: int,
    model_dir: Path = LSTM_MODEL_DIR,
    vocabulary_source_path: Path = VOCABULARY_JSON,
    extra_config: Optional[dict] = None,
) -> dict:
    """
    Save complete versioned model artifacts:
    - model.keras: Architecture and weights.
    - model_config.json: Hyperparameters and dimensional specifications.
    - vocabulary.json: Dynamic token mapping co-located with model.
    - model_summary.txt: Formatted layer-by-layer parameter summary.
    """
    model_dir = Path(model_dir).resolve()
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / "model.keras"
    config_path = model_dir / "model_config.json"
    vocab_dest_path = model_dir / "vocabulary.json"
    summary_path = model_dir / "model_summary.txt"

    # 1. Save Keras Model
    model.save(str(model_path))

    # 2. Co-locate vocabulary alongside model
    if Path(vocabulary_source_path).exists():
        shutil.copy2(vocabulary_source_path, vocab_dest_path)
    else:
        # Save placeholder vocabulary
        vocab = Vocabulary()
        vocab.save(vocab_dest_path)

    # 3. Save model configuration
    config_data = {
        "model_type": "LSTM",
        "model_name": model.name,
        "version": model_dir.name,
        "vocab_size": vocab_size,
        "sequence_length": sequence_length,
        "embedding_dim": EMBEDDING_DIM,
        "lstm_units": LSTM_UNITS,
        "dropout_rate": DROPOUT_RATE,
        "learning_rate": LEARNING_RATE,
        "loss": "sparse_categorical_crossentropy",
        "optimizer": "adam",
        "total_parameters": int(model.count_params()),
        "trainable_parameters": int(sum(np.prod(p.shape) for p in model.trainable_weights)),
    }
    if extra_config:
        config_data.update(extra_config)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)

    # 4. Save model summary text
    summary_str = get_model_summary_string(model)
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_str)

    print(f"[+] Model artifacts saved to: {model_dir}")
    print(f"    - Model file     : {model_path.name}")
    print(f"    - Config file    : {config_path.name}")
    print(f"    - Vocabulary file: {vocab_dest_path.name}")
    print(f"    - Summary file   : {summary_path.name}")

    return config_data


def load_model_for_inference(
    model_dir: Union[str, Path] = LSTM_MODEL_DIR,
) -> tuple[keras.Model, Vocabulary, dict]:
    """
    Load a trained model, its configuration, and its co-located vocabulary for inference.

    Returns:
        (model, vocabulary, config_dict)
    """
    model_dir = Path(model_dir).resolve()
    model_path = model_dir / "model.keras"
    config_path = model_dir / "model_config.json"
    vocab_path = model_dir / "vocabulary.json"

    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    if not vocab_path.exists():
        raise FileNotFoundError(f"Vocabulary file not found: {vocab_path}")

    # Load model
    model = keras.models.load_model(str(model_path))

    # Load config
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Load vocabulary
    vocab = Vocabulary.load(vocab_path)

    return model, vocab, config


def verify_forward_pass(
    model: keras.Model,
    sequence_length: int = SEQUENCE_LENGTH,
    vocab_size: Optional[int] = None,
    batch_size: int = 2,
) -> dict:
    """
    Execute a dummy forward pass through the model to verify shape integrity,
    softmax probability normalization, and tensor flow.

    Returns:
        Verification summary dictionary.
    """
    if vocab_size is None:
        vocab_size = model.output_shape[-1]

    # Generate random integer token sequences in range [0, vocab_size - 1]
    dummy_input = np.random.randint(0, vocab_size, size=(batch_size, sequence_length), dtype=np.int32)

    # Forward pass
    predictions = model(dummy_input, training=False).numpy()

    # Integrity assertions
    assert predictions.shape == (batch_size, vocab_size), (
        f"Output shape mismatch: expected ({batch_size}, {vocab_size}), got {predictions.shape}"
    )

    # Verify softmax property: each row sums to 1.0
    row_sums = np.sum(predictions, axis=-1)
    np.testing.assert_allclose(
        row_sums,
        np.ones(batch_size),
        rtol=1e-4,
        atol=1e-4,
        err_msg="Softmax probabilities do not sum to 1.0",
    )

    # Verify predictions are non-negative
    assert np.all(predictions >= 0.0), "Found negative probabilities in output"

    verification_result = {
        "status": "PASSED",
        "input_shape": list(dummy_input.shape),
        "output_shape": list(predictions.shape),
        "softmax_sums": [float(round(s, 6)) for s in row_sums],
        "top_token_id_sample_0": int(np.argmax(predictions[0])),
        "top_prob_sample_0": float(round(float(np.max(predictions[0])), 6)),
        "is_valid_distribution": True,
    }

    return verification_result


def main():
    """Build, summarize, save artifacts, and verify forward pass without training."""
    print("=" * 65)
    print("       AI MUSIC STUDIO - LSTM MODEL INITIALIZATION")
    print("=" * 65)

    # 1. Determine dynamic vocabulary size from processed vocabulary
    if VOCABULARY_JSON.exists():
        vocab = Vocabulary.load(VOCABULARY_JSON)
        vocab_size = len(vocab)
        print(f"[+] Loaded dynamic vocabulary: {vocab_size:,} unique tokens from {VOCABULARY_JSON}")
    else:
        vocab_size = 1000
        print(f"[!] Warning: Vocabulary not found at {VOCABULARY_JSON}. Using fallback size: {vocab_size}")

    print(f"Model Directory     : {LSTM_MODEL_DIR}")
    print(f"Sequence Length     : {SEQUENCE_LENGTH}")
    print(f"Embedding Dim       : {EMBEDDING_DIM}")
    print(f"LSTM Units          : {LSTM_UNITS}")
    print(f"Dropout Rate        : {DROPOUT_RATE}")
    print(f"Learning Rate       : {LEARNING_RATE}")
    print("=" * 65)

    # 2. Build model
    model = build_lstm_model(
        vocab_size=vocab_size,
        sequence_length=SEQUENCE_LENGTH,
        embedding_dim=EMBEDDING_DIM,
        lstm_units=LSTM_UNITS,
        dropout_rate=DROPOUT_RATE,
        learning_rate=LEARNING_RATE,
    )

    # 3. Print Model Summary
    print("\n" + "=" * 65)
    print("                     MODEL SUMMARY")
    print("=" * 65)
    model.summary()

    # 4. Save model artifacts (models/lstm/v1/)
    print("\n" + "=" * 65)
    print("                 SAVING MODEL ARTIFACTS")
    print("=" * 65)
    config = save_model_artifacts(
        model=model,
        vocab_size=vocab_size,
        sequence_length=SEQUENCE_LENGTH,
        model_dir=LSTM_MODEL_DIR,
        vocabulary_source_path=VOCABULARY_JSON,
    )

    # 5. Verify forward pass
    print("\n" + "=" * 65)
    print("               VERIFYING FORWARD PASS")
    print("=" * 65)
    res = verify_forward_pass(model, sequence_length=SEQUENCE_LENGTH, vocab_size=vocab_size)
    print(f"Input Tensor Shape  : {res['input_shape']}")
    print(f"Output Tensor Shape : {res['output_shape']}")
    print(f"Softmax Row Sums    : {res['softmax_sums']}")
    print(f"Sample 0 Prediction : Token ID {res['top_token_id_sample_0']} (p={res['top_prob_sample_0']})")
    print(f"[OK] FORWARD PASS VERIFICATION: {res['status']}")

    # 6. Verify model reloadability for inference
    print("\n" + "=" * 65)
    print("            VERIFYING INFERENCE RELOADABILITY")
    print("=" * 65)
    reloaded_model, reloaded_vocab, reloaded_config = load_model_for_inference(LSTM_MODEL_DIR)
    assert len(reloaded_vocab) == vocab_size, "Reloaded vocabulary size mismatch"
    assert reloaded_model.count_params() == model.count_params(), "Reloaded model parameter count mismatch"
    print("[OK] RELOADABILITY VERIFIED: Model and vocabulary successfully loaded for future inference.")
    print("=" * 65)
    print("[*] Model initialized. Ready for training phase when requested.")


if __name__ == "__main__":
    main()
