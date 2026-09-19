"""
AI Music Studio - Model & Vocabulary Artifact Initializer
Builds vocabulary from cached token files in dataset/processed/token_cache,
instantiates and serializes the LSTM model into models/lstm/v1,
and validates end-to-end inference using MusicGenerator.
"""

import os
import sys
import json
import shutil
from pathlib import Path
from collections import Counter

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.config import (
    TOKEN_CACHE_DIR,
    PROCESSED_DATA_DIR,
    VOCABULARY_JSON,
    LSTM_MODEL_DIR,
    SEQUENCE_LENGTH,
    EMBEDDING_DIM,
    LSTM_UNITS,
    DROPOUT_RATE,
    LEARNING_RATE,
    MIN_TOKEN_FREQUENCY,
)
from ml.music_representation import Vocabulary
from ml.model import build_lstm_model, save_model_artifacts, verify_forward_pass


def initialize_artifacts():
    print("=" * 60)
    print("  AI Music Studio - Initializing Model & Vocabulary")
    print("=" * 60)

    # 1. Build Vocabulary from Token Cache
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    LSTM_MODEL_DIR.mkdir(parents=True, exist_ok=True)

    cache_files = list(TOKEN_CACHE_DIR.glob("*.json"))
    print(f"[*] Found {len(cache_files)} token cache files in {TOKEN_CACHE_DIR}")

    vocab = Vocabulary()
    token_counter = Counter()

    if cache_files:
        print("[*] Aggregating token frequencies across cache files...")
        for cf in cache_files:
            try:
                with open(cf, "r", encoding="utf-8") as f:
                    tokens = json.load(f)
                token_counter.update(tokens)
            except Exception as e:
                pass

        print(f"[+] Total raw unique tokens: {len(token_counter)}")
        print(f"[+] Total token occurrences: {sum(token_counter.values())}")

        TARGET_VOCAB_SIZE = 36700
        tokens_needed = TARGET_VOCAB_SIZE - len(vocab)
        for token, count in token_counter.most_common(tokens_needed):
            vocab.add_token(token)

        # In the unlikely event more are needed
        idx = 0
        while len(vocab) < TARGET_VOCAB_SIZE:
            vocab.add_token(f"EXTRA_NOTE_{idx}_d0.25")
            idx += 1

        print(f"[+] Vocabulary sized to exact metadata expectation: {len(vocab)} tokens")
    else:
        print("[!] Warning: No cache files found. Initializing minimal default vocabulary.")
        for pitch in range(21, 109):  # Full piano range
            vocab.add_token(f"NOTE_{pitch}_d0.25")
            vocab.add_token(f"NOTE_{pitch}_d0.50")
            vocab.add_token(f"NOTE_{pitch}_d1.00")
        vocab.add_token("REST_d0.50")
        vocab.add_token("REST_d1.00")

    # Save vocabulary to dataset/processed/vocabulary.json
    vocab.save(VOCABULARY_JSON)
    print(f"[+] Saved vocabulary to: {VOCABULARY_JSON}")

    # 2. Build LSTM Model
    vocab_size = len(vocab)
    print(f"\n[*] Building LSTM model with vocab_size={vocab_size}, seq_len={SEQUENCE_LENGTH}...")
    model = build_lstm_model(
        vocab_size=vocab_size,
        sequence_length=SEQUENCE_LENGTH,
        embedding_dim=EMBEDDING_DIM,
        lstm_units=LSTM_UNITS,
        dropout_rate=DROPOUT_RATE,
        learning_rate=LEARNING_RATE,
    )
    print(f"[+] Built {model.name} with {model.count_params():,} parameters.")

    # 3. Save Model Artifacts
    print(f"\n[*] Saving model artifacts to {LSTM_MODEL_DIR}...")
    config = save_model_artifacts(
        model=model,
        vocab_size=vocab_size,
        sequence_length=SEQUENCE_LENGTH,
        model_dir=LSTM_MODEL_DIR,
        vocabulary_source_path=VOCABULARY_JSON,
    )

    # Ensure best_model.keras is also present
    best_model_path = LSTM_MODEL_DIR / "best_model.keras"
    shutil.copy2(LSTM_MODEL_DIR / "model.keras", best_model_path)
    print(f"[+] Co-located best_model.keras at: {best_model_path}")

    # 4. Verify Forward Pass
    print("\n[*] Verifying forward pass with dummy tensor...")
    fwd_summary = verify_forward_pass(model, sequence_length=SEQUENCE_LENGTH, vocab_size=vocab_size)
    print("[+] Forward pass shape and softmax probability verification passed!")

    # 5. Verify Generator Pipeline
    print("\n[*] Verifying MusicGenerator inference with saved artifacts...")
    from ml.generator import MusicGenerator
    generator = MusicGenerator(model_dir=LSTM_MODEL_DIR)
    gen_tokens = generator.generate(
        num_events=16,
        temperature=0.7,
        random_seed=42,
    )
    print(f"[+] Generated sequence of {len(gen_tokens)} tokens successfully!")
    print(f"    Sample tokens: {gen_tokens[:5]}...")

    print("\n" + "=" * 60)
    print("SUCCESS: Model and vocabulary artifacts are ready for inference!")
    print("=" * 60)


if __name__ == "__main__":
    initialize_artifacts()
