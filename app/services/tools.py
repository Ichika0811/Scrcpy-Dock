"""Locating scrcpy builds and reading their versions."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from ..errors import AppError
from ..parsers import normalize_version

IS_WINDOWS = os.name == "nt"
CREATE_NO_WINDOW = 0x08000000 if IS_WINDOWS else 0

_SKIP_DIRS = {
    "node_modules",
    ".git",
    ".svn",
    "$recycle.bin",
    "system volume information",
    "windows",
    "system32",
    "winsxs",
}


def is_file(path: str | Path | None) -> bool:
    if not path:
        return False
    try:
        return Path(path).is_file()
    except OSError:
        return False


def _subprocess_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {"creationflags": CREATE_NO_WINDOW} if IS_WINDOWS else {}
    return kwargs


def run_capture(
    args: list[str],
    *,
    timeout: float = 8.0,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        **_subprocess_kwargs(),
    )


def _walk_executables(
    root: Path,
    filename: str,
    *,
    max_depth: int = 3,
    max_entries: int = 6000,
) -> tuple[list[Path], bool]:
    found: list[Path] = []
    queue: list[tuple[Path, int]] = [(root, 0)]
    visited = 0
    truncated = False
    target = filename.casefold()
    while queue:
        directory, depth = queue.pop(0)
        try:
            entries = list(os.scandir(directory))
        except OSError:
            continue
        for entry in entries:
            visited += 1
            if visited > max_entries:
                truncated = True
                break
            try:
                path = Path(entry.path)
                if entry.is_file(follow_symlinks=False) and entry.name.casefold() == target:
                    found.append(path)
                    continue
                if (
                    entry.is_dir(follow_symlinks=False)
                    and depth < max_depth
                    and entry.name.casefold() not in _SKIP_DIRS
                    and not entry.name.startswith(".")
                ):
                    queue.append((path, depth + 1))
            except OSError:
                continue
        if truncated:
            break
    found = sorted(set(found), key=lambda item: (len(item.parts), str(item).casefold()))
    return found, truncated


def find_executable(
    root: str | Path,
    filename: str,
    *,
    max_depth: int = 3,
    max_entries: int = 6000,
) -> tuple[Path | None, int, bool]:
    found, truncated = _walk_executables(
        Path(root), filename, max_depth=max_depth, max_entries=max_entries
    )
    return (found[0] if found else None), len(found), truncated


def find_all_executables(
    root: str | Path,
    filename: str,
    *,
    max_depth: int = 3,
    max_entries: int = 12000,
) -> tuple[list[Path], bool]:
    return _walk_executables(
        Path(root), filename, max_depth=max_depth, max_entries=max_entries
    )


def read_scrcpy_version(scrcpy_path: str | Path) -> dict[str, str]:
    path = Path(scrcpy_path)
    try:
        result = run_capture([str(path), "--version"], timeout=5.0, cwd=path.parent)
        raw = "\n".join(
            part for part in [result.stdout or "", result.stderr or ""] if part
        ).strip()
        return {
            "version": normalize_version(raw),
            "raw": "\n".join(raw.splitlines()[:4])[:2000],
            "warning": "",
        }
    except subprocess.TimeoutExpired:
        return {
            "version": "未知版本",
            "raw": "",
            "warning": "读取版本超时，请手动修改版本标签",
        }
    except OSError as exc:
        return {
            "version": "未知版本",
            "raw": "",
            "warning": f"无法读取版本信息：{exc}",
        }


def inspect_tool_folder(selected_path: str | Path) -> dict[str, Any]:
    selected = Path(str(selected_path).strip().strip('"')).expanduser()
    if not selected.exists():
        raise AppError("选择的文件夹不存在", code="PATH_NOT_FOUND")
    if selected.is_file():
        selected = selected.parent
    if not selected.is_dir():
        raise AppError("选择的路径不是文件夹", code="NOT_A_DIRECTORY")

    scrcpy, match_count, truncated = find_executable(
        selected, "scrcpy.exe", max_depth=3, max_entries=6000
    )
    if not scrcpy:
        raise AppError(
            "这个文件夹里没有找到 scrcpy.exe",
            code="SCRCPY_NOT_FOUND",
            hint="请选择完整解压后的 scrcpy 目录。",
        )
    folder = scrcpy.parent
    adb, _, _ = find_executable(folder, "adb.exe", max_depth=2, max_entries=1200)
    version_info = read_scrcpy_version(scrcpy)
    warnings: list[str] = []
    if version_info["warning"]:
        warnings.append(version_info["warning"])
    if match_count > 1:
        warnings.append(f"发现 {match_count} 个 scrcpy.exe，已选择层级最浅的一个")
    if truncated:
        warnings.append("文件夹较大，扫描已提前停止")
    if not adb:
        warnings.append("未找到 adb.exe，将使用全局 ADB")

    return {
        "folder": str(folder),
        "scrcpy_path": str(scrcpy),
        "adb_path": str(adb) if adb else "",
        "version": version_info["version"],
        "detected_version": version_info["version"],
        "version_raw": version_info["raw"],
        "warnings": warnings,
    }


def inspect_tool_parent(parent_path: str | Path, *, limit: int = 24) -> dict[str, Any]:
    root = Path(str(parent_path).strip().strip('"')).expanduser()
    if not root.is_dir():
        raise AppError("请选择一个包含 scrcpy 版本的父文件夹", code="NOT_A_DIRECTORY")
    executables, truncated = find_all_executables(root, "scrcpy.exe")
    folders: list[Path] = []
    seen: set[str] = set()
    for executable in executables:
        key = str(executable.parent).casefold()
        if key in seen:
            continue
        seen.add(key)
        folders.append(executable.parent)

    tools: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for folder in folders[:limit]:
        try:
            tools.append(inspect_tool_folder(folder))
        except AppError as exc:
            errors.append({"folder": str(folder), "message": exc.message})
        except Exception as exc:  # defensive: one bad folder should not abort batch
            errors.append({"folder": str(folder), "message": str(exc)})

    return {
        "root": str(root),
        "found": len(folders),
        "truncated": truncated or len(folders) > limit,
        "tools": tools,
        "errors": errors,
    }


def rescan_tool(tool: dict[str, Any]) -> dict[str, Any]:
    scrcpy_path = Path(tool["scrcpy_path"])
    if not scrcpy_path.is_file():
        raise AppError(
            "scrcpy.exe 已不存在，请重新添加版本",
            code="TOOL_MISSING",
            hint=str(scrcpy_path),
        )
    version = read_scrcpy_version(scrcpy_path)
    adb, _, _ = find_executable(scrcpy_path.parent, "adb.exe", max_depth=2, max_entries=1200)
    return {
        "detected_version": version["version"],
        "version_raw": version["raw"],
        "adb_path": str(adb) if adb else "",
    }
