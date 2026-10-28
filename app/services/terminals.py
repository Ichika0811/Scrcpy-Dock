"""Managed scrcpy terminal sessions backed by QProcess."""

from __future__ import annotations

import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from ..config import ConfigStore
from ..errors import AppError
from ..parsers import (
    build_scrcpy_args,
    clean_line,
    command_line,
    evaluate_adb_connect,
    make_target,
    scrcpy_window_title,
    supports_window_title,
)
from .adb import AdbService
from .window_title import set_scrcpy_window_title


@dataclass
class LogLine:
    ts: float
    kind: str
    text: str

    def as_dict(self) -> dict[str, Any]:
        return {"ts": self.ts, "kind": self.kind, "text": self.text}


@dataclass
class TerminalSession:
    id: str
    tool_id: str | None
    status: str = "idle"
    target: dict[str, Any] | None = None
    process: QProcess | None = None
    adb_process: QProcess | None = None
    command_process: QProcess | None = None
    command_pid: int | None = None
    shell_cwd: str = ""
    pid: int | None = None
    command: str = ""
    adb_command: str = ""
    working_directory: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    ended_at: float | None = None
    exit_code: int | None = None
    error: str = ""
    lines: list[LogLine] = field(default_factory=list)
    log_path: Path | None = None
    log_handle: Any = None
    carry: dict[str, str] = field(default_factory=dict)
    generation: int = 0
    stopping: bool = False

    def target_serial(self) -> str:
        if not self.target:
            return ""
        return f"{self.target.get('host')}:{self.target.get('port')}"


