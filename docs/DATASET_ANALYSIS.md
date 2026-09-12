# MAESTRO Dataset Analysis & Modeling Implications

This document details the statistical profile of the **MAESTRO (MIDI and Audio Edited for Synchronous TRacks and Organization) v3.0.0** dataset and outlines its architectural implications for training the LSTM/RNN music generation engine in **AI Music Studio**.

---

## 1. Dataset Overview & Integrity

The analysis scanned and verified **100% of the MIDI files** using `music21`:

* **Dataset Path**: `C:\Users\banka\OneDrive\Desktop\maestro-v3.0.0-midi`
* **Total Discovered MIDI Files**: `1,276`
* **Successfully Parsed Files**: `1,276` (`100.0%`)
* **Corrupted / Invalid Files**: `0` (`0.0%`)
* **Total Dataset Size**: `79.98 MB` (`83,863,607 bytes`)
* **Total Performance Duration**: `198.65 hours` (`715,151.48 seconds`)
* **Average Performance Duration**: `9 minutes 20 seconds` (`560.46 seconds`)
* **Total Musical Notes Extracted**: `6,512,506`
* **Average Notes per Piece**: `5,104 notes`
* **Total Musical Chords Extracted**: `253,678`
* **Average Chords per Piece**: `199 chords`
* **Instrument Distribution**: `100% Acoustic Grand Piano` (General MIDI Program 0, captured via Yamaha Disklavier concert pianos)

---

## 2. Repertoire & Split Distribution

The dataset represents virtuosic classical piano literature spanning **60 distinct composers** across multiple stylistic eras (Baroque, Classical, Romantic, Modern).

### Dataset Splits
The official MAESTRO splits isolate distinct musical works to prevent data leakage between training and evaluation:
* **Train Split**: `962 files` (`75.4%`)
* **Validation Split**: `137 files` (`10.7%`)
* **Test Split**: `177 files` (`13.9%`)

### Top 10 Represented Composers

| Composer | Pieces / Performances | Era / Stylistic Character |
| :--- | :---: | :--- |
| **Frédéric Chopin** | 201 | Romantic, highly expressive rubato, intricate ornamental lines |
| **Franz Schubert** | 186 | Classical-Romantic transitional, lyrical vocal melodies, rich harmonic modulation |
| **Ludwig van Beethoven** | 146 | Classical/Heroic, structural rigor, dynamic contrast, polyphonic motifs |
| **Johann Sebastian Bach** | 145 | Baroque, strict counterpoint, fugues, inventions, linear voice leading |
| **Franz Liszt** | 131 | High Romantic virtuosic, dense arpeggiated runs, extended chord voicings |
| **Sergei Rachmaninoff** | 59 | Late Romantic, dense multi-layered chords, wide hand spans |
| **Robert Schumann** | 49 | Romantic, dense polyrhythms, whimsical thematic development |
| **Claude Debussy** | 45 | Impressionist, whole-tone scales, parallel chord progressions |
| **Joseph Haydn** | 40 | Classical, sonata form, clear periodicity, thematic development |
| **Wolfgang Amadeus Mozart** | 38 | Classical, clarity of line, balanced antecedent-consequent phrases |

---

## 3. Harmonic & Tonal Distribution

### Mode Distribution
* **Minor Mode**: `655 pieces` (`51.3%`)
* **Major Mode**: `621 pieces` (`48.7%`)

The dataset exhibits an exceptionally well-balanced distribution between Major and Minor tonalities, ensuring that generative models do not suffer from modal bias.

### Top Tonalities (Krumhansl-Schmuckler Key Analysis)

