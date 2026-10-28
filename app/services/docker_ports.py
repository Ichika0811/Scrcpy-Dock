"""Discover Android/ADB ports published by local Docker containers."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

_DOCKER_CANDIDATES = [
    Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    / "Docker"
    / "Docker"
    / "resources"
    / "bin"
    / "docker.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Docker" / "docker.exe",
    Path("C:/ProgramData/DockerDesktop/version-bin/docker.exe"),
]


def find_docker() -> str | None:
    found = shutil.which("docker.exe") or shutil.which("docker")
    if found:
        return found
    for candidate in _DOCKER_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
    return None


def _is_adb_container_port(container_port: int) -> bool:
    # scrcpy talks to adb on 5555 by default; some Android containers expose
    # 5556/5557/5585 for multiple instances. Other published web ports are
    # intentionally ignored so the device rail does not fill with noise.
    return 5555 <= container_port <= 5585 or container_port == 5037


def _host_ports(mapping: str) -> list[int]:
    """Extract host ports from a Docker Ports cell.

    Examples:
      0.0.0.0:55007->5555/tcp, [::]:55007->5555/tcp
      127.0.0.1:5556->5555/tcp
      55007->5555/tcp
    """
    result: list[int] = []
    for part in str(mapping or "").split(","):
        part = part.strip()
        if "->" not in part:
            continue
        left, right = part.split("->", 1)
        try:
            container_port = int(right.split("/", 1)[0])
        except ValueError:
            continue
        if not _is_adb_container_port(container_port):
            continue
        host_side = left.rsplit(":", 1)[-1].strip()
        if host_side.isdigit():
            port = int(host_side)
            if 1 <= port <= 65535 and port not in result:
                result.append(port)
    return result


def parse_docker_ps(output: str) -> list[dict[str, Any]]:
    ports: list[dict[str, Any]] = []
    seen: set[int] = set()
    for raw in str(output or "").splitlines():
        line = raw.rstrip("\r")
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) >= 3:
            name, image, mapping = fields[0].strip(), fields[1].strip(), fields[2].strip()
        elif len(fields) == 2:
            name, image, mapping = fields[0].strip(), "", fields[1].strip()
        else:
            continue
        for port in _host_ports(mapping):
            if port in seen:
                continue
            seen.add(port)
            ports.append(
                {
                    "port": port,
                    "container": name or image or "Docker 容器",
                    "image": image,
                    "mapping": mapping,
                }
            )
    return ports


def discover_docker_ports(*, timeout: float = 5.0) -> list[dict[str, Any]]:
    """Return adb-like published ports from the local Docker daemon.

    Missing Docker, a stopped daemon, permission errors, or timeouts are all
    treated as "no Docker" rather than an application error.
    """
    docker = find_docker()
    if not docker:
        return []
    try:
        result = subprocess.run(
            [
                docker,
                "ps",
                "--format",
                "{{.Names}}\t{{.Image}}\t{{.Ports}}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            return []
        return parse_docker_ps(result.stdout or "")
    except (OSError, subprocess.SubprocessError):
        return []