class TerminalManager(QObject):
    created = Signal(str)
    updated = Signal(str)
    output = Signal(str, object)
    removed = Signal(str)

    def __init__(
        self,
        config: ConfigStore,
        adb_service: AdbService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.adb = adb_service
        self.sessions: dict[str, TerminalSession] = {}

    # ------------------------------------------------------------------ basics

    def create(self, tool_id: str | None = None) -> str:
        selected = tool_id if self.config.get_tool(tool_id) else self.config.last_tool_id
        terminal_id = uuid.uuid4().hex
        stamp = time.strftime("%Y%m%d_%H%M%S")
        log_path = self.config.logs_dir / f"{stamp}_terminal_{terminal_id[:8]}.log"
        session = TerminalSession(id=terminal_id, tool_id=selected, log_path=log_path)
        tool = self.config.get_tool(selected)
        if tool:
            session.shell_cwd = str(tool.get("folder") or "")
            session.working_directory = session.shell_cwd
        try:
            session.log_handle = log_path.open("a", encoding="utf-8", buffering=1)
            session.log_handle.write(
                f"# Scrcpy Dock terminal {terminal_id}\n"
                f"# Created: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )
        except OSError:
            session.log_handle = None
            session.log_path = None
        self.sessions[terminal_id] = session
        self.created.emit(terminal_id)
        self._append(session, "system", "终端就绪。选择左侧 scrcpy 版本，然后点击右侧端口开始连接。")
        self.updated.emit(terminal_id)
        return terminal_id

    def exists(self, terminal_id: str) -> bool:
        return terminal_id in self.sessions

    def require(self, terminal_id: str) -> TerminalSession:
        session = self.sessions.get(terminal_id)
        if not session:
            raise AppError("终端不存在", code="TERMINAL_NOT_FOUND")
        return session

    def lines(self, terminal_id: str) -> list[dict[str, Any]]:
        return [line.as_dict() for line in self.require(terminal_id).lines]

    def is_active_id(self, terminal_id: str) -> bool:
        session = self.sessions.get(terminal_id)
        return bool(session and session.status in {"connecting", "starting", "running", "stopping"})

    def active_count(self) -> int:
        return sum(
            1
            for session in self.sessions.values()
            if session.status in {"connecting", "starting", "running", "stopping"}
        )

    def snapshot(self, terminal_id: str) -> dict[str, Any]:
        session = self.require(terminal_id)
        tool = self.config.get_tool(session.tool_id)
        network = None
        port_info = None
        if session.target:
            network = (
                self.config.get_network(session.target.get("network_id"))
                if session.target.get("network_id")
                else self.config.find_network_by_ip(session.target.get("host", ""))
            )
            if network:
                port_info = next(
                    (
                        entry
                        for entry in network["ports"]
                        if entry["port"] == session.target.get("port")
                    ),
                    None,
                )
        target = None
        if session.target:
            target = {
                **session.target,
                "serial": session.target_serial(),
                "network_label": (network or {}).get("label", ""),
                "device_name": (port_info or {}).get("device_name")
                or session.target.get("device_name", ""),
            }
        command_running = False
        if session.command_process is not None:
            try:
                command_running = (
                    session.command_process.state() != QProcess.ProcessState.NotRunning
                )
            except RuntimeError:
                command_running = False
        return {
            "id": session.id,
            "tool_id": session.tool_id,
            "tool_version": (tool or {}).get("version") or "未选择版本",
            "tool_available": bool(tool and Path(tool["scrcpy_path"]).is_file()),
            "status": session.status,
            "target": target,
            "pid": session.pid,
            "command_running": command_running,
            "command_pid": session.command_pid,
            "shell_cwd": session.shell_cwd or session.working_directory,
            "command": session.command,
            "adb_command": session.adb_command,
            "working_directory": session.working_directory,
            "created_at": session.created_at,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "exit_code": session.exit_code,
            "error": session.error,
            "line_count": len(session.lines),
            "log_path": str(session.log_path) if session.log_path else "",
            "label": (network or {}).get("label", ""),
        }

    # ----------------------------------------------------------------- logging

    def _write_log(self, session: TerminalSession, line: LogLine) -> None:
        if not session.log_handle:
            return
        try:
            stamp = time.strftime("%H:%M:%S", time.localtime(line.ts))
            session.log_handle.write(f"{stamp} [{line.kind}] {line.text}\n")
        except OSError:
            pass

    def _append(self, session: TerminalSession, kind: str, text: str) -> None:
        clean = clean_line(text)[:16000]
        line = LogLine(ts=time.time(), kind=kind, text=clean)
        session.lines.append(line)
        limit = self.config.settings["max_terminal_lines"]
        if len(session.lines) > limit:
            del session.lines[: len(session.lines) - limit]
        self._write_log(session, line)
        self.output.emit(session.id, [line.as_dict()])

    def _append_text(self, session: TerminalSession, key: str, kind: str, text: str) -> None:
        if not text:
            return
        value = (session.carry.get(key, "") + text).replace("\r\n", "\n").replace("\r", "\n")
        parts = value.split("\n")
        session.carry[key] = parts.pop() if parts else ""
        for part in parts:
            self._append(session, kind, part)
        if len(session.carry.get(key, "")) > 20000:
            self._append(session, kind, session.carry[key])
            session.carry[key] = ""

    def _flush_carry(self, session: TerminalSession) -> None:
        for key, kind in (
            ("stdout", "stdout"),
            ("stderr", "stderr"),
            ("adb_stdout", "stdout"),
            ("adb_stderr", "stderr"),
            ("cmd_stdout", "stdout"),
            ("cmd_stderr", "stderr"),
        ):
            value = session.carry.get(key, "")
            if value:
                self._append(session, kind, value)
                session.carry[key] = ""

    def _emit_updated(self, session: TerminalSession) -> None:
        self.updated.emit(session.id)

    # ------------------------------------------------------------- process set

    @staticmethod
    def _hide_console(process: QProcess) -> None:
        try:
            def modifier(arguments: Any) -> None:
                arguments.flags |= 0x08000000  # CREATE_NO_WINDOW

            process.setCreateProcessArgumentsModifier(modifier)
            process._dsh_modifier = modifier  # keep the callback alive
        except (AttributeError, TypeError):
            pass

    def _kill_process(self, process: QProcess | None) -> None:
        if process is None:
            return
        try:
            process.blockSignals(True)
        except RuntimeError:
            return
        pid = process.processId()
        if os.name == "nt" and pid:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    timeout=4,
                    creationflags=0x08000000,
                )
            except (OSError, subprocess.SubprocessError):
                pass
        try:
            if process.state() != QProcess.ProcessState.NotRunning:
                process.kill()
                process.waitForFinished(1200)
        except RuntimeError:
            pass
        try:
            process.deleteLater()
        except RuntimeError:
            pass

    def _cancel_active(self, session: TerminalSession) -> None:
        session.generation += 1
        adb_process, process = session.adb_process, session.process
        session.adb_process = None
        session.process = None
        session.pid = None
        self._kill_process(adb_process)
        self._kill_process(process)
        self._kill_command(session, announce=False, emit=False)

    # --------------------------------------------------------------- command

    def _command_cwd(self, session: TerminalSession) -> Path:
        tool = self.config.get_tool(session.tool_id)
        candidates = [
            session.shell_cwd,
            (tool or {}).get("folder", ""),
            session.working_directory,
        ]
        for candidate in candidates:
            if candidate:
                path = Path(candidate)
                if path.is_dir():
                    return path
        return Path.home()

    def _kill_command(
        self,
        session: TerminalSession,
        *,
        announce: bool = False,
        emit: bool = True,
    ) -> None:
        process = session.command_process
        session.command_process = None
        session.command_pid = None
        if process is not None:
            self._flush_carry(session)
            self._kill_process(process)
        if announce:
            self._append(session, "system", "已中断当前命令。")
        if emit:
            self._emit_updated(session)

    def _command_running(self, session: TerminalSession) -> bool:
        process = session.command_process
        if process is None:
            return False
        try:
            return process.state() != QProcess.ProcessState.NotRunning
        except RuntimeError:
            return False

    def run_command(self, terminal_id: str, command: str) -> None:
        session = self.require(terminal_id)
        command = str(command or "").strip()
        if not command:
            return
        if len(command) > 4000:
            raise AppError("命令过长", code="COMMAND_TOO_LONG")
        if self._command_running(session):
            raise AppError("上一条命令仍在运行，请先按 Ctrl+C 中断", code="COMMAND_BUSY")

        cwd = self._command_cwd(session)
        lowered = command.casefold()
        if lowered in {"clear", "cls"}:
            self.clear(terminal_id)
            return
        if lowered in {"pwd", "cd"}:
            self._append(session, "stdout", str(cwd))
            self._emit_updated(session)
            return
        if lowered.startswith("cd ") or lowered.startswith("cd\t"):
            target = command[2:].strip().strip('"').strip("'")
            path = Path(target).expanduser()
            if not path.is_absolute():
                path = cwd / path
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            if resolved.is_dir():
                session.shell_cwd = str(resolved)
                self._append(session, "system", f"工作目录：{resolved}")
                self._emit_updated(session)
            else:
                self._append(session, "error", f"目录不存在：{resolved}")
                self._emit_updated(session)
            return

        self._append(session, "command", command)
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        process.setProgram(os.environ.get("COMSPEC", "cmd.exe"))
        process.setArguments(
            ["/d", "/s", "/c", f"chcp 65001>nul & {command}"]
        )
        process.setWorkingDirectory(str(cwd))
        environment = QProcessEnvironment.systemEnvironment()
        existing_path = environment.value("PATH") or environment.value("Path")
        environment.insert(
            "PATH",
            os.pathsep.join(
                dict.fromkeys(
                    [str(cwd), *[part for part in existing_path.split(os.pathsep) if part]]
                )
            ),
        )
        process.setProcessEnvironment(environment)
        self._hide_console(process)

        def consume() -> None:
            if session.command_process is not process:
                return
            out = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
            err = bytes(process.readAllStandardError()).decode("utf-8", errors="replace")
            self._append_text(session, "cmd_stdout", "stdout", out)
            self._append_text(session, "cmd_stderr", "stderr", err)

        def started() -> None:
            if session.command_process is not process:
                return
            session.command_pid = process.processId() or None
            self._emit_updated(session)

        def finished(code: int, _status: QProcess.ExitStatus) -> None:
            if session.command_process is not process:
                return
            consume()
            self._flush_carry(session)
            session.command_process = None
            session.command_pid = None
            self._append(session, "system", f"命令结束（退出码 {code}）")
            self._emit_updated(session)
            process.deleteLater()

        def failed(error: QProcess.ProcessError) -> None:
            if session.command_process is not process:
                return
            consume()
            self._flush_carry(session)
            session.command_process = None
            session.command_pid = None
            self._append(session, "error", f"命令启动失败：{error.name}")
            self._emit_updated(session)
            process.deleteLater()

        process.readyReadStandardOutput.connect(consume)
        process.readyReadStandardError.connect(consume)
        process.started.connect(started)
        process.finished.connect(finished)
        process.errorOccurred.connect(failed)
        session.command_process = process
        session.command_pid = None
        self._emit_updated(session)
        process.start()

    def interrupt(self, terminal_id: str) -> bool:
        session = self.require(terminal_id)
        if self._command_running(session):
            self._kill_command(session, announce=True)
            return True
        if self.is_active_id(terminal_id):
            self.stop(terminal_id)
            return True
        return False

    # ---------------------------------------------------------------- connect

    def assign_tool(self, terminal_id: str, tool_id: str) -> None:
        session = self.require(terminal_id)
        tool = self.config.get_tool(tool_id)
        if not tool:
            raise AppError("scrcpy 版本不存在", code="TOOL_NOT_FOUND")
        if not Path(tool["scrcpy_path"]).is_file():
            raise AppError(
                "scrcpy.exe 已不存在",
                code="TOOL_MISSING",
                hint=tool["folder"],
            )
        if session.status in {"connecting", "starting", "stopping"}:
            raise AppError("终端正在切换，请稍候", code="TERMINAL_BUSY")
        if session.tool_id == tool_id and session.status != "failed":
            self.config.set_last_tool(tool_id)
            return
        previous_target = dict(session.target) if session.target else None
        session.tool_id = tool_id
        self.config.set_last_tool(tool_id)
        self._append(session, "meta", f"当前终端版本切换为 scrcpy {tool['version']}")
        if previous_target and session.status == "running":
            self._append(session, "system", "正在使用新版本重新连接当前设备…")
            self.open_device(
                terminal_id,
                previous_target["host"],
                previous_target["port"],
                network_id=previous_target.get("network_id"),
            )
        else:
            self._emit_updated(session)

    def open_device(
        self,
        terminal_id: str,
        host: str,
        port: int,
        *,
        network_id: str | None = None,
    ) -> None:
        session = self.require(terminal_id)
        try:
            target_serial = make_target(host, port)
        except ValueError as exc:
            raise AppError(str(exc), code="INVALID_TARGET") from exc

        tool = self.config.get_tool(session.tool_id) or self.config.get_tool(self.config.last_tool_id)
        if not tool:
            raise AppError(
                "还没有可用的 scrcpy 版本",
                code="NO_TOOL",
                hint="请先在左侧添加 scrcpy 工具文件夹。",
            )
        if not Path(tool["scrcpy_path"]).is_file():
            raise AppError(
                "scrcpy.exe 不存在或已被移动",
                code="TOOL_MISSING",
                hint=tool["scrcpy_path"],
            )

        self._cancel_active(session)
        generation = session.generation
        session.tool_id = tool["id"]
        session.working_directory = str(tool["folder"])
        session.error = ""
        session.exit_code = None
        session.ended_at = None
        session.started_at = None
        session.stopping = False
        session.command = ""
        session.adb_command = ""
        session.carry.clear()
        session.target = {
            "host": host,
            "port": int(port),
            "network_id": network_id,
            "device_name": "",
        }
        self.config.mark_tool_used(tool["id"])

        network = self.config.ensure_network_port(host, int(port), network_id)
        if network:
            session.target["network_id"] = network["id"]
            entry = next(
                (item for item in network["ports"] if item["port"] == int(port)),
                None,
            )
            session.target["device_name"] = (entry or {}).get("device_name", "")

        session.status = "connecting"
        self._append(
            session,
            "meta",
            f"──── 连接 {target_serial} · scrcpy {tool['version']} ────",
        )
        self._append(session, "meta", f"工作目录：{tool['folder']}")
        self._emit_updated(session)

        settings = self.config.settings
        if not settings.get("auto_adb_connect"):
            self._start_scrcpy(session, generation)
            return

        try:
            adb_info = self.adb.require_adb(tool["id"])
        except AppError as exc:
            self._fail(session, exc.message)
            raise

        self.start_adb_connect(session, generation, adb_info, target_serial)

    def start_adb_connect(
        self,
        session: TerminalSession,
        generation: int,
        adb_info: dict[str, Any],
        target_serial: str,
    ) -> None:
        adb_command = command_line("adb.exe", ["connect", target_serial])
        session.adb_command = adb_command
        session.status = "connecting"
        self._append(session, "command", adb_command)
        process = QProcess(self)
        self._hide_console(process)
        tool = self.config.get_tool(session.tool_id)
        if tool:
            process.setWorkingDirectory(tool["folder"])
        process.setProgram(adb_info["path"])
        process.setArguments(["connect", target_serial])
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        session.adb_process = process
        chunks: list[str] = []

        def consume() -> None:
            if generation != session.generation or session.adb_process is not process:
                return
            out = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
            err = bytes(process.readAllStandardError()).decode("utf-8", errors="replace")
            if out:
                chunks.append(out)
            if err:
                chunks.append(err)
            self._append_text(session, "adb_stdout", "stdout", out)
            self._append_text(session, "adb_stderr", "stderr", err)

        def finished(code: int, _status: QProcess.ExitStatus) -> None:
            if generation != session.generation or session.adb_process is not process:
                return
            consume()
            output = "".join(chunks)
            self._flush_carry(session)
            session.adb_process = None
            success, message = evaluate_adb_connect(output)
            network_id = session.target.get("network_id") if session.target else None
            if network_id and session.target:
                self.config.record_port_attempt(
                    network_id,
                    session.target["port"],
                    success=success,
                    message=message,
                )
            if not success:
                self._fail(session, f"无法连接到 {target_serial}：{message}")
                self._append(
                    session,
                    "hint",
                    "请检查手机无线调试、IP 与端口，确保手机和电脑在同一局域网。",
                )
                self._emit_updated(session)
                return
            self._append(session, "success", f"ADB 已连接：{target_serial}")
            process.deleteLater()
            self._start_scrcpy(session, generation)

        process.finished.connect(finished)
        process.readyReadStandardOutput.connect(consume)
        process.readyReadStandardError.connect(consume)
        process.errorOccurred.connect(
            lambda error: self._on_process_error(session, generation, process, error, "ADB")
        )
        process.start()

    def _start_scrcpy(self, session: TerminalSession, generation: int) -> None:
        if generation != session.generation or not session.target:
            return
        tool = self.config.get_tool(session.tool_id)
        if not tool:
            self._fail(session, "scrcpy 版本已被移除")
            return
        settings = self.config.settings
        adb_info = self.adb.get_adb_info(tool["id"])
        adb_path = adb_info.get("path") or ""
        window_title = ""
        capability_version = tool.get("detected_version") or tool["version"]
        if supports_window_title(capability_version):
            window_title = scrcpy_window_title(
                session.target.get("device_name") or "",
                session.target_serial(),
            )
        try:
            args = build_scrcpy_args(
                session.target_serial(),
                window_title=window_title,
                extra_args=settings.get("default_args", ""),
            )
        except ValueError as exc:
            self._fail(session, str(exc))
            return

        session.command = command_line("scrcpy.exe", args)
        session.working_directory = str(tool["folder"])
        session.status = "starting"
        self._append(session, "command", session.command)
        self._append(
            session,
            "system",
            f"启动 scrcpy {tool['version']}"
            + (f" · {session.target.get('device_name')}" if session.target.get("device_name") else ""),
        )
        self._emit_updated(session)

        process = QProcess(self)
        self._hide_console(process)
        # Run from the selected version folder. Both old (1.19/1.24) and new
        # scrcpy builds find the bundled adb.exe here, so no --adb argument is
        # needed. The ADB environment variable is used only when the user has
        # explicitly selected an external ADB or the version has no adb.exe.
        process.setWorkingDirectory(tool["folder"])
        process.setProgram(tool["scrcpy_path"])
        process.setArguments(args)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        environment = QProcessEnvironment.systemEnvironment()
        bundled_adb = tool.get("adb_path") if Path(tool.get("adb_path") or "").is_file() else ""
        custom_adb = settings.get("adb_path") or ""
        fallback_adb = custom_adb if custom_adb else ("" if bundled_adb else adb_path)
        if fallback_adb:
            environment.insert("ADB", fallback_adb)
            existing_path = environment.value("PATH") or environment.value("Path")
            environment.insert(
                "PATH",
                os.pathsep.join(
                    dict.fromkeys(
                        [
                            str(Path(fallback_adb).parent),
                            *[part for part in existing_path.split(os.pathsep) if part],
                        ]
                    )
                ),
            )
        else:
            environment.remove("ADB")
        process.setProcessEnvironment(environment)
        session.process = process

        def consume() -> None:
            if generation != session.generation or session.process is not process:
                return
            out = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
            err = bytes(process.readAllStandardError()).decode("utf-8", errors="replace")
            self._append_text(session, "stdout", "stdout", out)
            self._append_text(session, "stderr", "stderr", err)

        def started() -> None:
            if generation != session.generation or session.process is not process:
                return
            session.pid = process.processId() or None
            session.status = "running"
            session.started_at = time.time()
            session.ended_at = None
            self._append(session, "success", "投屏进程已启动。")
            self._emit_updated(session)
            if session.pid and window_title:
                self._schedule_window_title(session, session.pid, window_title)

        def finished(code: int, _status: QProcess.ExitStatus) -> None:
            self._on_scrcpy_finished(session, generation, process, code)

        process.readyReadStandardOutput.connect(consume)
        process.readyReadStandardError.connect(consume)
        process.started.connect(started)
        process.finished.connect(finished)
        process.errorOccurred.connect(
            lambda error: self._on_process_error(
                session, generation, process, error, "scrcpy"
            )
        )
        process.start()

    def _schedule_window_title(
        self,
        session: TerminalSession,
        pid: int,
        title: str,
    ) -> None:
        # scrcpy 1.x appends "(serial)" after creating the window. Re-apply the
        # caption a few times to win that race across old and new versions.
        for delay in (120, 400, 900, 1600, 2800):
            QTimer.singleShot(
                delay,
                lambda p=pid, t=title: self._apply_window_title(session, p, t),
            )

    def _apply_window_title(self, session: TerminalSession, pid: int, title: str) -> None:
        if session.pid != pid or session.status != "running":
            return
        set_scrcpy_window_title(pid, title)

    def _on_process_error(
        self,
        session: TerminalSession,
        generation: int,
        process: QProcess,
        error: QProcess.ProcessError,
        label: str,
    ) -> None:
        if generation != session.generation:
            return
        if process not in (session.process, session.adb_process):
            return
        if error == QProcess.ProcessError.FailedToStart:
            if session.adb_process is process:
                session.adb_process = None
            if session.process is process:
                session.process = None
            self._fail(session, f"{label} 启动失败")
        elif error == QProcess.ProcessError.Crashed and session.status not in {"failed", "stopped"}:
            self._fail(session, f"{label} 进程异常结束")

    def _on_scrcpy_finished(
        self,
        session: TerminalSession,
        generation: int,
        process: QProcess,
        code: int,
    ) -> None:
        if generation != session.generation or session.process is not process:
            return
        self._flush_carry(session)
        session.process = None
        session.pid = None
        session.exit_code = int(code)
        session.ended_at = time.time()
        was_stopping = session.stopping or session.status == "stopping"
        session.stopping = False
        if was_stopping or code == 0:
            session.status = "stopped"
            self._append(session, "system", "scrcpy 已退出。")
        else:
            session.status = "failed"
            session.error = f"scrcpy 异常退出（代码 {code}）"
            self._append(session, "error", session.error)
        self._emit_updated(session)
        process.deleteLater()

    def _fail(self, session: TerminalSession, message: str) -> None:
        session.status = "failed"
        session.error = message
        session.ended_at = time.time()
        session.pid = None
        self._append(session, "error", message)
        self._emit_updated(session)

    # ---------------------------------------------------------------- controls

    def stop(self, terminal_id: str) -> None:
        session = self.require(terminal_id)
        if not self.is_active_id(terminal_id):
            return
        session.stopping = True
        session.status = "stopping"
        self._append(session, "system", "正在结束当前投屏进程…")
        self._emit_updated(session)
        session.generation += 1
        process, adb_process = session.process, session.adb_process
        session.process = None
        session.adb_process = None
        self._kill_process(adb_process)
        self._kill_process(process)
        self._kill_command(session, announce=False, emit=False)
        self._flush_carry(session)
        session.pid = None
        session.exit_code = None
        session.ended_at = time.time()
        session.status = "stopped"
        session.stopping = False
        self._append(session, "system", "终端已停止。可以点击重连恢复当前设备。")
        self._emit_updated(session)

    def clear(self, terminal_id: str) -> None:
        session = self.require(terminal_id)
        session.lines.clear()
        self._append(session, "system", "终端输出已清空。")
        self._emit_updated(session)

    def dismiss(self, terminal_id: str) -> None:
        session = self.require(terminal_id)
        if self.is_active_id(terminal_id):
            raise AppError("终端仍在运行，请先停止", code="TERMINAL_ACTIVE")
        self._cancel_active(session)
        try:
            if session.log_handle:
                session.log_handle.close()
        except OSError:
            pass
        self.sessions.pop(terminal_id, None)
        self.removed.emit(terminal_id)

    def open_log_path(self, terminal_id: str) -> Path:
        session = self.require(terminal_id)
        if not session.log_path or not session.log_path.is_file():
            raise AppError("这个终端还没有日志文件", code="LOG_NOT_FOUND")
        return session.log_path

    def stop_all(self) -> None:
        for session in list(self.sessions.values()):
            if session.status in {"connecting", "starting", "running", "stopping"}:
                session.generation += 1
                self._kill_process(session.adb_process)
                self._kill_process(session.process)
                session.adb_process = None
                session.process = None
            self._kill_command(session, announce=False, emit=False)
            try:
                if session.log_handle:
                    session.log_handle.close()
            except OSError:
                pass
