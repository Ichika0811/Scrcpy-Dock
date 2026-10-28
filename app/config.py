"""Persistent application configuration and device history."""

from __future__ import annotations

import copy
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from .errors import AppError
from .parsers import is_valid_host, is_valid_port

CONFIG_VERSION = 2

TOOL_COLOR_PALETTE: tuple[tuple[str, str], ...] = (
    ("#5eead4", "青绿"),
    ("#60a5fa", "蓝色"),
    ("#a78bfa", "紫色"),
    ("#f472b6", "粉色"),
    ("#fbbf24", "琥珀"),
    ("#4ade80", "绿色"),
    ("#fb923c", "橙色"),
    ("#22d3ee", "天蓝"),
    ("#f87171", "红色"),
    ("#94a3b8", "灰蓝"),
)
TOOL_COLORS = tuple(color for color, _name in TOOL_COLOR_PALETTE)


def clean_tool_color(value: Any) -> str:
    text = str(value or "").strip().lower()
    if len(text) == 7 and text.startswith("#"):
        try:
            int(text[1:], 16)
        except ValueError:
            return ""
        return text
    return ""

DEFAULT_SETTINGS: dict[str, Any] = {
    "adb_path": "",
    "scan_start": 5555,
    "scan_end": 5585,
    "scan_timeout_ms": 420,
    "auto_scan": True,
    "scan_full": True,
    "auto_adb_connect": True,
    "auto_import_adb_devices": True,
    "use_docker_ports": True,
    "max_terminal_lines": 5000,
    "default_args": "",
}

_WINDOW_DEFAULT = {
    "width": 1280,
    "height": 820,
    "x": None,
    "y": None,
    "maximized": False,
}


def default_data_dir() -> Path:
    override = os.environ.get("SCRCPY_DOCK_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "ScrcpyDock"
    return Path.home() / ".scrcpy-dock"


def _clamp(value: Any, fallback: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, number))


def _clean(value: Any, limit: int = 200) -> str:
    return re_clean(value)[:limit]


def re_clean(value: Any) -> str:
    text = str(value or "")
    return "".join(character for character in text if ord(character) >= 32).strip()


def normalize_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    data = {**DEFAULT_SETTINGS, **(raw or {})}
    start = _clamp(data.get("scan_start"), 5555, 1, 65535)
    end = _clamp(data.get("scan_end"), 5585, 1, 65535)
    if start > end:
        start, end = 5555, 5585
    return {
        "adb_path": str(data.get("adb_path") or "").strip(),
        "scan_start": start,
        "scan_end": end,
        "scan_timeout_ms": _clamp(data.get("scan_timeout_ms"), 420, 80, 3000),
        "auto_scan": bool(data.get("auto_scan", True)),
        "scan_full": bool(data.get("scan_full", True)),
        "auto_adb_connect": bool(data.get("auto_adb_connect", True)),
        "auto_import_adb_devices": bool(data.get("auto_import_adb_devices", True)),
        "use_docker_ports": bool(data.get("use_docker_ports", True)),
        "max_terminal_lines": _clamp(data.get("max_terminal_lines"), 5000, 500, 20000),
        "default_args": str(data.get("default_args") or "")[:8000],
    }


def normalize_tool(raw: dict[str, Any]) -> dict[str, Any] | None:
    if not raw or not raw.get("id") or not raw.get("scrcpy_path"):
        return None
    detected = _clean(raw.get("detected_version") or raw.get("version") or "未知版本", 60)
    version_auto = raw.get("version_auto") is not False
    version = detected if version_auto else _clean(raw.get("version") or detected, 60)
    return {
        "id": str(raw["id"]),
        "folder": str(raw.get("folder") or Path(raw["scrcpy_path"]).parent),
        "scrcpy_path": str(raw["scrcpy_path"]),
        "adb_path": str(raw.get("adb_path") or ""),
        "version": version or "未知版本",
        "detected_version": detected or "未知版本",
        "version_auto": version_auto,
        "version_raw": str(raw.get("version_raw") or "")[:2000],
        "color": clean_tool_color(raw.get("color")),
        "favorite": bool(raw.get("favorite")),
        "favorite_at": float(raw.get("favorite_at") or 0),
        "added_at": float(raw.get("added_at") or time.time()),
        "last_used_at": float(raw.get("last_used_at") or 0),
    }


