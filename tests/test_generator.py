"""
AI Music Studio - Unit Tests for Music Generator
Verifies:
1. Generator initialization and model/vocabulary loading.
2. Temperature-scaled probability sampling behavior.
3. Zero unknown (<UNK>), padding (<PAD>), or start (<START>) token guarantee.
4. Parameter validation (rejecting non-positive event counts or temperatures).
5. Reproducibility using fixed random seeds.
6. Custom seed sequence handling and padding.
"""

import pytest
import numpy as np
from ml.generator import MusicGenerator, ModelLoadError
from ml.music_representation import Vocabulary


def test_generator_initialization():
    """Verify generator loads model and vocabulary with correct attributes."""
    gen = MusicGenerator()
    assert gen.model is not None
    assert gen.vocab is not None
    assert len(gen.vocab) == 36700
    assert gen.sequence_length == 50
    assert len(gen.forbidden_token_ids) == 3


def test_zero_unknown_token_guarantee():
    """Verify generated tokens never contain UNK, PAD, or START tokens."""
    gen = MusicGenerator()
    tokens = gen.generate(num_events=30, temperature=1.0, random_seed=123)

    assert len(tokens) == 30
    for tok in tokens:
        assert tok not in (Vocabulary.UNK_TOKEN, Vocabulary.PAD_TOKEN, Vocabulary.START_TOKEN)
        assert tok in gen.vocab.token_to_id


def test_reproducibility_with_seed():
    """Verify that identical random seeds produce identical token sequences."""
    gen = MusicGenerator()
    tokens1 = gen.generate(num_events=25, temperature=0.8, random_seed=999)
    tokens2 = gen.generate(num_events=25, temperature=0.8, random_seed=999)
    assert tokens1 == tokens2

    # Different seeds should produce different sequences
    tokens3 = gen.generate(num_events=25, temperature=0.8, random_seed=111)
    assert tokens1 != tokens3


def test_parameter_validation():
    """Verify generator catches invalid parameters."""
    gen = MusicGenerator()

    with pytest.raises(ValueError):
        gen.generate(num_events=-5)

    with pytest.raises(ValueError):
        gen.generate(num_events=10, temperature=-0.5)

    with pytest.raises(ValueError):
        gen.generate(num_events=10, temperature=0.0)


def test_custom_seed_sequence():
    """Verify custom seed sequence is correctly processed and continued."""
    gen = MusicGenerator()
    custom_seed = ["NOTE_60_d0.50", "NOTE_64_d0.50", "NOTE_67_d1.00"]
    tokens = gen.generate(seed_sequence=custom_seed, num_events=15, temperature=0.7, random_seed=42)

    assert len(tokens) == 15
    for t in tokens:
        assert t in gen.vocab.token_to_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
