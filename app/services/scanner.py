"""Fast, bounded TCP port probing for adb-over-Wi-Fi candidates."""

from __future__ import annotations

import socket
import struct
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from ..errors import AppError
from ..parsers import is_valid_host, is_valid_port, normalize_port_range

_ADB_COMMANDS = {"CNXN", "AUTH", "OKAY", "CLSE"}


def _probe(ip: str, port: int, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        code = sock.connect_ex((ip, port))
        is_open = code == 0
    except OSError:
        is_open = False
    finally:
        try:
            sock.close()
        except OSError:
            pass
    return {
        "port": port,
        "open": is_open,
        "latency_ms": round((time.perf_counter() - started) * 1000),
    }


def probe_adb(host: str, port: int, timeout: float = 1.0) -> bool:
    """Perform a read-only ADB CNXN handshake to distinguish adbd from generic
    open services (RPC, SMB, web servers, ...).

    This never issues a shell command and does not register a device with the
    local adb server. It only asks the remote endpoint whether it speaks ADB.
    """
    payload = b"host::\x00"
    command = int.from_bytes(b"CNXN", "little")
    header = struct.pack(
        "<6I",
        command,
        0x01000000,
        256 * 1024,
        len(payload),
        sum(payload) & 0xFFFFFFFF,
        command ^ 0xFFFFFFFF,
    )
    sock: socket.socket | None = None
    try:
        sock = socket.create_connection((host, int(port)), timeout=timeout)
        sock.settimeout(timeout)
        sock.sendall(header + payload)
        response = sock.recv(4)
        return len(response) == 4 and response.decode("ascii", errors="replace") in _ADB_COMMANDS
    except OSError:
        return False
    finally:
        try:
            sock.close()
        except (AttributeError, OSError):
            pass


def verify_adb_ports(
    host: str,
    ports: list[int],
    *,
    timeout: float = 1.0,
    concurrency: int = 16,
) -> list[int]:
    if not ports:
        return []
    verified: list[int] = []
    with ThreadPoolExecutor(max_workers=max(1, min(32, concurrency))) as pool:
        futures = {pool.submit(probe_adb, host, port, timeout): port for port in ports}
        for future in as_completed(futures):
            try:
                if future.result():
                    verified.append(futures[future])
            except Exception:
                pass
    return sorted(set(verified))


def scan_ports(
    host: str,
    start: int = 5555,
    end: int = 5585,
    timeout_ms: int = 420,
    extra_ports: list[int] | None = None,
    concurrency: int = 32,
    verify_adb: bool = False,
) -> dict[str, Any]:
    clean_host = str(host or "").strip()
    if not is_valid_host(clean_host):
        raise AppError("请输入有效的 IP 地址或主机名", code="INVALID_HOST")
    first, last = normalize_port_range(start, end)
    timeout = max(0.08, min(3.0, float(timeout_ms) / 1000.0))
    ports = set(range(first, last + 1))
    for value in extra_ports or []:
        if is_valid_port(value):
            ports.add(int(value))
    ordered = sorted(ports)

    try:
        infos = socket.getaddrinfo(clean_host, None, socket.AF_INET, socket.SOCK_STREAM)
        ip = infos[0][4][0]
    except socket.gaierror as exc:
        raise AppError(
            f"无法解析地址 {clean_host}",
            code="HOST_UNRESOLVABLE",
            hint="请检查 IP 是否正确，以及手机和电脑是否在同一局域网。",
            detail=str(exc),
        ) from exc

    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    worker_count = max(1, min(256, max(int(concurrency), len(ordered) // 32)))
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = {pool.submit(_probe, ip, port, timeout): port for port in ordered}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception:
                results.append({"port": futures[future], "open": False, "latency_ms": 0})

    results.sort(key=lambda item: item["port"])
    open_ports = [item for item in results if item["open"]]
    adb_ports: list[int] = []
    if verify_adb and open_ports:
        adb_ports = verify_adb_ports(
            ip,
            [item["port"] for item in open_ports],
            timeout=min(1.5, max(0.6, timeout * 2.5)),
            concurrency=16,
        )
    return {
        "host": clean_host,
        "ip": ip,
        "range": {"start": first, "end": last},
        "scanned": len(ordered),
        "timeout_ms": int(timeout * 1000),
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "ports": results,
        "open_ports": open_ports,
        "adb_ports": adb_ports,
        "open": [item["port"] for item in open_ports],
    }
