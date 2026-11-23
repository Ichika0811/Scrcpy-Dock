"""Log retention cleanup tests."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

from app.services.logs import cleanup_logs


class LogCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.logs = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _make(self, name: str, size: int, age_days: int = 0) -> Path:
        path = self.logs / name
        path.write_bytes(b"x" * size)
        stamp = time.time() - age_days * 86400
        os.utime(path, (stamp, stamp))
        return path

    def test_removes_expired_logs(self) -> None:
        old = self._make("20250101_terminal_old.log", 128, age_days=30)
        fresh = self._make("20250102_terminal_new.log", 128, age_days=1)
        removed, _size = cleanup_logs(self.logs, retention_days=14)
        self.assertEqual(removed, 1)
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())

    def test_enforces_total_size_oldest_first(self) -> None:
        old = self._make("20250101_terminal_old.log", 600 * 1024, age_days=2)
        new = self._make("20250102_terminal_new.log", 600 * 1024, age_days=1)
        removed, _size = cleanup_logs(self.logs, retention_days=14, max_total_mb=1)
        self.assertEqual(removed, 1)
        self.assertFalse(old.exists())
        self.assertTrue(new.exists())


if __name__ == "__main__":
    unittest.main()
