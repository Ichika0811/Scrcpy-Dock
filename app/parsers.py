"""Pure parsing and command-line helpers (no Qt, no I/O)."""

from __future__ import annotations

import re
from typing import Any, Iterable

_ANSI_OSC = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\)")
_ANSI_CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_ANSI_OTHER = re.compile(r"\x1b[@-_]")


def strip_ansi(text: str) -> str:
    value = str(text or "")
    value = _ANSI_OSC.sub("", value)
    value = _ANSI_CSI.sub("", value)
    value = _ANSI_OTHER.sub("", value)
    return value.replace("\r", "")


def clean_line(text: str) -> str:
    return (
        strip_ansi(text)
        .replace("\x00", "")
        .replace("\b", "")
        .replace("\v", "")
        .replace("\f", "")
        .replace("\n", " ")
    )


def normalize_version(output: str) -> str:
    match = re.search(r"\bscrcpy\s+v?([0-9][0-9a-zA-Z.+\-_]*)", output or "", re.I)
    if match:
        return match.group(1).rstrip("),;")
    return "未知版本"


def parse_arg_string(value: str) -> list[str]:
    """Split a command-line fragment without a shell.

    Backslashes are preserved so Windows paths such as ``C:\\tools`` survive.
    A backslash only escapes the quote that is currently active.
    """
    source = str(value or "")
    if len(source) > 8000:
        raise ValueError("附加参数过长")
    args: list[str] = []
    current = ""
    quote: str | None = None
    token_started = False
    i = 0
    while i < len(source):
        char = source[i]
        if quote:
            if char == quote:
                quote = None
                token_started = True
                i += 1
                continue
            if char == "\\" and i + 1 < len(source) and source[i + 1] == quote:
                current += quote
                i += 2
                continue
            current += char
            i += 1
            continue
        if char in {'"', "'"}:
            quote = char
            token_started = True
            i += 1
            continue
        if char.isspace():
            if token_started:
                args.append(current)
                current = ""
                token_started = False
            i += 1
            continue
        current += char
        token_started = True
        i += 1
    if quote:
        raise ValueError("附加参数中的引号未闭合")
    if token_started:
        args.append(current)
    return args


def quote_arg(value: str) -> str:
    text = str(value or "")
    if not text:
        return '""'
    if not re.search(r'[\s"]', text):
        return text
    return f'"{text.replace(chr(34), chr(92) + chr(34))}"'


def command_line(executable: str, args: Iterable[str]) -> str:
    return " ".join(quote_arg(part) for part in [executable, *args])


def build_scrcpy_args(
    serial: str,
    *,
    window_title: str = "",
    extra_args: str = "",
) -> list[str]:
    if not serial.strip():
        raise ValueError("缺少设备序列号")
    args = ["-s", serial]
    if window_title:
        args.append(f"--window-title={window_title}")
    args.extend(parse_arg_string(extra_args))
    return args


def supports_window_title(version: str) -> bool:
    match = re.match(r"^(\d+)\.(\d+)", version or "")
    if not match:
        return False
    major, minor = int(match.group(1)), int(match.group(2))
    return major > 1 or (major == 1 and minor >= 19)


def scrcpy_window_title(device_name: str, serial: str) -> str:
    """The native scrcpy window is named "<ip>:<port> <device>"."""
    name = " ".join(str(device_name or "").split())
    target = " ".join(str(serial or "").split())
    return f"{target} {name}".strip()


def is_valid_port(value: Any) -> bool:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return False
    return 1 <= port <= 65535


def is_valid_host(value: str) -> bool:
    host = str(value or "").strip()
    if not host or len(host) > 253 or re.search(r"[\s/\\]", host):
        return False
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host):
        return all(0 <= int(part) <= 255 for part in host.split("."))
    return bool(
        re.fullmatch(
            r"(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)"
            r"(?:\.(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?))*",
            host,
        )
    )