def normalize_port(raw: dict[str, Any]) -> dict[str, Any] | None:
    try:
        port = int(raw.get("port"))
    except (TypeError, ValueError):
        return None
    if not is_valid_port(port):
        return None
    source = raw.get("source") if raw.get("source") in {"scan", "connect", "manual", "device", "history", "docker"} else "history"
    status = raw.get("last_status") if raw.get("last_status") in {"success", "failed", "unknown"} else "unknown"
    return {
        "port": port,
        "device_name": _clean(raw.get("device_name"), 120),
        "source": source,
        "last_connected_at": float(raw.get("last_connected_at") or 0),
        "last_attempt_at": float(raw.get("last_attempt_at") or 0),
        "last_status": status,
        "last_message": _clean(raw.get("last_message"), 300),
    }


def normalize_network(raw: dict[str, Any]) -> dict[str, Any] | None:
    host = _clean(raw.get("ip"), 200)
    if not is_valid_host(host):
        return None
    ports: list[dict[str, Any]] = []
    seen: set[int] = set()
    for entry in raw.get("ports") or []:
        port = normalize_port(entry)
        if not port or port["port"] in seen:
            continue
        seen.add(port["port"])
        ports.append(port)
    ports.sort(key=lambda item: (-(item["last_connected_at"] or item["last_attempt_at"] or 0), item["port"]))
    return {
        "id": str(raw.get("id") or uuid.uuid4()),
        "ip": host,
        "label": _clean(raw.get("label"), 60),
        "ports": ports,
        "created_at": float(raw.get("created_at") or time.time()),
        "last_used_at": float(raw.get("last_used_at") or 0),
    }


def normalize_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    source = raw or {}
    tools: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for entry in source.get("tools") or []:
        tool = normalize_tool(entry)
        if not tool:
            continue
        key = tool["scrcpy_path"].casefold()
        if key in seen_paths:
            continue
        seen_paths.add(key)
        if not tool.get("color"):
            tool["color"] = TOOL_COLORS[len(tools) % len(TOOL_COLORS)]
        tools.append(tool)
    tool_ids = {tool["id"] for tool in tools}
    last_tool_id = source.get("last_tool_id")
    if last_tool_id not in tool_ids:
        last_tool_id = tools[0]["id"] if tools else None

    networks: list[dict[str, Any]] = []
    seen_hosts: set[str] = set()
    for entry in source.get("networks") or []:
        network = normalize_network(entry)
        if not network or network["ip"].casefold() in seen_hosts:
            continue
        seen_hosts.add(network["ip"].casefold())
        networks.append(network)
    networks.sort(key=lambda item: item["last_used_at"], reverse=True)

    window = {**_WINDOW_DEFAULT, **(source.get("window") or {})}
    window["width"] = _clamp(window.get("width"), 1280, 940, 4096)
    window["height"] = _clamp(window.get("height"), 820, 620, 2600)
    window["x"] = int(window["x"]) if isinstance(window.get("x"), (int, float)) else None
    window["y"] = int(window["y"]) if isinstance(window.get("y"), (int, float)) else None
    window["maximized"] = bool(window.get("maximized"))

    return {
        "version": CONFIG_VERSION,
        "tools": tools,
        "last_tool_id": last_tool_id,
        "networks": networks,
        "settings": normalize_settings(source.get("settings")),
        "window": window,
    }


