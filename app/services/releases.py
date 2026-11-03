"""Official scrcpy release discovery and safe Windows package installation."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import shutil
import stat
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable

from ..errors import AppError
from .tools import find_executable

RELEASES_API = "https://api.github.com/repos/Genymobile/scrcpy/releases?per_page=50"
RELEASE_PREFIX = "https://github.com/Genymobile/scrcpy/releases/download/"
ASSET_PREFIX = "scrcpy-win64-"
MAX_DOWNLOAD_BYTES = 220 * 1024 * 1024
MAX_EXTRACT_BYTES = 600 * 1024 * 1024
SAFE_ASSET = re.compile(r"scrcpy-win64-[A-Za-z0-9._-]+\.zip", re.IGNORECASE)


def parse_releases(payload: Any) -> list[dict[str, Any]]:
    """Extract stable Windows packages from a GitHub releases response."""
    if not isinstance(payload, list):
        raise AppError("GitHub 返回的版本列表格式不正确", code="RELEASE_BAD_FORMAT")
    releases: list[dict[str, Any]] = []
    for raw in payload:
        if not isinstance(raw, dict) or raw.get("draft") or raw.get("prerelease"):
            continue
        tag = str(raw.get("tag_name") or "").strip()
        if not tag:
            continue
        assets = raw.get("assets") or []
        asset = next(
            (
                item
                for item in assets
                if isinstance(item, dict)
                and str(item.get("name") or "").lower().startswith(ASSET_PREFIX)
                and str(item.get("name") or "").lower().endswith(".zip")
            ),
            None,
        )
        if not asset:
            continue
        name = str(asset.get("name") or "")
        if not SAFE_ASSET.fullmatch(name):
            continue
        url = str(asset.get("browser_download_url") or "")
        if not url.startswith(RELEASE_PREFIX):
            continue
        releases.append(
            {
                "tag": tag,
                "name": str(raw.get("name") or tag),
                "published": str(raw.get("published_at") or ""),
                "asset_name": name,
                "asset_size": int(asset.get("size") or 0),
                "download_url": url,
                "digest": str(asset.get("digest") or ""),
                "html_url": str(raw.get("html_url") or ""),
            }
        )
    return releases


def fetch_releases() -> list[dict[str, Any]]:
    request = urllib.request.Request(
        RELEASES_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "ScrcpyDock-ReleaseDownloader",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    payload: Any = None
    last_error: Exception | None = None
    # GitHub is occasionally flaky from mainland networks; a short retry helps.
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except (
            urllib.error.URLError,
            http.client.HTTPException,
            TimeoutError,
            OSError,
        ) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.8 * (attempt + 1))
        except ValueError as exc:
            raise AppError("GitHub 返回了无效的版本列表", code="RELEASES_FORMAT") from exc
    if payload is None:
        raise AppError(
            "无法获取 scrcpy 官方版本列表",
            code="RELEASES_NETWORK",
            hint="请检查网络，或稍后重试；也可以继续手动添加本地版本。",
        ) from last_error
    return parse_releases(payload)


def _download(
    release: dict[str, Any],
    target: Path,
    progress: Callable[[int, int], None] | None,
) -> None:
    url = str(release["download_url"])
    if not url.startswith(RELEASE_PREFIX):
        raise AppError("下载地址不是官方 scrcpy 资源", code="UNSAFE_DOWNLOAD")
    expected = int(release.get("asset_size") or 0)
    if expected > MAX_DOWNLOAD_BYTES:
        raise AppError("下载包超过允许大小", code="RELEASE_TOO_LARGE")

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ScrcpyDock-ReleaseDownloader",
            "Accept": "application/octet-stream",
        },
    )
    digest = hashlib.sha256()
    written = 0
    try:
        with urllib.request.urlopen(request, timeout=45) as response, target.open("wb") as handle:
            total = int(response.headers.get("Content-Length") or expected or 0)
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_DOWNLOAD_BYTES:
                    raise AppError("下载包超过允许大小", code="RELEASE_TOO_LARGE")
                digest.update(chunk)
                handle.write(chunk)
                if progress:
                    progress(written, total)
    except AppError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AppError(
            "下载 scrcpy 版本失败",
            code="DOWNLOAD_FAILED",
            hint="请检查网络后重试。",
        ) from exc

    if expected and written != expected:
        raise AppError(
            "下载文件大小不完整",
            code="DOWNLOAD_INCOMPLETE",
            hint=f"期望 {expected} 字节，实际 {written} 字节。",
        )
    expected_digest = str(release.get("digest") or "")
    if expected_digest.startswith("sha256:"):
        actual = digest.hexdigest()
        if actual.casefold() != expected_digest[7:].casefold():
            raise AppError("下载文件校验失败", code="DOWNLOAD_CHECKSUM")


def _extract(zip_path: Path, destination: Path) -> None:
    root = destination.resolve()
    try:
        with zipfile.ZipFile(zip_path) as archive:
            total = 0
            for info in archive.infolist():
                name = info.filename.replace("\\", "/")
                path = Path(name)
                if path.is_absolute() or any(part == ".." for part in path.parts):
                    raise AppError("压缩包包含不安全路径", code="UNSAFE_ARCHIVE")
                target = (root / path).resolve()
                if target != root and root not in target.parents:
                    raise AppError("压缩包包含不安全路径", code="UNSAFE_ARCHIVE")
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    raise AppError("压缩包包含符号链接", code="UNSAFE_ARCHIVE")
                total += int(info.file_size)
                if total > MAX_EXTRACT_BYTES:
                    raise AppError("解压后的文件超过允许大小", code="ARCHIVE_TOO_LARGE")
            archive.extractall(root)
    except zipfile.BadZipFile as exc:
        raise AppError("下载的 scrcpy 压缩包无效", code="INVALID_ARCHIVE") from exc


def download_release(
    release: dict[str, Any],
    destination_root: str | Path,
    progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Download, validate and extract one official scrcpy Windows release.

    Returns the directory containing scrcpy.exe (or its extracted root).
    Callers should run this off the Qt main thread.
    """
    root = Path(destination_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    asset_name = str(release["asset_name"])
    if not SAFE_ASSET.fullmatch(asset_name):
        raise AppError("scrcpy 资源文件名不安全", code="UNSAFE_ASSET")
    stem = Path(asset_name).stem
    final_dir = root / stem
    temporary_zip = root / f".{stem}.part"
    temporary_dir = root / f".{stem}.extracting"

    if final_dir.exists():
        raise AppError(
            "该 scrcpy 版本目录已经存在",
            code="TOOL_DIRECTORY_EXISTS",
            hint=str(final_dir),
        )
    for path in (temporary_zip, temporary_dir):
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)

    try:
        _download(release, temporary_zip, progress)
        _extract(temporary_zip, temporary_dir)
        scrcpy, _count, _truncated = find_executable(temporary_dir, "scrcpy.exe")
        if not scrcpy:
            raise AppError(
                "下载包中没有找到 scrcpy.exe",
                code="SCRCPY_NOT_FOUND",
            )
        # Most official zips contain one top-level folder; flatten that case.
        members = list(temporary_dir.iterdir())
        source = temporary_dir
        if len(members) == 1 and members[0].is_dir():
            source = members[0]
        os.replace(source, final_dir)
        return final_dir
    except AppError:
        raise
    except OSError as exc:
        raise AppError(
            "解压或保存 scrcpy 版本失败",
            code="INSTALL_FAILED",
            hint=str(exc),
        ) from exc
    finally:
        try:
            temporary_zip.unlink(missing_ok=True)
        except OSError:
            pass
        if temporary_dir.exists():
            shutil.rmtree(temporary_dir, ignore_errors=True)
