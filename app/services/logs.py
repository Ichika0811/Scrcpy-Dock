"""Terminal log retention cleanup."""

from __future__ import annotations

import time
from pathlib import Path


def cleanup_logs(
    logs_dir: Path,
    *,
    retention_days: int = 14,
    max_total_mb: int = 100,
    keep: set[Path] | None = None,
) -> tuple[int, int]:
    """Delete old/oversized terminal logs and return (count, bytes_removed)."""
    directory = Path(logs_dir)
    if not directory.is_dir():
        return 0, 0
    keep_paths = {path.resolve() for path in (keep or set())}
    logs: list[Path] = []
    for path in directory.glob("*_terminal_*.log"):
        try:
            resolved = path.resolve()
            if resolved not in keep_paths and path.is_file():
                logs.append(path)
        except OSError:
            continue

    now = time.time()
    cutoff = now - max(1, int(retention_days)) * 86400
    removed_count = 0
    removed_bytes = 0
    remaining: list[tuple[float, int, Path]] = []

    for path in logs:
        try:
            stat = path.stat()
        except OSError:
            continue
        if stat.st_mtime < cutoff:
            try:
                path.unlink()
                removed_count += 1
                removed_bytes += stat.st_size
            except OSError:
                pass
        else:
            remaining.append((stat.st_mtime, stat.st_size, path))

    limit = max(1, int(max_total_mb)) * 1024 * 1024
    total = sum(size for _mtime, size, _path in remaining)
    for _mtime, size, path in sorted(remaining):
        if total <= limit:
            break
        try:
            path.unlink()
            total -= size
            removed_count += 1
            removed_bytes += size
        except OSError:
            continue
    return removed_count, removed_bytes
