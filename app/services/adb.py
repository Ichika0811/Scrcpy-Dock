"""ADB discovery and device listing."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..config import ConfigStore
from ..errors import AppError
from ..parsers import parse_adb_devices, parse_mdns_services
from .tools import run_capture


class AdbService:
    def __init__(self, config: ConfigStore) -> None:
        self.config = config

    def get_adb_info(self, tool_id: str | None = None) -> dict[str, Any]:
        settings = self.config.settings
        configured = str(settings.get("adb_path") or "").strip()
        if configured:
            if Path(configured).is_file():
                return {
                    "path": configured,
                    "source": "custom",
                    "source_label": "设置中指定",
                    "available": True,
                }
            return {
                "path": None,
                "source": "custom-missing",
                "source_label": "设置中的 ADB 不存在",
                "available": False,
                "missing_path": configured,
            }

        requested = self.config.get_tool(tool_id)
        if requested and requested.get("adb_path") and Path(requested["adb_path"]).is_file():
            return {
                "path": requested["adb_path"],
                "source": "tool",
                "source_label": f"{requested['version']} 内置",
                "available": True,
            }

        for tool in self.config.tools:
            adb_path = tool.get("adb_path")
            if adb_path and Path(adb_path).is_file():
                return {
                    "path": adb_path,
                    "source": "other-tool",
                    "source_label": f"{tool['version']} 内置",
                    "available": True,
                }

        env_adb = os.environ.get("ADB")
        candidates: list[Path] = []
        if env_adb:
            candidates.append(Path(env_adb))
        path_found = shutil.which("adb.exe") or shutil.which("adb")
        if path_found:
            candidates.append(Path(path_found))
        local = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        candidates.extend(
            [
                local / "Android" / "Sdk" / "platform-tools" / "adb.exe",
                Path.home() / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe",
                Path("C:/platform-tools/adb.exe"),
                Path(os.environ.get("ProgramFiles", "C:/Program Files"))
                / "Android"
                / "platform-tools"
                / "adb.exe",
            ]
        )
        for candidate in candidates:
            if candidate.is_file():
                return {
                    "path": str(candidate),
                    "source": "system",
                    "source_label": "系统 ADB",
                    "available": True,
                }

        return {
            "path": None,
            "source": "none",
            "source_label": "未找到 ADB",
            "available": False,
        }

    def require_adb(self, tool_id: str | None = None) -> dict[str, Any]:
        info = self.get_adb_info(tool_id)
        if not info.get("path"):
            raise AppError(
                "没有找到可用的 adb.exe",
                code="ADB_UNAVAILABLE",
                hint="添加自带 adb 的 scrcpy 版本，或在右侧设置中指定 adb.exe。",
                detail=info.get("missing_path", ""),
            )
        return info

    def run(
        self,
        args: list[str],
        *,
        tool_id: str | None = None,
        timeout: float = 12.0,
    ) -> subprocess.CompletedProcess[str]:
        info = self.require_adb(tool_id)
        try:
            return run_capture([info["path"], *args], timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise AppError(
                "ADB 响应超时",
                code="ADB_TIMEOUT",
                hint="确认 adb server 正常运行后重试。",
                detail=str(exc),
            ) from exc
        except OSError as exc:
            raise AppError(
                "无法运行 ADB",
                code="ADB_RUN_FAILED",
                hint=info["path"],
                detail=str(exc),
            ) from exc

    def list_devices(self, tool_id: str | None = None) -> dict[str, Any]:
        result = self.run(["devices", "-l"], tool_id=tool_id, timeout=15.0)
        output = f"{result.stdout or ''}{result.stderr or ''}"
        devices = parse_adb_devices(output)
        if result.returncode != 0 and not devices:
            raise AppError(
                "读取设备列表失败",
                code="ADB_LIST_FAILED",
                detail=output.strip()[:2000],
            )
        return {
            "devices": devices,
            "raw": output,
            "adb": self.get_adb_info(tool_id),
        }

    def discover_mdns(self, tool_id: str | None = None) -> dict[str, Any]:
        result = self.run(["mdns", "services"], tool_id=tool_id, timeout=12.0)
        output = f"{result.stdout or ''}{result.stderr or ''}"
        return {
            "services": parse_mdns_services(output),
            "raw": output,
            "supported": result.returncode == 0 or bool(output.strip()),
        }