class ConfigStore:
    """Small synchronous JSON store owned by the UI thread."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir = self.data_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.data_dir / "config.json"
        self.data = normalize_config({})
        self.load()

    def load(self) -> None:
        if self.config_path.exists():
            try:
                raw = json.loads(self.config_path.read_text(encoding="utf-8"))
                self.data = normalize_config(raw)
            except Exception as exc:  # corrupted JSON must not brick the app
                stamp = time.strftime("%Y%m%d-%H%M%S")
                try:
                    backup = self.data_dir / f"config.corrupt-{stamp}.json"
                    backup.write_bytes(self.config_path.read_bytes())
                except OSError:
                    pass
                self.data = normalize_config({})
                self.last_load_error = exc
            self.save()
        else:
            self.data = normalize_config({})
            self.save()

    def save(self) -> None:
        payload = json.dumps(self.data, ensure_ascii=False, indent=2) + "\n"
        temporary = self.config_path.with_suffix(".json.tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, self.config_path)

    # ------------------------------------------------------------------ tools

    @property
    def tools(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.data["tools"])

    def get_tool(self, tool_id: str | None) -> dict[str, Any] | None:
        if not tool_id:
            return None
        for tool in self.data["tools"]:
            if tool["id"] == tool_id:
                return copy.deepcopy(tool)
        return None

    def add_tool(self, info: dict[str, Any]) -> dict[str, Any]:
        scrcpy_path = str(info.get("scrcpy_path") or "")
        duplicate = next(
            (tool for tool in self.data["tools"] if tool["scrcpy_path"].casefold() == scrcpy_path.casefold()),
            None,
        )
        if duplicate:
            raise AppError(
                "这个 scrcpy 工具已经添加过了",
                code="TOOL_DUPLICATE",
                hint=duplicate["folder"],
            )
        detected = _clean(info.get("detected_version") or info.get("version") or "未知版本", 60)
        tool = {
            "id": str(uuid.uuid4()),
            "folder": str(info.get("folder") or Path(scrcpy_path).parent),
            "scrcpy_path": scrcpy_path,
            "adb_path": str(info.get("adb_path") or ""),
            "version": detected,
            "detected_version": detected,
            "version_auto": True,
            "version_raw": str(info.get("version_raw") or "")[:2000],
            "color": TOOL_COLORS[len(self.data["tools"]) % len(TOOL_COLORS)],
            "favorite": False,
            "favorite_at": 0.0,
            "added_at": time.time(),
            "last_used_at": 0.0,
        }
        self.data["tools"].append(tool)
        self.data["last_tool_id"] = tool["id"]
        self.save()
        return copy.deepcopy(tool)

    def update_tool(self, tool_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        target = next((tool for tool in self.data["tools"] if tool["id"] == tool_id), None)
        if not target:
            raise AppError("scrcpy 版本不存在", code="TOOL_NOT_FOUND")
        if "favorite" in patch:
            target["favorite"] = bool(patch["favorite"])
            target["favorite_at"] = time.time() if target["favorite"] else 0.0
        if "version" in patch:
            version = _clean(patch["version"], 60)
            if not version:
                raise AppError("版本标签不能为空", code="INVALID_VERSION")
            target["version"] = version
            target["version_auto"] = False
        if patch.get("version_auto") is True:
            target["version_auto"] = True
            target["version"] = target["detected_version"]
        if "detected_version" in patch:
            target["detected_version"] = _clean(patch["detected_version"], 60) or "未知版本"
            if target["version_auto"]:
                target["version"] = target["detected_version"]
        if "version_raw" in patch:
            target["version_raw"] = str(patch["version_raw"] or "")[:2000]
        if "adb_path" in patch:
            target["adb_path"] = str(patch["adb_path"] or "")
        if "color" in patch:
            color = clean_tool_color(patch["color"])
            if not color:
                raise AppError("颜色格式无效", code="INVALID_COLOR")
            target["color"] = color
        self.save()
        return copy.deepcopy(target)

    def remove_tool(self, tool_id: str) -> None:
        before = len(self.data["tools"])
        self.data["tools"] = [tool for tool in self.data["tools"] if tool["id"] != tool_id]
        if len(self.data["tools"]) == before:
            raise AppError("scrcpy 版本不存在", code="TOOL_NOT_FOUND")
        if self.data["last_tool_id"] == tool_id:
            self.data["last_tool_id"] = self.data["tools"][0]["id"] if self.data["tools"] else None
        self.save()

    def mark_tool_used(self, tool_id: str) -> None:
        for tool in self.data["tools"]:
            if tool["id"] == tool_id:
                tool["last_used_at"] = time.time()
                self.data["last_tool_id"] = tool_id
                self.save()
                return

    @property
    def last_tool_id(self) -> str | None:
        return self.data["last_tool_id"]

    def set_last_tool(self, tool_id: str) -> None:
        if any(tool["id"] == tool_id for tool in self.data["tools"]):
            self.data["last_tool_id"] = tool_id
            self.save()

    # --------------------------------------------------------------- networks

    @property
    def networks(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.data["networks"])

    def get_network(self, network_id: str | None) -> dict[str, Any] | None:
        if not network_id:
            return None
        for network in self.data["networks"]:
            if network["id"] == network_id:
                return copy.deepcopy(network)
        return None

    def find_network_by_ip(self, host: str) -> dict[str, Any] | None:
        host_cf = str(host or "").casefold()
        for network in self.data["networks"]:
            if network["ip"].casefold() == host_cf:
                return copy.deepcopy(network)
        return None

    def add_network(
        self,
        ip: str,
        *,
        label: str = "",
        port: int | None = None,
        device_name: str = "",
        source: str = "manual",
    ) -> dict[str, Any]:
        host = _clean(ip, 200)
        if not is_valid_host(host):
            raise AppError("请输入有效的 IP 地址或主机名", code="INVALID_HOST")
        if self.find_network_by_ip(host):
            raise AppError("这个 IP 已经存在", code="NETWORK_DUPLICATE", hint=host)
        network = {
            "id": str(uuid.uuid4()),
            "ip": host,
            "label": _clean(label, 60),
            "ports": [],
            "created_at": time.time(),
            "last_used_at": 0.0,
        }
        if port is not None and is_valid_port(port):
            network["ports"].append(
                {
                    "port": int(port),
                    "device_name": _clean(device_name, 120),
                    "source": source,
                    "last_connected_at": 0.0,
                    "last_attempt_at": 0.0,
                    "last_status": "unknown",
                    "last_message": "",
                }
            )
        self.data["networks"].insert(0, network)
        self.save()
        return copy.deepcopy(network)

    def update_network(self, network_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        network = next((item for item in self.data["networks"] if item["id"] == network_id), None)
        if not network:
            raise AppError("IP 不存在", code="NETWORK_NOT_FOUND")
        if "label" in patch:
            network["label"] = _clean(patch["label"], 60)
        if "ip" in patch:
            host = _clean(patch["ip"], 200)
            if not is_valid_host(host):
                raise AppError("请输入有效的 IP 地址或主机名", code="INVALID_HOST")
            duplicate = any(
                item["id"] != network_id and item["ip"].casefold() == host.casefold()
                for item in self.data["networks"]
            )
            if duplicate:
                raise AppError("这个 IP 已经存在", code="NETWORK_DUPLICATE")
            network["ip"] = host
        self.save()
        return copy.deepcopy(network)

    def remove_network(self, network_id: str) -> None:
        self.data["networks"] = [item for item in self.data["networks"] if item["id"] != network_id]
        self.save()

    def add_network_port(
        self,
        network_id: str,
        port: int,
        *,
        device_name: str = "",
        source: str = "manual",
    ) -> dict[str, Any]:
        network = next((item for item in self.data["networks"] if item["id"] == network_id), None)
        if not network:
            raise AppError("IP 不存在", code="NETWORK_NOT_FOUND")
        if not is_valid_port(port):
            raise AppError("端口号必须在 1–65535 之间", code="INVALID_PORT")
        numeric = int(port)
        entry = next((item for item in network["ports"] if item["port"] == numeric), None)
        if entry is None:
            entry = {
                "port": numeric,
                "device_name": "",
                "source": source,
                "last_connected_at": 0.0,
                "last_attempt_at": 0.0,
                "last_status": "unknown",
                "last_message": "",
            }
            network["ports"].append(entry)
        if device_name and not entry["device_name"]:
            entry["device_name"] = _clean(device_name, 120)
        if source and entry["source"] != "connect":
            entry["source"] = source
        self._sort_ports(network)
        self.save()
        return copy.deepcopy(network)

    def remove_network_port(self, network_id: str, port: int) -> None:
        network = next((item for item in self.data["networks"] if item["id"] == network_id), None)
        if not network:
            return
        network["ports"] = [entry for entry in network["ports"] if entry["port"] != int(port)]
        self.save()

    def ensure_network_port(
        self,
        host: str,
        port: int,
        network_id: str | None = None,
    ) -> dict[str, Any]:
        network = self.get_network(network_id) or self.find_network_by_ip(host)
        if network is None:
            network = self.add_network(host, port=port, source="connect")
            return self.get_network(network["id"]) or network
        if not any(entry["port"] == int(port) for entry in network["ports"]):
            network = self.add_network_port(network["id"], port, source="manual")
        return self.get_network(network["id"]) or network

    def record_port_attempt(
        self,
        network_id: str,
        port: int,
        *,
        success: bool,
        device_name: str = "",
        message: str = "",
    ) -> dict[str, Any] | None:
        network = next((item for item in self.data["networks"] if item["id"] == network_id), None)
        if not network:
            return None
        entry = next((item for item in network["ports"] if item["port"] == int(port)), None)
        if entry is None:
            entry = {
                "port": int(port),
                "device_name": "",
                "source": "connect",
                "last_connected_at": 0.0,
                "last_attempt_at": 0.0,
                "last_status": "unknown",
                "last_message": "",
            }
            network["ports"].append(entry)
        now = time.time()
        entry["last_attempt_at"] = now
        entry["last_status"] = "success" if success else "failed"
        entry["last_message"] = _clean(message, 300)
        if device_name:
            entry["device_name"] = _clean(device_name, 120)
        if success:
            entry["last_connected_at"] = now
            entry["source"] = "connect"
            network["last_used_at"] = now
            others = [item for item in self.data["networks"] if item["id"] != network["id"]]
            self.data["networks"] = [network, *others]
        self._sort_ports(network)
        self.save()
        return copy.deepcopy(network)

    def apply_device_names(
        self,
        devices: list[dict[str, Any]],
        *,
        auto_import: bool = False,
    ) -> bool:
        changed = False
        for device in devices:
            if not device.get("wireless"):
                continue
            serial = str(device.get("serial") or "")
            if ":" not in serial:
                continue
            host, port_text = serial.rsplit(":", 1)
            try:
                port = int(port_text)
            except ValueError:
                continue
            network = next(
                (
                    item
                    for item in self.data["networks"]
                    if item["ip"].casefold() == host.casefold()
                ),
                None,
            )
            if not network:
                if not auto_import or not device.get("online"):
                    continue
                network = {
                    "id": str(uuid.uuid4()),
                    "ip": host,
                    "label": "",
                    "ports": [],
                    "created_at": time.time(),
                    "last_used_at": 0.0,
                }
                self.data["networks"].insert(0, network)
                changed = True
            entry = next((item for item in network["ports"] if item["port"] == port), None)
            if entry is None:
                entry = {
                    "port": port,
                    "device_name": "",
                    "source": "device",
                    "last_connected_at": 0.0,
                    "last_attempt_at": time.time(),
                    "last_status": "unknown",
                    "last_message": "",
                }
                network["ports"].append(entry)
                changed = True
            model = _clean(device.get("model"), 120)
            if model and entry["device_name"] != model:
                entry["device_name"] = model
                changed = True
        if changed:
            for network in self.data["networks"]:
                self._sort_ports(network)
            self.save()
        return changed

    @staticmethod
    def _sort_ports(network: dict[str, Any]) -> None:
        network["ports"].sort(
            key=lambda entry: (
                -(entry["last_connected_at"] or entry["last_attempt_at"] or 0),
                entry["port"],
            )
        )

    # ---------------------------------------------------------------- settings

    @property
    def settings(self) -> dict[str, Any]:
        return copy.deepcopy(self.data["settings"])

    def update_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        self.data["settings"] = normalize_settings({**self.data["settings"], **patch})
        self.save()
        return copy.deepcopy(self.data["settings"])

    @property
    def window_state(self) -> dict[str, Any]:
        return copy.deepcopy(self.data["window"])

    def update_window_state(self, patch: dict[str, Any]) -> None:
        self.data["window"].update(patch)
        self.save()

    def snapshot(self) -> dict[str, Any]:
        return {
            "tools": self.tools,
            "last_tool_id": self.last_tool_id,
            "networks": self.networks,
            "settings": self.settings,
            "data_dir": str(self.data_dir),
            "logs_dir": str(self.logs_dir),
        }
