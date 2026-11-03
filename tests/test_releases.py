"""Official scrcpy release parsing and archive safety tests."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from app.errors import AppError
from app.services.releases import _extract, parse_releases


class ReleaseTests(unittest.TestCase):
    def test_parse_stable_windows_assets(self) -> None:
        payload = [
            {
                "tag_name": "v5.0.1",
                "name": "scrcpy v5.0.1",
                "draft": False,
                "prerelease": False,
                "published_at": "2026-10-08T06:44:27Z",
                "html_url": "https://github.com/Genymobile/scrcpy/releases/tag/v5.0.1",
                "assets": [
                    {
                        "name": "scrcpy-win64-v5.0.1.zip",
                        "size": 11264000,
                        "browser_download_url": (
                            "https://github.com/Genymobile/scrcpy/releases/download/"
                            "v5.0.1/scrcpy-win64-v5.0.1.zip"
                        ),
                        "digest": "sha256:" + "a" * 64,
                    }
                ],
            },
            {
                "tag_name": "v5.0-beta",
                "prerelease": True,
                "assets": [],
            },
            {
                "tag_name": "v4.9",
                "draft": True,
                "assets": [],
            },
            {
                "tag_name": "v4.8",
                "prerelease": False,
                "assets": [
                    {
                        "name": "scrcpy-win64-v4.8.zip",
                        "size": 100,
                        "browser_download_url": "https://example.com/scrcpy-win64-v4.8.zip",
                    }
                ],
            },
        ]
        releases = parse_releases(payload)
        self.assertEqual(len(releases), 1)
        self.assertEqual(releases[0]["tag"], "v5.0.1")
        self.assertEqual(releases[0]["asset_name"], "scrcpy-win64-v5.0.1.zip")

    def test_extract_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive_path = root / "bad.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../outside.txt", "bad")
            target = root / "extract"
            target.mkdir()
            with self.assertRaises(AppError):
                _extract(archive_path, target)

    def test_extract_normal_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive_path = root / "ok.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("scrcpy-win64-demo/scrcpy.exe", "demo")
            target = root / "extract"
            _extract(archive_path, target)
            self.assertTrue((target / "scrcpy-win64-demo" / "scrcpy.exe").is_file())


if __name__ == "__main__":
    unittest.main()
