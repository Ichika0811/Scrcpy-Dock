"""Terminal output view and per-session page."""

from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..parsers import clean_line
from .resources import app_pixmap


class ElidedLabel(QLabel):
    """A label that elides its text instead of hard-clipping it."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802
        self._full_text = str(text or "")
        self._refresh()

    def fullText(self) -> str:  # noqa: N802
        return self._full_text

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        width = max(0, self.width() - 2)
        if width <= 0:
            super().setText(self._full_text)
            return
        elided = self.fontMetrics().elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, width
        )
        super().setText(elided)
        self.setToolTip(self._full_text if elided != self._full_text else "")



def format_clock(timestamp: float) -> str:
    try:
        return time.strftime("%H:%M:%S", time.localtime(float(timestamp)))
    except (TypeError, ValueError, OSError):
        return "--:--:--"


def format_duration(milliseconds: float) -> str:
    total = max(0, int(milliseconds / 1000))
    hours, rest = divmod(total, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


_KIND_MARKERS = {
    "command": "❯",
    "stderr": "!",
    "success": "✓",
    "error": "×",
    "system": "·",
    "meta": "─",
    "hint": "?",
    "stdout": "›",
}
_KIND_COLORS = {
    "command": "#d7ebe7",
    "stderr": "#d6b4bb",
    "success": "#84cba8",
    "error": "#ff9da9",
    "system": "#74889e",
    "meta": "#5c7086",
    "hint": "#c0a15f",
    "stdout": "#b5c2d2",
}
_PREFIX_COLORS = {
    "command": "#5eead4",
    "stderr": "#b46d7a",
    "success": "#4ade80",
    "error": "#fb7185",
    "system": "#526176",
    "meta": "#4f6278",
    "hint": "#fbbf24",
    "stdout": "#4b5d72",
}


class TerminalConsole(QTextEdit):
    interrupt_requested = Signal()
    paste_requested = Signal()
    clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Console")
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document().setDocumentMargin(0)
        self.document().setMaximumBlockCount(5000)
        font = QFont()
        font.setFamilies(["Cascadia Mono", "Cascadia Code", "Consolas", "Courier New"])
        font.setPointSizeF(9.4)
        self.document().setDefaultFont(font)
        self.setFont(font)
        self._max_lines = 5000
        self._line_count = 0

    def set_max_lines(self, value: int) -> None:
        self._max_lines = max(500, min(20000, int(value)))
        self.document().setMaximumBlockCount(self._max_lines)

    def line_count(self) -> int:
        return self._line_count

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        modifiers = event.modifiers()
        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        if ctrl and shift and key == Qt.Key.Key_C:
            self.copy()
            event.accept()
            return
        if ctrl and key == Qt.Key.Key_C:
            if self.textCursor().hasSelection():
                super().keyPressEvent(event)
            else:
                self.interrupt_requested.emit()
                event.accept()
            return
        if ctrl and key == Qt.Key.Key_V:
            self.paste_requested.emit()
            event.accept()
            return
        if ctrl and key == Qt.Key.Key_L:
            self.clear_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def clear_console(self) -> None:
        self.clear()
        self._line_count = 0

    def append_line(
        self,
        kind: str,
        text: str,
        timestamp: float | None = None,
        *,
        autoscroll: bool = True,
    ) -> None:
        kind = kind if kind in _KIND_MARKERS else "stdout"
        bar = self.verticalScrollBar()
        at_bottom = bar.maximum() - bar.value() <= 4
        first = self._line_count == 0

        cursor = QTextCursor(self.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if self.document().characterCount() > 1:
            cursor.insertBlock()

        time_format = QTextCharFormat()
        time_format.setForeground(QColor("#38465a"))
        time_format.setFontPointSize(7.4)
        cursor.insertText(f"{format_clock(timestamp or time.time())}  ", time_format)

        prefix_format = QTextCharFormat()
        prefix_format.setForeground(QColor(_PREFIX_COLORS[kind]))
        prefix_format.setFontPointSize(8.0)
        cursor.insertText(f"{_KIND_MARKERS[kind]} ", prefix_format)

        text_format = QTextCharFormat()
        text_format.setForeground(QColor(_KIND_COLORS[kind]))
        if kind in {"meta", "system", "hint"}:
            text_format.setFontPointSize(8.2)
        cursor.insertText(clean_line(text) or " ", text_format)

        self._line_count += 1
        if self._line_count > self._max_lines:
            self._line_count = self._max_lines
        if autoscroll and (at_bottom or first):
            bar.setValue(bar.maximum())

    def append_lines(self, lines: list[dict[str, Any]]) -> None:
        bar = self.verticalScrollBar()
        at_bottom = bar.maximum() - bar.value() <= 4
        for line in lines:
            self.append_line(
                line.get("kind", "stdout"),
                line.get("text", ""),
                line.get("ts"),
                autoscroll=False,
            )
        if at_bottom:
            bar.setValue(bar.maximum())


class TerminalCommandEdit(QLineEdit):
    submitted = Signal(str)
    interrupt_requested = Signal()
    copy_requested = Signal()
    clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setClearButtonEnabled(True)
        self.setPlaceholderText("输入命令，Enter 执行 · ↑↓ 历史 · Ctrl+C 终止")
        self._history: list[str] = []
        self._history_index = 0

    def submit(self) -> None:
        command = self.text().strip()
        if command:
            self.remember(command)
            self.clear()
            self.submitted.emit(command)
        self.setFocus()

    def remember(self, command: str) -> None:
        if command and (not self._history or self._history[-1] != command):
            self._history.append(command)
            self._history = self._history[-100:]
        self._history_index = len(self._history)

    def _history_move(self, delta: int) -> None:
        if not self._history:
            return
        self._history_index = max(
            0,
            min(len(self._history), self._history_index + delta),
        )
        if self._history_index >= len(self._history):
            self.clear()
        else:
            self.setText(self._history[self._history_index])
            self.setCursorPosition(len(self.text()))

    def _paste_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        if not text:
            return
        lines = [
            line.strip()
            for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
            if line.strip()
        ]
        if lines:
            self.insert(lines[0])

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        modifiers = event.modifiers()
        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.submit()
            event.accept()
            return
        if key == Qt.Key.Key_Up:
            self._history_move(-1)
            event.accept()
            return
        if key == Qt.Key.Key_Down:
            self._history_move(1)
            event.accept()
            return
        if (ctrl and key == Qt.Key.Key_V) or (
            shift and key == Qt.Key.Key_Insert
        ):
            self._paste_clipboard()
            event.accept()
            return
        if ctrl and shift and key == Qt.Key.Key_C:
            self.copy_requested.emit()
            event.accept()
            return
        if ctrl and key == Qt.Key.Key_C:
            self.clear()
            self.interrupt_requested.emit()
            event.accept()
            return
        if ctrl and key == Qt.Key.Key_L:
            self.clear_requested.emit()
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            self.clear()
            event.accept()
            return
        super().keyPressEvent(event)


class TerminalPanel(QWidget):
    action_requested = Signal(str, str)  # terminal_id, action
    command_requested = Signal(str, str)  # terminal_id, command
    interrupt_requested = Signal(str)

    STATUS_LABELS = {
        "idle": "就绪",
        "connecting": "正在连接",
        "starting": "正在启动",
        "running": "运行中",
        "stopping": "正在停止",
        "stopped": "已停止",
        "failed": "连接失败",
    }

    def __init__(self, terminal_id: str, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.terminal_id = terminal_id
        self.index = index
        self.snapshot: dict[str, Any] = {}
        self._started_at: float | None = None
        self._ended_at: float | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 9, 10, 10)
        root.setSpacing(0)

        self.shell = QFrame()
        self.shell.setObjectName("TerminalShell")
        root.addWidget(self.shell)

        shell_layout = QVBoxLayout(self.shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        self.header = QFrame()
        self.header.setObjectName("TerminalHeader")
        self.header.setFixedHeight(56)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(11, 7, 8, 7)
        header_layout.setSpacing(8)
        shell_layout.addWidget(self.header)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("TerminalIcon")
        self.icon_label.setFixedSize(32, 32)
        self.icon_label.setPixmap(app_pixmap(32))
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.icon_label)

        title_block = QWidget()
        title_layout = QVBoxLayout(title_block)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)
        self.title_row = QHBoxLayout()
        self.title_row.setSpacing(7)
        self.title_label = ElidedLabel("新终端")
        self.title_label.setObjectName("TerminalTitle")
        self.version_label = QLabel("未选择版本")
        self.version_label.setProperty("role", "versionPill")
        self.title_row.addWidget(self.title_label, 1)
        self.title_row.addWidget(self.version_label, 0)
        self.title_row.addStretch(0)
        title_layout.addLayout(self.title_row)

        sub_row = QHBoxLayout()
        sub_row.setSpacing(6)
        self.sub_label = QLabel("未连接设备")
        self.sub_label.setObjectName("TerminalSub")
        self.sub_sep = QLabel("·")
        self.sub_sep.setObjectName("TerminalSub")
        self.device_label = ElidedLabel("等待右侧端口")
        self.device_label.setObjectName("TerminalSub")
        self.adb_label = QLabel("ADB 自动连接")
        self.adb_label.setObjectName("TerminalSub")
        self.adb_label.hide()
        sub_row.addWidget(self.sub_label, 0)
        sub_row.addWidget(self.sub_sep, 0)
        sub_row.addWidget(self.device_label, 1)
        title_layout.addLayout(sub_row)
        header_layout.addWidget(title_block, 1)

        self.status_pill = QLabel("就绪")
        self.status_pill.setObjectName("StatusPill")
        self.status_pill.setProperty("state", "idle")
        header_layout.addWidget(self.status_pill, 0, Qt.AlignmentFlag.AlignVCenter)

        self.copy_button = self._make_action("⧉", "copy", "复制当前命令")
        self.clear_button = self._make_action("⌫", "clear", "清空终端输出")
        self.log_button = self._make_action("≡", "log", "打开终端日志")
        self.stop_button = self._make_action("■", "stop", "停止当前投屏", danger=True)
        self.reconnect_button = self._make_action("▶", "reconnect", "重新连接当前设备")
        header_layout.addWidget(self.copy_button)
        header_layout.addWidget(self.clear_button)
        header_layout.addWidget(self.log_button)
        header_layout.addWidget(self.stop_button)
        header_layout.addWidget(self.reconnect_button)

        self.stack = QStackedWidget()
        shell_layout.addWidget(self.stack, 1)

        self.idle_page = self._build_idle()
        self.console_page = QWidget()
        console_layout = QVBoxLayout(self.console_page)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(0)

        self.progress_banner = QFrame()
        self.progress_banner.setObjectName("ProgressBanner")
        progress_layout = QHBoxLayout(self.progress_banner)
        progress_layout.setContentsMargins(9, 5, 9, 5)
        self.progress_label = QLabel("正在连接…")
        self.progress_label.setObjectName("ProgressText")
        progress_layout.addWidget(self.progress_label)
        self.progress_banner.hide()
        console_layout.addWidget(self.progress_banner)
        self.progress_banner.setContentsMargins(10, 7, 10, 0)

        self.error_banner = QFrame()
        self.error_banner.setObjectName("ErrorBanner")
        error_layout = QHBoxLayout(self.error_banner)
        error_layout.setContentsMargins(9, 6, 9, 6)
        self.error_icon = QLabel("⚠")
        self.error_icon.setObjectName("ErrorText")
        self.error_text = QLabel("")
        self.error_text.setObjectName("ErrorText")
        self.error_text.setWordWrap(True)
        error_layout.addWidget(self.error_icon, 0, Qt.AlignmentFlag.AlignTop)
        error_layout.addWidget(self.error_text, 1)
        self.error_banner.hide()
        console_layout.addWidget(self.error_banner)
        self.error_banner.setContentsMargins(10, 7, 10, 0)

        self.console = TerminalConsole()
        self.console.interrupt_requested.connect(
            lambda: self.interrupt_requested.emit(self.terminal_id)
        )
        self.console.paste_requested.connect(self._paste_to_command)
        self.console.clear_requested.connect(
            lambda: self.action_requested.emit(self.terminal_id, "clear")
        )
        console_layout.addWidget(self.console, 1)

        self.command_bar = QFrame()
        self.command_bar.setObjectName("CommandBar")
        command_layout = QHBoxLayout(self.command_bar)
        command_layout.setContentsMargins(11, 4, 8, 4)
        command_layout.setSpacing(7)
        prompt = QLabel("❯")
        prompt.setObjectName("CommandPrompt")
        self.command_text = TerminalCommandEdit()
        self.command_text.setObjectName("CommandText")
        self.command_text.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.command_text.setToolTip(
            "Enter 执行 · ↑↓ 历史 · Ctrl+C 终止 · Ctrl+Shift+C 复制选中"
        )
        self.command_text.submitted.connect(self._submit_command)
        self.command_text.interrupt_requested.connect(
            lambda: self.interrupt_requested.emit(self.terminal_id)
        )
        self.command_text.copy_requested.connect(self._copy_console_selection)
        self.command_text.clear_requested.connect(
            lambda: self.action_requested.emit(self.terminal_id, "clear")
        )
        command_send = QPushButton("▶")
        command_send.setProperty("kind", "favorite")
        command_send.setToolTip("运行命令（Enter）")
        command_send.clicked.connect(self.command_text.submit)
        command_copy = QPushButton("⧉")
        command_copy.setProperty("kind", "favorite")
        command_copy.setToolTip("复制上次投屏命令")
        command_copy.clicked.connect(lambda: self.action_requested.emit(self.terminal_id, "copy"))
        command_layout.addWidget(prompt)
        command_layout.addWidget(self.command_text, 1)
        command_layout.addWidget(command_send)
        command_layout.addWidget(command_copy)
        console_layout.addWidget(self.command_bar)
        self._last_command = ""

        self.footer = QFrame()
        self.footer.setObjectName("TerminalFooter")
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(11, 4, 11, 4)
        footer_layout.setSpacing(9)
        self.footer_pid = QLabel("PID —")
        self.footer_version = QLabel("未选择版本")
        self.footer_target = QLabel("—")
        self.footer_elapsed = QLabel("00:00")
        self.footer_lines = QLabel("0 行")
        for label in (
            self.footer_pid,
            self.footer_version,
            self.footer_target,
            self.footer_elapsed,
            self.footer_lines,
        ):
            label.setObjectName("TerminalFooterText")
            footer_layout.addWidget(label)
        footer_layout.addStretch(1)
        self.footer_log = QLabel("日志自动保存")
        self.footer_log.setObjectName("TerminalFooterText")
        footer_layout.addWidget(self.footer_log)
        console_layout.addWidget(self.footer)

        self.stack.addWidget(self.idle_page)
        self.stack.addWidget(self.console_page)
        self.stack.setCurrentWidget(self.idle_page)

        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.timeout.connect(self._tick)
        self.elapsed_timer.start(1000)
        self._has_tools = False
        self._has_networks = False
        self._has_connectable = False

    def _submit_command(self, command: str) -> None:
        command = str(command or "").strip()
        if not command:
            return
        self.command_requested.emit(self.terminal_id, command)
        self.command_text.setFocus()

    def _paste_to_command(self) -> None:
        text = QApplication.clipboard().text()
        if not text:
            return
        lines = [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines() if line.strip()]
        if not lines:
            return
        # The input is intentionally one line; pasting a snippet keeps its first
        # non-empty command and leaves the user in control of the rest.
        self.command_text.setFocus()
        self.command_text.insert(lines[0])

    def _copy_console_selection(self) -> None:
        if self.console.textCursor().hasSelection():
            self.console.copy()

    def _make_action(
        self, text: str, action: str, tooltip: str, *, danger: bool = False
    ) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("kind", "termDanger" if danger else "term")
        button.setFixedSize(27, 27)
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda: self.action_requested.emit(self.terminal_id, action))
        return button

    def _build_idle(self) -> QWidget:
        page = QWidget()
        page.setObjectName("IdlePanel")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 24, 30, 26)
        layout.setSpacing(8)
        layout.addStretch(1)

        icon_label = QLabel()
        icon_label.setObjectName("IdleIcon")
        icon_label.setFixedSize(62, 62)
        icon_label.setPixmap(app_pixmap(62))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("准备开始投屏")
        title.setObjectName("IdleTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        text = QLabel(
            "左侧选择 scrcpy 版本，右侧点击任意 IP 端口。\n"
            "终端会自动执行 ADB 连接，并在下方打印完整 scrcpy 命令与输出。"
        )
        text.setObjectName("IdleText")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text)

        steps = QHBoxLayout()
        steps.setSpacing(7)
        steps.addStretch(1)
        for index, caption in (
            ("1", "选择 scrcpy 版本"),
            ("2", "展开右侧 IP"),
            ("3", "点击端口一键连接"),
        ):
            card = QFrame()
            card.setObjectName("IdleStep")
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(8, 6, 8, 6)
            card_layout.setSpacing(6)
            number = QLabel(index)
            number.setObjectName("IdleStepIndex")
            number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label = QLabel(caption)
            label.setObjectName("IdleStepText")
            card_layout.addWidget(number)
            card_layout.addWidget(label)
            steps.addWidget(card)
        steps.addStretch(1)
        layout.addLayout(steps)

        actions = QHBoxLayout()
        actions.setSpacing(7)
        actions.addStretch(1)
        self.idle_primary = QPushButton("添加 scrcpy 版本")
        self.idle_primary.setProperty("kind", "primary")
        self.idle_primary.clicked.connect(
            lambda: self.action_requested.emit(self.terminal_id, "idle_primary")
        )
        self.idle_secondary = QPushButton("添加设备 IP")
        self.idle_secondary.setProperty("kind", "ghost")
        self.idle_secondary.clicked.connect(
            lambda: self.action_requested.emit(self.terminal_id, "add_network")
        )
        actions.addWidget(self.idle_primary)
        actions.addWidget(self.idle_secondary)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)
        return page

    def set_idle_context(self, *, has_tools: bool, has_networks: bool, has_connectable: bool) -> None:
        self._has_tools = has_tools
        self._has_networks = has_networks
        self._has_connectable = has_connectable
        if not has_tools:
            self.idle_primary.setText("＋ 添加 scrcpy 版本")
            self.idle_primary.setVisible(True)
            self.idle_secondary.setText("添加设备 IP")
            self.idle_secondary.setVisible(False)
        elif not has_networks:
            self.idle_primary.setText("＋ 添加设备 IP")
            self.idle_primary.setVisible(True)
            self.idle_secondary.setText("添加 scrcpy 版本")
            self.idle_secondary.setVisible(True)
        elif has_connectable:
            self.idle_primary.setText("▶ 连接第一个端口")
            self.idle_primary.setVisible(True)
            self.idle_secondary.setText("添加 scrcpy 版本")
            self.idle_secondary.setVisible(True)
        else:
            self.idle_primary.setText("⟳ 去右侧扫描端口")
            self.idle_primary.setVisible(True)
            self.idle_secondary.setText("添加 scrcpy 版本")
            self.idle_secondary.setVisible(True)

    def update_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.snapshot = snapshot
        target = snapshot.get("target")
        status = snapshot.get("status", "idle")
        version = snapshot.get("tool_version") or "未选择版本"
        version_text = (
            "未选择版本"
            if version == "未选择版本"
            else version
            if version.startswith("scrcpy")
            else f"scrcpy {version}"
        )
        self.version_label.setText(version_text)
        if snapshot.get("tool_id") and snapshot.get("tool_available") is False:
            self.version_label.setText(f"{version_text} · 路径失效")

        if target:
            self.title_label.setText(
                target.get("network_label")
                or target.get("device_name")
                or target.get("host")
                or f"终端 {self.index}"
            )
            self.sub_label.setText(f"终端 {self.index}")
            self.sub_sep.setVisible(True)
            self.device_label.setText(target.get("serial") or "")
            self.adb_label.setText(
                "ADB 自动连接"
                if self.snapshot.get("_auto_adb", True)
                else "ADB 自动连接关闭"
            )
            self.stack.setCurrentWidget(self.console_page)
        else:
            self.title_label.setText(f"终端 {self.index}")
            self.sub_label.setText("未连接设备")
            self.sub_sep.setVisible(False)
            self.device_label.setText("等待右侧端口")
            self.adb_label.setText("")
            self.stack.setCurrentWidget(self.idle_page)

        self.status_pill.setText(self.STATUS_LABELS.get(status, status))
        self.status_pill.setProperty("state", status)
        self._repolish(self.status_pill)

        active = status in {"connecting", "starting", "running", "stopping"}
        stopped = status in {"stopped", "failed"}
        self.copy_button.setVisible(bool(target))
        self.copy_button.setEnabled(bool(snapshot.get("command")))
        self.clear_button.setVisible(bool(target))
        self.stop_button.setVisible(active)
        self.stop_button.setEnabled(status != "stopping")
        self.reconnect_button.setVisible(bool(stopped and target))

        self._last_command = snapshot.get("command") or ""
        cwd = snapshot.get("shell_cwd") or snapshot.get("working_directory") or ""
        command_running = bool(snapshot.get("command_running"))
        if command_running:
            self.command_text.setPlaceholderText("命令运行中 · Ctrl+C 中断")
        else:
            self.command_text.setPlaceholderText(
                "输入命令，Enter 执行 · ↑↓ 历史 · Ctrl+C 终止"
            )
        tooltip = [
            "Enter 执行 · ↑↓ 历史 · Ctrl+C 终止 · Ctrl+Shift+C 复制选中",
        ]
        if cwd:
            tooltip.append(f"工作目录：{cwd}")
        if self._last_command:
            tooltip.append(f"上次投屏命令：{self._last_command}")
        self.command_text.setToolTip("\n".join(tooltip))

        self._started_at = snapshot.get("started_at")
        self._ended_at = snapshot.get("ended_at")
        self.footer_pid.setText(f"PID {snapshot.get('pid') or '—'}")
        self.footer_version.setText(version_text)
        self.footer_target.setText(target.get("serial") if target else "—")
        self.footer_lines.setText(f"{snapshot.get('line_count', 0)} 行")
        self.footer_log.setText("日志自动保存" if snapshot.get("log_path") else "日志未保存")

        if status in {"connecting", "starting", "stopping"}:
            self.progress_banner.show()
            self.progress_label.setText(
                {
                    "connecting": "正在执行 ADB 连接并准备 scrcpy 命令…",
                    "starting": "scrcpy 正在启动…",
                    "stopping": "正在结束投屏进程…",
                }[status]
            )
        else:
            self.progress_banner.hide()

        if status == "failed" and snapshot.get("error"):
            self.error_banner.show()
            self.error_text.setText(snapshot["error"])
        else:
            self.error_banner.hide()
        self._tick()

    def append_lines(self, lines: list[dict[str, Any]]) -> None:
        if not lines:
            return
        self.console.append_lines(lines)
        self.footer_lines.setText(f"{self.console.line_count()} 行")

    def clear_console(self) -> None:
        self.console.clear_console()
        self.footer_lines.setText("0 行")

    def set_max_lines(self, value: int) -> None:
        self.console.set_max_lines(value)

    def _tick(self) -> None:
        if not self._started_at:
            self.footer_elapsed.setText("00:00")
            return
        end = self._ended_at or time.time()
        self.footer_elapsed.setText(format_duration((float(end) - float(self._started_at)) * 1000))

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()
