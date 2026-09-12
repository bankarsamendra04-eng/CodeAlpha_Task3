"""
AI Music Studio - Machine Learning Utilities
Provides data transformation, vocabulary serialization, seed setting,
and sequence encoding functions for LSTM model training and inference.
"""

import os
import json
import random
import pathlib
import joblib
import numpy as np
import tensorflow as tf
import music21

from ml.config import RANDOM_SEED, VOCABULARY_PATH


def set_seed(seed: int = RANDOM_SEED):
    """Set random seeds across Python, NumPy, and TensorFlow for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def save_vocabulary(vocab_to_int: dict, file_path: pathlib.Path = VOCABULARY_PATH):
    """Save token-to-integer vocabulary mapping as JSON."""
    file_path = pathlib.Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(vocab_to_int, f, indent=2)


def load_vocabulary(file_path: pathlib.Path = VOCABULARY_PATH) -> tuple[dict, dict]:
    """
    Load vocabulary mapping from JSON.
    Returns:
        (vocab_to_int, int_to_vocab)
    """
    file_path = pathlib.Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Vocabulary file not found at: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        vocab_to_int = json.load(f)

    int_to_vocab = {int(idx): token for token, idx in vocab_to_int.items()}
    return vocab_to_int, int_to_vocab


def save_artifact(obj, file_path: pathlib.Path):
    """Persist preprocessed numpy arrays or token lists with joblib."""
    file_path = pathlib.Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(obj, file_path, compress=3)


def load_artifact(file_path: pathlib.Path):
    """Load persisted joblib object."""
    file_path = pathlib.Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Artifact not found: {file_path}")
    return joblib.load(file_path)


def create_sliding_windows(token_sequence: list[int], seq_length: int = 64) -> tuple[np.ndarray, np.ndarray]:
    """
    Transform a 1D integer sequence of tokens into sliding-window (X, y) training pairs:
    Input X shape: (num_samples, seq_length)
    Target y shape: (num_samples,)
    """
    if len(token_sequence) <= seq_length:
        return np.empty((0, seq_length), dtype=np.int32), np.empty((0,), dtype=np.int32)

    X, y = [], []
    for i in range(len(token_sequence) - seq_length):
        X.append(token_sequence[i : i + seq_length])
        y.append(token_sequence[i + seq_length])

    return np.array(X, dtype=np.int32), np.array(y, dtype=np.int32)


def token_to_music21_element(token: str) -> music21.note.GeneralNote:
    """
    Convert a string token back to a music21 Note or Chord object.
    Supports single pitch names (e.g. 'C4', 'D#5') or chord pitch strings (e.g. '60.64.67').
    """
    if "." in token:
        # Multi-pitch chord representation
        pitches = [int(p) for p in token.split(".") if p.isdigit()]
        return music21.chord.Chord(pitches)
    elif token.isdigit():
        return music21.note.Note(int(token))
    else:
        return music21.note.Note(token)


def tokens_to_stream(tokens: list[str], tempo_bpm: float = 120.0, time_sig: str = "4/4") -> music21.stream.Stream:
    """
    Assemble a list of token strings into a playable music21 Stream.
    """
    s = music21.stream.Stream()
    s.append(music21.meter.TimeSignature(time_sig))
    s.append(music21.tempo.MetronomeMark(number=tempo_bpm))
    s.append(music21.instrument.Piano())

    for tok in tokens:
        try:
            elem = token_to_music21_element(tok)
            elem.duration = music21.duration.Duration(0.5)  # Default eighth note
            s.append(elem)
        except Exception:
            continue

    return s