| Key | Count | Mode | Common Character |
| :--- | :---: | :---: | :--- |
| **C minor** | 90 | Minor | Dramatic, tragic, stormy (e.g., Beethoven Pathetique) |
| **A minor** | 90 | Minor | Melancholic, natural, lyrical |
| **D minor** | 82 | Minor | Somber, contrapuntal (e.g., Bach Toccata & Fugue) |
| **C major** | 80 | Major | Bright, pure, foundational |
| **C# minor** | 74 | Minor | Intense, passionate (e.g., Moonlight Sonata 3rd mvt) |
| **Ab major** | 72 | Major | Warm, expressive, lyrical |
| **Eb major** | 67 | Major | Heroic, noble, expansive |
| **D major** | 65 | Major | Triumphant, celebratory, bright |
| **Bb major** | 59 | Major | Serene, rich, sonorous |
| **C# major** | 53 | Major | Luminous, brilliant |

---

## 4. Implications for LSTM/RNN Model Architecture

### 1. Sequence Length & Context Windows
* **The Challenge**: Pieces average **5,104 notes**, with some extended concertos exceeding **25,000 note events**. Standard LSTM layers suffer from vanishing and exploding gradients when unrolled over thousands of steps, losing coherence beyond 150–300 steps.
* **Architecture Solution**:
  * Implement sliding-window sequence segmentation with fixed sequence lengths (e.g., `sequence_length = 64` or `128` tokens).
  * Train the LSTM to predict the next token given the preceding window: `(batch_size, 64) -> (batch_size, vocabulary_size)`.
  * During generation, seed with a primer sequence (derived from the Groq prompt parameters) and roll generation autoregressively.

### 2. Tokenization Strategy & Vocabulary Design
* **Pitch Range**: The piano covers 88 keys (MIDI pitches `21` to `108`).
* **Note vs. Chord Representation**:
  * Single notes: Represented by MIDI pitch number or pitch name (`C4`, `G#5`, etc.).
  * Chords: Simultaneous notes at identical timestamps can be represented as dot-separated pitch class strings (e.g., `60.64.67` for C Major triad) or serialized with special time-shift tokens.
  * In the MAESTRO dataset, extracting single notes yields **6,512,506 events** and simultaneous groups yield **253,678 chords**.
  * A discrete token vocabulary covering the most common pitches and chords (e.g., vocabulary size ~300 to 500 unique tokens) captures over 99% of all musical events without exponential sparsity.

### 3. Key Normalization & Data Augmentation
* **The Challenge**: A melody in F# Minor uses completely different pitch tokens from the same melody in A Minor, forcing the model to learn 24 independent keys separately.
* **Architecture Solution**:
  * Transpose all pieces to a canonical key (**C Major** for major-mode pieces, **A Minor** for minor-mode pieces) during preprocessing.
  * This compresses the active vocabulary, dramatically speeds up convergence, and teaches the neural network relative musical intervals and voice leading.
  * During generation, the Stage 1 Groq parser determines the user's requested key (e.g., "Eb Minor"), and the post-processing engine transposes the generated tokens back to the target key.

### 4. Integration with the 3-Stage Pipeline

```
[User Prompt]
     │ "A solemn, melancholic piano piece in C minor at 72 BPM"
     ▼
[Stage 1: Groq Semantic Parser]
     │ Returns: {"key": "C", "mode": "minor", "tempo": 72, "style": "chopin"}
     ▼
[Stage 2: LSTM / RNN Generator]
     │ Seeds generation using C minor primer / token distribution
     │ Autoregressively generates sequence of notes and chords
     ▼
[Stage 3: music21 Quantization & Assembly]
     │ Translates token integers -> music21.note.Note & music21.chord.Chord
     │ Applies key signature (3 flats), tempo (72 BPM), 4/4 meter
     │ Writes to .mid and renders to .wav
```

---

## 5. Artifact Reference

* **Full CSV Dataset Inventory**: `dataset/maestro_inventory.csv`
* **Detailed Per-File Analysis**: `dataset/maestro_analysis.csv`
* **Machine-Readable Summary**: `dataset/dataset_summary.json`
* **Automated Analysis Script**: `scripts/analyze_dataset.py`
* **Automated Validation Script**: `scripts/validate_dataset.py`
