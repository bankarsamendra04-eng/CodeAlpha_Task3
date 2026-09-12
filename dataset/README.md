# MAESTRO Dataset Configuration & Inventory

This directory manages the connection to the **MAESTRO (MIDI and Audio Edited for Synchronous TRacks and Organization) v3.0.0** dataset for the AI Music Studio.

---

## 📍 Dataset Location & Linking

To prevent duplicating tens or hundreds of megabytes of MIDI files, the project references the existing dataset location on your computer:

* **Configured Path (`DATASET_PATH`)**: `C:\Users\banka\OneDrive\Desktop\maestro-v3.0.0-midi`
* **Local Fallback**: `dataset/midi/` (if files are placed locally)

The path can be adjusted at any time in `.env`:
```env
DATASET_PATH=C:\Users\banka\OneDrive\Desktop\maestro-v3.0.0-midi
```

---

## 📊 Dataset Inventory & Metadata

Running `python scripts/prepare_dataset.py` creates:
* `dataset/maestro_inventory.csv`

This inventory contains:
1. `file_path`: Absolute file path on disk
2. `filename`: Standard MIDI filename
3. `relative_path`: Relative path within MAESTRO
4. `year`: Year of performance
5. `composer`: Canonical composer (from MAESTRO metadata)
6. `title`: Canonical title of the musical piece
7. `split`: Dataset split (`train`, `validation`, `test`)
8. `duration`: Performance duration in seconds
9. `file_size_bytes`: Size in bytes
10. `number_of_notes`: Total extracted musical notes
11. `number_of_chords`: Total extracted musical chords
12. `parsing_status`: Status (`VALID` or `INVALID`)
13. `error_message`: Any parsing error details

---

## 🛠️ Utility Scripts

1. **Dataset Discovery & Inventory Preparation**:
   ```powershell
   python scripts/prepare_dataset.py
   ```

2. **Full Music21 Parsing & Dataset Validation**:
   ```powershell
   python scripts/validate_dataset.py
   ```
