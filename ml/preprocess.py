"""
AI Music Studio - MAESTRO Dataset Preprocessing Pipeline
Processes raw MIDI files from DATASET_PATH into quantized musical tokens, builds a filtered
vocabulary, creates fixed-length sliding-window sequence pairs (X, y), and saves them
in memory-safe chunked NumPy arrays (.npz) on disk.

Features:
- Incremental processing: caches extracted tokens per MIDI file to avoid re-processing.
- Multi-worker parallelism: utilizes multiple CPU cores for fast MIDI extraction.
- Memory safe: streams files one by one, never loading the whole dataset into RAM.
- Fault tolerant: isolates corrupted MIDI files safely and records them in metadata.
- Configurable sequence length, chunk size, and minimum token frequency.
- Generates comprehensive metadata.json and preprocessing statistics.
"""

import os
import sys
import time
import json
from pathlib import Path

# Ensure project root is on sys.path when script is executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
from datetime import datetime
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional

import numpy as np
from tqdm import tqdm

from ml.config import (
    DATASET_PATH,
    PROCESSED_DATA_DIR,
    TRAINING_DATA_DIR,
    TOKEN_CACHE_DIR,
    VOCABULARY_JSON,
    METADATA_JSON,
    SPLITS_DIR,
    TRAIN_SPLIT_CSV,
    VAL_SPLIT_CSV,
    TEST_SPLIT_CSV,
    SPLIT_SUMMARY_JSON,
    SEQUENCE_LENGTH,
    CHUNK_SIZE,
    MIN_TOKEN_FREQUENCY,
    RANDOM_SEED,
)
from ml.music_representation import Vocabulary, midi_to_tokens
from scripts.create_dataset_splits import create_splits


