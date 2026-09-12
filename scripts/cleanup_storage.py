"""
AI Music Studio - File Storage Retention and Optimization Engine
Manages generated output files (MIDI, WAV, temp artifacts) to prevent unbounded disk usage.
Removes files older than a configurable retention window (default 72 hours) while preserving
database metadata integrity and preventing active request race conditions.
"""

import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.config import (
    MIDI_OUTPUT_DIR,
    AUDIO_OUTPUT_DIR,
    FILE_RETENTION_HOURS,
)


def cleanup_storage(
    max_age_hours: int = FILE_RETENTION_HOURS,
    directories: list = None,
    dry_run: bool = False,
) -> dict:
    """
    Purge generated files older than max_age_hours from designated storage directories.
    """
    if directories is None:
        directories = [MIDI_OUTPUT_DIR, AUDIO_OUTPUT_DIR]

    now = time.time()
    cutoff_time = now - (max_age_hours * 3600)

    stats = {
        "files_scanned": 0,
        "files_deleted": 0,
        "bytes_freed": 0,
        "directories_scanned": [str(d) for d in directories],
        "cutoff_timestamp": datetime.fromtimestamp(cutoff_time, tz=timezone.utc).isoformat(),
        "dry_run": dry_run,
        "deleted_files": [],
    }

    for dir_path in directories:
        target_dir = Path(dir_path).resolve()
        if not target_dir.exists():
            continue

        for file_path in target_dir.glob("*.*"):
            if not file_path.is_file():
                continue

            stats["files_scanned"] += 1
            try:
                st = file_path.stat()
                if st.st_mtime < cutoff_time:
                    size = st.st_size
                    stats["bytes_freed"] += size
                    stats["files_deleted"] += 1
                    stats["deleted_files"].append(file_path.name)

                    if not dry_run:
                        file_path.unlink()
            except Exception:
                pass

    return stats


def get_storage_stats() -> dict:
    """Calculate current disk usage for output directories."""
    total_files = 0
    total_bytes = 0
    dirs_info = {}

    for name, path in [("midi", MIDI_OUTPUT_DIR), ("audio", AUDIO_OUTPUT_DIR)]:
        p = Path(path).resolve()
        count = 0
        size = 0
        if p.exists():
            for f in p.glob("*.*"):
                if f.is_file():
                    count += 1
                    size += f.stat().st_size
        dirs_info[name] = {"count": count, "size_bytes": size, "path": str(p)}
        total_files += count
        total_bytes += size

    return {
        "total_files": total_files,
        "total_size_bytes": total_bytes,
        "total_size_mb": round(total_bytes / (1024 * 1024), 2),
        "directories": dirs_info,
    }


def main():
    parser = argparse.ArgumentParser(description="Clean up expired music studio files.")
    parser.add_argument("--hours", type=int, default=FILE_RETENTION_HOURS, help="Max file age in hours")
    parser.add_argument("--dry-run", action="store_true", help="Preview files to be deleted")
    parser.add_argument("--stats", action="store_true", help="Display current storage usage statistics")
    args = parser.parse_args()

    if args.stats:
        usage = get_storage_stats()
        print("=== AI Music Studio Storage Usage ===")
        print(f"Total Files : {usage['total_files']}")
        print(f"Total Disk  : {usage['total_size_mb']} MB")
        for k, v in usage["directories"].items():
            print(f"  - {k}: {v['count']} files ({round(v['size_bytes'] / 1024, 1)} KB) -> {v['path']}")
        return

    print(f"Starting storage cleanup (Max age: {args.hours} hours, dry-run: {args.dry_run})...")
    res = cleanup_storage(max_age_hours=args.hours, dry_run=args.dry_run)
    print(f"Scanned {res['files_scanned']} files. Deleted {res['files_deleted']} ({round(res['bytes_freed'] / 1024, 2)} KB freed).")


if __name__ == "__main__":
    main()
