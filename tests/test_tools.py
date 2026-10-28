"""Filesystem discovery tests for scrcpy tools."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.tools import find_all_executables, find_executable, is_file


class ToolDiscoveryTests(unittest.TestCase):
    def test_finds_scrcpy_in_nested_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested = root / "scrcpy-win64-v3.1"
            nested.mkdir()
            (nested / "scrcpy.exe").write_bytes(b"MZ")
            (nested / "adb.exe").write_bytes(b"MZ")
            other = root / "scrcpy-win64-v2.4"
            other.mkdir()
            (other / "scrcpy.exe").write_bytes(b"MZ")

            executable, count, truncated = find_executable(root, "scrcpy.exe")
            self.assertIsNotNone(executable)
            self.assertEqual(count, 2)
            self.assertFalse(truncated)
            self.assertTrue(is_file(executable))
            all_files, _ = find_all_executables(root, "scrcpy.exe")
            self.assertEqual(len(all_files), 2)

    def test_missing_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            executable, count, _ = find_executable(temporary, "scrcpy.exe")
            self.assertIsNone(executable)
            self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