def make_target(host: str, port: Any) -> str:
    clean_host = str(host or "").strip()
    if not is_valid_host(clean_host):
        raise ValueError("请输入有效的设备 IP 地址或主机名")
    if not is_valid_port(port):
        raise ValueError("端口号必须在 1–65535 之间")
    return f"{clean_host}:{int(port)}"


def normalize_port_range(start: Any, end: Any) -> tuple[int, int]:
    try:
        first, last = int(start), int(end)
    except (TypeError, ValueError) as exc:
        raise ValueError("扫描端口范围无效") from exc
    if not (1 <= first <= 65535 and 1 <= last <= 65535):
        raise ValueError("扫描端口范围无效")
    if first > last:
        raise ValueError("扫描起始端口不能大于结束端口")
    return first, last


_STATUS_LABELS = {
    "device": "在线",
    "offline": "离线",
    "unauthorized": "未授权",
    "recovery": "Recovery",
    "sideload": "Sideload",
    "bootloader": "Fastboot",
    "no permissions": "无访问权限",
}


def parse_adb_devices(output: str) -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in str(output or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("*") or re.match(r"^List of devices", line, re.I):
            continue
        if re.match(r"^adb server", line, re.I) or line.lower().startswith("error:"):
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        serial, status = fields[0], fields[1]
        rest_start = 2
        if status == "no" and len(fields) > 2 and fields[2] == "permissions":
            status = "no permissions"
            rest_start = 3
        if status not in _STATUS_LABELS or serial in seen:
            continue
        seen.add(serial)
        meta: dict[str, str] = {}
        for token in fields[rest_start:]:
            if ":" in token:
                key, value = token.split(":", 1)
                meta[key] = value
        model = (meta.get("model") or meta.get("product") or "").replace("_", " ").strip()
        is_emulator = serial.startswith("emulator-")
        is_tcp = bool(re.fullmatch(r".+:\d+", serial)) and not is_emulator
        devices.append(
            {
                "serial": serial,
                "status": status,
                "status_label": _STATUS_LABELS[status],
                "online": status == "device",
                "model": model or ("Android 模拟器" if is_emulator else "Android 设备"),
                "product": meta.get("product", ""),
                "device": meta.get("device", ""),
                "transport_id": meta.get("transport_id", ""),
                "kind": "tcp" if is_tcp else "emulator" if is_emulator else "usb",
                "wireless": is_tcp,
                "name": model or ("Android 模拟器" if is_emulator else serial),
            }
        )
    devices.sort(key=lambda item: (not item["online"], item["model"].casefold()))
    return devices


def parse_mdns_services(output: str) -> list[dict[str, Any]]:
    services: list[dict[str, Any]] = []
    for raw in str(output or "").splitlines():
        line = raw.strip()
        if not line or line.lower().startswith("list of discovered"):
            continue
        match = re.search(
            r"(\S+)\s+(_adb-tls-(connect|pairing))\._tcp\.?\s+(\S+):(\d+)",
            line,
            re.I,
        )
        if not match:
            continue
        port = int(match.group(5))
        if not is_valid_port(port):
            continue
        services.append(
            {
                "name": match.group(1),
                "type": match.group(2),
                "kind": match.group(3),
                "host": match.group(4),
                "port": port,
                "target": f"{match.group(4)}:{port}",
                "pairing": match.group(3) == "pairing",
            }
        )
    return services


def evaluate_adb_connect(output: str) -> tuple[bool, str]:
    text = str(output or "")
    clean = text.strip()
    first_line = next(
        (
            line.strip()
            for line in clean.splitlines()
            if line.strip() and not line.startswith("*") and not re.match(r"^adb server", line, re.I)
        ),
        "",
    )
    failed = bool(
        re.search(
            r"failed|cannot|unable|refused|timed out|no route|offline|unknown host",
            text,
            re.I,
        )
    )
    success = bool(re.search(r"connected to|already connected", text, re.I)) and not failed
    return success, first_line or ("连接成功" if success else "ADB 连接失败")


def safe_file_part(value: str, fallback: str = "terminal") -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", str(value or ""))
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._")[:80]
    return cleaned or fallback