def _process_single_midi_worker(args: tuple[str, str, str, bool]) -> dict:
    """
    Top-level worker function for multiprocessing MIDI extraction.
    Args: (midi_path_str, cache_path_str, rel_path, force)
    """
    midi_path_str, cache_path_str, rel_path, force = args
    midi_path = Path(midi_path_str)
    cache_path = Path(cache_path_str)

    # Check cache validity
    if not force and cache_path.exists():
        try:
            if cache_path.stat().st_mtime >= midi_path.stat().st_mtime:
                with open(cache_path, "r", encoding="utf-8") as f:
                    tokens = json.load(f)
                return {
                    "rel_path": rel_path,
                    "cache_path": str(cache_path),
                    "status": "CACHED",
                    "num_tokens": len(tokens),
                    "error": None,
                }
        except Exception:
            pass  # Fall through and re-extract if cache is corrupted

    try:
        tokens = midi_to_tokens(midi_path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(tokens, f)
        return {
            "rel_path": rel_path,
            "cache_path": str(cache_path),
            "status": "PROCESSED",
            "num_tokens": len(tokens),
            "error": None,
        }
    except Exception as exc:
        return {
            "rel_path": rel_path,
            "cache_path": str(cache_path),
            "status": "FAILED",
            "num_tokens": 0,
            "error": str(exc),
        }


class MaestroPreprocessor:
    """
    Production-grade preprocessing pipeline for the MAESTRO dataset.
    """

    def __init__(
        self,
        dataset_path: Path = DATASET_PATH,
        processed_dir: Path = PROCESSED_DATA_DIR,
        splits_dir: Path = SPLITS_DIR,
        sequence_length: int = SEQUENCE_LENGTH,
        chunk_size: int = CHUNK_SIZE,
        min_token_frequency: int = MIN_TOKEN_FREQUENCY,
        max_workers: Optional[int] = None,
    ):
        self.dataset_path = Path(dataset_path).resolve()
        self.processed_dir = Path(processed_dir).resolve()
        self.splits_dir = Path(splits_dir).resolve()
        self.training_data_dir = self.processed_dir / "training_data"
        self.token_cache_dir = self.processed_dir / "token_cache"
        self.vocabulary_file = self.processed_dir / "vocabulary.json"
        self.metadata_file = self.processed_dir / "metadata.json"

        self.sequence_length = sequence_length
        self.chunk_size = chunk_size
        self.min_token_frequency = min_token_frequency
        self.max_workers = max_workers or max(1, (os.cpu_count() or 4) - 2)

        # Ensure directories exist
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.training_data_dir.mkdir(parents=True, exist_ok=True)
        self.token_cache_dir.mkdir(parents=True, exist_ok=True)
        self.splits_dir.mkdir(parents=True, exist_ok=True)

    def load_or_create_splits(self) -> dict[str, set[str]]:
        """Load split definitions (relative paths), generating them if missing."""
        train_csv = self.splits_dir / "train.csv"
        val_csv = self.splits_dir / "validation.csv"
        test_csv = self.splits_dir / "test.csv"

        if not (train_csv.exists() and val_csv.exists() and test_csv.exists()):
            print("[*] Split files missing. Generating reproducible splits...")
            create_splits(splits_dir=self.splits_dir)

        import pandas as pd
        splits = {
            "train": set(pd.read_csv(train_csv)["relative_path"].astype(str)),
            "validation": set(pd.read_csv(val_csv)["relative_path"].astype(str)),
            "test": set(pd.read_csv(test_csv)["relative_path"].astype(str)),
        }
        print(f"[+] Loaded split files: Train={len(splits['train'])}, Val={len(splits['validation'])}, Test={len(splits['test'])}")
        return splits

    def discover_midi_files(self) -> list[Path]:
        """Recursively scan DATASET_PATH for all .midi / .mid files."""
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset path does not exist: {self.dataset_path}")

        files = sorted(
            p for p in self.dataset_path.rglob("*")
            if p.is_file() and p.suffix.lower() in (".midi", ".mid")
        )
        return files

    def extract_tokens_parallel(self, midi_files: list[Path], force: bool = False) -> tuple[list[dict], list[dict]]:
        """
        Extract tokens from all MIDI files using parallel worker processes.
        Returns: (successful_results, failed_results)
        """
        tasks = []
        for mf in midi_files:
            rel_path = mf.relative_to(self.dataset_path).as_posix()
            safe_name = rel_path.replace("/", "_").replace("\\", "_") + ".json"
            cache_path = self.token_cache_dir / safe_name
            tasks.append((str(mf), str(cache_path), rel_path, force))

        successful = []
        failed = []

        print(f"[*] Extracting tokens from {len(midi_files)} MIDI files using {self.max_workers} workers...")
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(_process_single_midi_worker, t) for t in tasks]
            for future in tqdm(as_completed(futures), total=len(futures), desc="Tokenizing MIDI"):
                res = future.result()
                if res["status"] in ("PROCESSED", "CACHED"):
                    successful.append(res)
                else:
                    failed.append(res)

        # Sort successful results deterministically by relative path
        successful.sort(key=lambda x: x["rel_path"])
        return successful, failed

    def build_vocabulary(self, train_results: list[dict]) -> tuple[Vocabulary, dict[str, int]]:
        """
        Build a pruned vocabulary strictly from the training split token streams.
        Tokens appearing fewer than min_token_frequency times are mapped to <UNK>.
        Prevents data leakage from validation and test sets.
        """
        print(f"[*] Building vocabulary across {len(train_results)} training token streams...")
        token_counter = Counter()

        for item in tqdm(train_results, desc="Counting training tokens"):
            cache_file = Path(item["cache_path"])
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    tokens = json.load(f)
                token_counter.update(tokens)
            except Exception as e:
                print(f"[!] Warning reading cache {cache_file}: {e}")

        total_unique_tokens = len(token_counter)
        total_token_occurrences = sum(token_counter.values())

        # Construct vocabulary
        vocab = Vocabulary()
        for token, count in sorted(token_counter.items(), key=lambda x: (-x[1], x[0])):
            if count >= self.min_token_frequency:
                vocab.add_token(token)

        # Save vocabulary to JSON
        vocab.save(self.vocabulary_file)
        print(f"[+] Vocabulary built: {len(vocab)} unique tokens (from {total_unique_tokens} raw training types).")
        print(f"[+] Saved vocabulary to: {self.vocabulary_file}")

        stats = {
            "total_token_occurrences": total_token_occurrences,
            "raw_unique_tokens": total_unique_tokens,
            "pruned_vocab_size": len(vocab),
            "min_token_frequency": self.min_token_frequency,
        }
        return vocab, stats

    def _generate_split_chunks(
        self,
        split_results: list[dict],
        vocab: Vocabulary,
        output_dir: Path,
        split_name: str,
        force: bool = False,
    ) -> tuple[int, int]:
        """Form sliding window sequences for a single split and save chunked .npz files."""
        output_dir.mkdir(parents=True, exist_ok=True)
        if force:
            for old_chunk in output_dir.glob("chunk_*.npz"):
                old_chunk.unlink()

        x_buffer: list[list[int]] = []
        y_buffer: list[int] = []
        chunk_index = 1
        total_sequences = 0

        def flush_chunk():
            nonlocal chunk_index, x_buffer, y_buffer
            if not x_buffer:
                return
            x_arr = np.array(x_buffer, dtype=np.uint16)
            y_arr = np.array(y_buffer, dtype=np.uint16)
            chunk_file = output_dir / f"chunk_{chunk_index:04d}.npz"
            np.savez_compressed(chunk_file, X=x_arr, y=y_arr)
            chunk_index += 1
            x_buffer.clear()
            y_buffer.clear()

        for item in tqdm(split_results, desc=f"Creating {split_name} sequences"):
            cache_file = Path(item["cache_path"])
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    tokens = json.load(f)
            except Exception:
                continue

            if len(tokens) <= self.sequence_length:
                continue

            encoded_ids = vocab.encode(tokens)
            n_samples = len(encoded_ids) - self.sequence_length

            for i in range(n_samples):
                x_buffer.append(encoded_ids[i : i + self.sequence_length])
                y_buffer.append(encoded_ids[i + self.sequence_length])
                total_sequences += 1

                if len(x_buffer) >= self.chunk_size:
                    flush_chunk()

        if x_buffer:
            flush_chunk()

        total_chunks = chunk_index - 1
        print(f"[+] [{split_name.upper()}] Generated {total_sequences:,} sequences across {total_chunks} chunks.")
        return total_sequences, total_chunks

    def create_and_save_chunks(
        self,
        successful_results: list[dict],
        splits: dict[str, set[str]],
        vocab: Vocabulary,
        force: bool = False,
    ) -> dict[str, dict]:
        """
        Partition token streams by split (train, validation, test) and create isolated chunks.
        """
        print(f"[*] Generating split-isolated training sequences (seq_len={self.sequence_length}, chunk_size={self.chunk_size})...")

        # Partition results by split
        partitioned: dict[str, list[dict]] = {"train": [], "validation": [], "test": []}
        for res in successful_results:
            rel = res["rel_path"]
            # Match against split relative path or filename
            if rel in splits["train"]:
                partitioned["train"].append(res)
            elif rel in splits["validation"]:
                partitioned["validation"].append(res)
            elif rel in splits["test"]:
                partitioned["test"].append(res)
            else:
                # Fallback: check basename matching
                base = Path(rel).name
                matched = False
                for split_name in ("train", "validation", "test"):
                    if any(Path(p).name == base for p in splits[split_name]):
                        partitioned[split_name].append(res)
                        matched = True
                        break
                if not matched:
                    partitioned["train"].append(res)

        split_stats = {}
        for split_name in ("train", "validation", "test"):
            split_items = partitioned[split_name]
            split_dir = self.training_data_dir / split_name
            seqs, chunks = self._generate_split_chunks(
                split_items, vocab, split_dir, split_name, force=force
            )
            split_stats[split_name] = {
                "num_files": len(split_items),
                "num_sequences": seqs,
                "num_chunks": chunks,
                "output_dir": str(split_dir),
            }

        total_seqs = sum(s["num_sequences"] for s in split_stats.values())
        total_chunks = sum(s["num_chunks"] for s in split_stats.values())
        split_stats["total_sequences"] = total_seqs
        split_stats["total_chunks"] = total_chunks
        return split_stats

    def calculate_storage_size(self) -> tuple[int, float]:
        """Compute total storage size of processed data directory in bytes and megabytes."""
        total_bytes = sum(f.stat().st_size for f in self.processed_dir.rglob("*") if f.is_file())
        total_mb = round(total_bytes / (1024 * 1024), 2)
        return total_bytes, total_mb

    def save_metadata_report(
        self,
        total_discovered: int,
        successful_results: list[dict],
        failed_results: list[dict],
        vocab_stats: dict,
        split_stats: dict,
        elapsed_seconds: float,
    ) -> dict:
        """Write metadata.json with comprehensive summary metrics."""
        storage_bytes, storage_mb = self.calculate_storage_size()

        metadata = {
            "dataset_name": "MAESTRO v3.0.0 (MIDI)",
            "dataset_path": str(self.dataset_path),
            "processed_at": datetime.now().isoformat(),
            "pipeline_version": "1.1.0",
            "hyperparameters": {
                "sequence_length": self.sequence_length,
                "chunk_size": self.chunk_size,
                "min_token_frequency": self.min_token_frequency,
                "random_seed": RANDOM_SEED,
            },
            "file_metrics": {
                "total_files_discovered": total_discovered,
                "valid_files_processed": len(successful_results),
                "invalid_or_failed_files": len(failed_results),
                "failed_file_details": failed_results,
            },
            "token_metrics": {
                "total_musical_tokens": vocab_stats["total_token_occurrences"],
                "raw_unique_tokens": vocab_stats["raw_unique_tokens"],
                "vocabulary_size": vocab_stats["pruned_vocab_size"],
            },
            "split_metrics": split_stats,
            "dataset_metrics": {
                "total_training_sequences": split_stats["total_sequences"],
                "total_chunks": split_stats["total_chunks"],
                "storage_size_bytes": storage_bytes,
                "storage_size_mb": storage_mb,
                "elapsed_seconds": round(elapsed_seconds, 2),
            },
            "paths": {
                "processed_dir": str(self.processed_dir),
                "splits_dir": str(self.splits_dir),
                "vocabulary_file": str(self.vocabulary_file),
                "metadata_file": str(self.metadata_file),
                "training_data_dir": str(self.training_data_dir),
            },
        }

        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print(f"[+] Preprocessing metadata written to: {self.metadata_file}")
        return metadata

    def run(self, force: bool = False) -> dict:
        """Execute full preprocessing pipeline with split awareness."""
        start_time = time.time()
        print("=" * 65)
        print("    AI MUSIC STUDIO - COMPLETE MAESTRO PREPROCESSING PIPELINE")
        print("=" * 65)
        print(f"Dataset Path        : {self.dataset_path}")
        print(f"Target Processed Dir: {self.processed_dir}")
        print(f"Splits Directory   : {self.splits_dir}")
        print(f"Sequence Length     : {self.sequence_length}")
        print(f"Chunk Size          : {self.chunk_size:,}")
        print(f"Min Token Frequency : {self.min_token_frequency}")
        print("=" * 65)

        # 1. Discover MIDI files
        midi_files = self.discover_midi_files()
        print(f"[+] Found {len(midi_files)} MIDI files in dataset directory.")

        if not midi_files:
            raise RuntimeError(f"No MIDI files found at {self.dataset_path}")

        # 2. Load or generate splits
        splits = self.load_or_create_splits()

        # 3. Extract tokens in parallel with disk caching
        successful, failed = self.extract_tokens_parallel(midi_files, force=force)

        # 4. Filter training results for building vocabulary
        train_results = [
            r for r in successful
            if r["rel_path"] in splits["train"] or any(Path(p).name == Path(r["rel_path"]).name for p in splits["train"])
        ]
        print(f"[+] Filtered {len(train_results)} training files for vocabulary construction.")

        # 5. Build vocabulary on training split
        vocab, vocab_stats = self.build_vocabulary(train_results)

        # 6. Create sliding-window sequence chunks partitioned by split
        split_stats = self.create_and_save_chunks(successful, splits, vocab, force=force)

        # 7. Metadata report
        elapsed = time.time() - start_time
        metadata = self.save_metadata_report(
            total_discovered=len(midi_files),
            successful_results=successful,
            failed_results=failed,
            vocab_stats=vocab_stats,
            split_stats=split_stats,
            elapsed_seconds=elapsed,
        )

        storage_bytes, storage_mb = self.calculate_storage_size()

        print("\n" + "=" * 65)
        print("          PREPROCESSING COMPLETED SUCCESSFULLY")
        print("=" * 65)
        print(f"Total MIDI Files Discovered : {len(midi_files):,}")
        print(f"Files Processed (Valid)    : {len(successful):,}")
        print(f"Invalid / Failed Files      : {len(failed):,}")
        print(f"Vocabulary Size (Train)     : {vocab_stats['pruned_vocab_size']:,}")
        print(f"Sequence Length             : {self.sequence_length}")
        print(f"Train Sequences             : {split_stats['train']['num_sequences']:,} ({split_stats['train']['num_chunks']} chunks)")
        print(f"Val Sequences               : {split_stats['validation']['num_sequences']:,} ({split_stats['validation']['num_chunks']} chunks)")
        print(f"Test Sequences              : {split_stats['test']['num_sequences']:,} ({split_stats['test']['num_chunks']} chunks)")
        print(f"Total Sequences (X, y)      : {split_stats['total_sequences']:,} ({split_stats['total_chunks']} chunks)")
        print(f"Total Processed Storage     : {storage_mb:.2f} MB")
        print(f"Total Execution Time        : {elapsed:.2f}s ({elapsed/60:.2f}m)")
        print("=" * 65)

        return metadata


def parse_args():
    parser = argparse.ArgumentParser(description="Preprocess the complete MAESTRO dataset for AI Music Studio.")
    parser.add_argument("--dataset-path", type=str, default=str(DATASET_PATH), help="Path to MAESTRO dataset folder")
    parser.add_argument("--processed-dir", type=str, default=str(PROCESSED_DATA_DIR), help="Output directory for processed data")
    parser.add_argument("--sequence-length", type=int, default=SEQUENCE_LENGTH, help="Sliding window sequence length")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, help="Samples per training data chunk (.npz)")
    parser.add_argument("--min-frequency", type=int, default=MIN_TOKEN_FREQUENCY, help="Minimum token frequency in vocabulary")
    parser.add_argument("--workers", type=int, default=None, help="Number of worker processes (default: cpu_count - 2)")
    parser.add_argument("--force", action="store_true", help="Force reprocessing even if cached files exist")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    preprocessor = MaestroPreprocessor(
        dataset_path=Path(args.dataset_path),
        processed_dir=Path(args.processed_dir),
        sequence_length=args.sequence_length,
        chunk_size=args.chunk_size,
        min_token_frequency=args.min_frequency,
        max_workers=args.workers,
    )
    preprocessor.run(force=args.force)
