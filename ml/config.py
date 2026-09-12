"""
AI Music Studio - Machine Learning Configuration
Manages all model hyperparameters, paths, and environment settings.
All settings can be overridden via environment variables or .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve project root dynamically (no hardcoded absolute paths)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load environment variables from .env
load_dotenv(PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# Path Configurations
# ---------------------------------------------------------------------------
# Default to existing dataset path from .env, with local fallback
DATASET_PATH = Path(
    os.getenv("DATASET_PATH", str(PROJECT_ROOT / "dataset" / "midi"))
).resolve()

# Processed data directories (vocabulary, metadata, chunked training arrays)
PROCESSED_DATA_DIR = Path(
    os.getenv("PROCESSED_DATA_DIR", str(PROJECT_ROOT / "dataset" / "processed"))
).resolve()
PREPROCESSED_DATA_PATH = PROCESSED_DATA_DIR

TRAINING_DATA_DIR = PROCESSED_DATA_DIR / "training_data"
TOKEN_CACHE_DIR = PROCESSED_DATA_DIR / "token_cache"
VOCABULARY_JSON = PROCESSED_DATA_DIR / "vocabulary.json"
METADATA_JSON = PROCESSED_DATA_DIR / "metadata.json"

# Dataset split paths (80% train, 10% validation, 10% test)
SPLITS_DIR = Path(
    os.getenv("SPLITS_DIR", str(PROJECT_ROOT / "dataset" / "splits"))
).resolve()
TRAIN_SPLIT_CSV = SPLITS_DIR / "train.csv"
VAL_SPLIT_CSV = SPLITS_DIR / "validation.csv"
TEST_SPLIT_CSV = SPLITS_DIR / "test.csv"
SPLIT_SUMMARY_JSON = SPLITS_DIR / "split_summary.json"

# Models & Checkpoint directories (versioned structure: models/lstm/v1/)
MODEL_DIR = Path(
    os.getenv("MODEL_DIR", str(PROJECT_ROOT / "models"))
).resolve()

MODEL_VERSION = os.getenv("MODEL_VERSION", "v1")
LSTM_MODEL_DIR = MODEL_DIR / "lstm" / MODEL_VERSION
VERSIONED_MODEL_DIR = LSTM_MODEL_DIR

MODEL_PATH = Path(
    os.getenv("MODEL_PATH", str(LSTM_MODEL_DIR / "model.keras"))
).resolve()

CHECKPOINT_DIR = Path(
    os.getenv("CHECKPOINT_DIR", str(LSTM_MODEL_DIR / "checkpoints"))
).resolve()

VOCABULARY_PATH = VOCABULARY_JSON  # Alias for vocabulary path

OUTPUT_PATH = Path(
    os.getenv("OUTPUT_PATH", str(PROJECT_ROOT / "output"))
).resolve()
MIDI_OUTPUT_DIR = OUTPUT_PATH / "midi"
AUDIO_OUTPUT_DIR = OUTPUT_PATH / "audio"

# External Audio Rendering Configurations (FluidSynth & SoundFont)
FLUIDSYNTH_PATH = os.getenv("FLUIDSYNTH_PATH", None)
SOUNDFONT_PATH = os.getenv("SOUNDFONT_PATH", None)

INVENTORY_PATH = PROJECT_ROOT / "dataset" / "maestro_inventory.csv"
ANALYSIS_PATH = PROJECT_ROOT / "dataset" / "maestro_analysis.csv"

# ---------------------------------------------------------------------------
# Hyperparameters & Sequence Modeling
# ---------------------------------------------------------------------------
# Number of musical events in each input window (configurable, default 50)
SEQUENCE_LENGTH = int(os.getenv("SEQUENCE_LENGTH", "50"))

# Chunk size for saving training arrays to disk
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "50000"))

# Minimum frequency for tokens to be included in vocabulary (rare outliers mapped to <UNK>)
MIN_TOKEN_FREQUENCY = int(os.getenv("MIN_TOKEN_FREQUENCY", "5"))

# Mini-batch training size
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "64"))

# Training iterations
EPOCHS = int(os.getenv("EPOCHS", "50"))

# Fraction of dataset used for evaluation
VALIDATION_SPLIT = float(os.getenv("VALIDATION_SPLIT", "0.2"))

# Reproducibility seed
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))

# ---------------------------------------------------------------------------
# Architecture Configurations
# ---------------------------------------------------------------------------
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "128"))
LSTM_UNITS = int(os.getenv("LSTM_UNITS", "256"))
NUM_LSTM_LAYERS = int(os.getenv("NUM_LSTM_LAYERS", "2"))
DROPOUT_RATE = float(os.getenv("DROPOUT_RATE", "0.3"))
LEARNING_RATE = float(os.getenv("LEARNING_RATE", "0.001"))

# ---------------------------------------------------------------------------
# Hardware Acceleration & Performance Configurations
# ---------------------------------------------------------------------------
ENABLE_GPU_GROWTH = os.getenv("ENABLE_GPU_GROWTH", "true").lower() in ("true", "1", "yes")
ENABLE_MIXED_PRECISION = os.getenv("ENABLE_MIXED_PRECISION", "false").lower() in ("true", "1", "yes")
TF_INTRA_OP_THREADS = int(os.getenv("TF_INTRA_OP_THREADS", "0"))
TF_INTER_OP_THREADS = int(os.getenv("TF_INTER_OP_THREADS", "0"))
MODEL_CACHE_ENABLED = os.getenv("MODEL_CACHE_ENABLED", "true").lower() in ("true", "1", "yes")
PROMPT_CACHE_MAX_SIZE = int(os.getenv("PROMPT_CACHE_MAX_SIZE", "256"))
FILE_RETENTION_HOURS = int(os.getenv("FILE_RETENTION_HOURS", "72"))

# ---------------------------------------------------------------------------
# Ensure Essential Directories Exist
# ---------------------------------------------------------------------------
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)
TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
MIDI_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_config_summary():
    """Return a dictionary of all active configurations."""
    return {
        "DATASET_PATH": str(DATASET_PATH),
        "PROCESSED_DATA_DIR": str(PROCESSED_DATA_DIR),
        "TRAINING_DATA_DIR": str(TRAINING_DATA_DIR),
        "VOCABULARY_JSON": str(VOCABULARY_JSON),
        "METADATA_JSON": str(METADATA_JSON),
        "MODEL_PATH": str(MODEL_PATH),
        "CHECKPOINT_DIR": str(CHECKPOINT_DIR),
        "OUTPUT_PATH": str(OUTPUT_PATH),
        "MIDI_OUTPUT_DIR": str(MIDI_OUTPUT_DIR),
        "AUDIO_OUTPUT_DIR": str(AUDIO_OUTPUT_DIR),
        "FLUIDSYNTH_PATH": str(FLUIDSYNTH_PATH),
        "SOUNDFONT_PATH": str(SOUNDFONT_PATH),
        "SEQUENCE_LENGTH": SEQUENCE_LENGTH,
        "CHUNK_SIZE": CHUNK_SIZE,
        "MIN_TOKEN_FREQUENCY": MIN_TOKEN_FREQUENCY,
        "BATCH_SIZE": BATCH_SIZE,
        "EPOCHS": EPOCHS,
        "VALIDATION_SPLIT": VALIDATION_SPLIT,
        "RANDOM_SEED": RANDOM_SEED,
    }


if __name__ == "__main__":
    print("=== AI Music Studio ML Configuration ===")
    for k, v in get_config_summary().items():
        print(f"  {k}: {v}")
