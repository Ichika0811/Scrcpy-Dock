"""Main three-column Scrcpy Dock window."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import platform
from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QObject, QPoint, QRect, QSize, QTimer, Qt, QUrl, Signal, Slot, qVersion
from PySide6.QtGui import (
    QColor,
    QCloseEvent,
    QDesktopServices,
    QIcon,
    QKeySequence,
    QPixmap,
    QShortcut,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import ConfigStore, TOOL_COLOR_PALETTE
from ..errors import AppError
from ..parsers import is_valid_port
from ..services.adb import AdbService
from ..services.docker_ports import discover_docker_ports
from ..services.scanner import scan_ports
from ..services.terminals import TerminalManager
from ..services.tools import inspect_tool_folder, inspect_tool_parent, rescan_tool
from .. import __version__
from .console import TerminalPanel
from .dialogs import (
    AboutDialog,
    AddNetworkDialog,
    AddPortDialog,
    BusyDialog,
    ConfirmDialog,
    EditNetworkDialog,
    NetworkSettingsDialog,
    ToolSettingsDialog,
    VersionDialog,
)
from .native import apply_dark_titlebar
from .rails import ClickableFrame, NetworkCard, ToolCard, display_version, make_label, repolish
from .resources import app_icon, app_pixmap
from .tabs import TabScrollArea, TerminalTab


class _TaskSignals(QObject):
    """Queued relay from Python worker threads back to the Qt main thread."""

    result = Signal(int, object)
    failed = Signal(int, object)
    finished = Signal(int)


class ToastFrame(QFrame):
    def __init__(
        self,
        parent: QWidget,
        kind: str,
        title: str,
        message: str,
        closer: Callable[["ToastFrame"], None],
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setProperty("kind", kind)
        self.setFixedWidth(360)
        self._closer = closer
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 9, 8, 9)
        layout.setSpacing(8)
        glyph = {"error": "⚠", "warning": "⚠", "success": "✓"}.get(kind, "ⓘ")
        icon = QLabel(glyph)
        icon.setObjectName("ToastIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        copy = QVBoxLayout()
        copy.setSpacing(1)
        if title:
            copy.addWidget(make_label(title, object_name="ToastTitle"))
        text = make_label(message, object_name="ToastText", word_wrap=True)
        copy.addWidget(text)
        layout.addLayout(copy, 1)
        close = QPushButton("✕")
        close.setProperty("kind", "favorite")
        close.setFixedSize(17, 17)
        close.clicked.connect(lambda: self._closer(self))
        layout.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        self.adjustSize()


class MainWindow(QMainWindow):
    def __init__(self, config: ConfigStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.adb = AdbService(config)
        self.manager = TerminalManager(config, self.adb, self)

        self.active_terminal_id: str | None = None
        self.pages: dict[str, TerminalPanel] = {}
        self.expanded_networks: set[str] = set()
        self.scanning_networks: set[str] = set()
        self.devices: list[dict[str, Any]] = []
        self.devices_error: str = ""
        self.device_task: int | None = None
        self.status_cache: dict[str, str] = {}
        self.tasks: dict[int, dict[str, Any]] = {}
        self._task_seq = 0
        self.toasts: list[ToastFrame] = []
        self.tool_settings_dialog: ToolSettingsDialog | None = None
        self._closing = False
        self.task_signals = _TaskSignals(self)
        self.task_signals.result.connect(self._task_result)
        self.task_signals.failed.connect(self._task_failure)
        self.task_signals.finished.connect(self._task_finished)

        self.setWindowTitle("Scrcpy Dock")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(940, 620)

        self._build_ui()
        self._bind_manager()
        self._bind_shortcuts()
        self._restore_geometry()

        self.device_timer = QTimer(self)
        self.device_timer.timeout.connect(lambda: self.refresh_devices(silent=True))
        self.device_timer.start(7000)
        QTimer.singleShot(100, lambda: self.refresh_devices(silent=True))
        QTimer.singleShot(0, self._ensure_initial_terminal)

    # ------------------------------------------------------------------- UI

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("Root")
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.tool_rail, self.tool_scroll_content, self.tool_scroll = self._build_tool_rail()
        self.terminal_workspace = self._build_terminal_workspace()
        self.network_rail, self.network_scroll_content, self.network_scroll = (
            self._build_network_rail()
        )
        root_layout.addWidget(self.tool_rail)
        root_layout.addWidget(self.terminal_workspace, 1)
        root_layout.addWidget(self.network_rail)
        self._bind_rail_contexts()

    def _build_tool_rail(self) -> tuple[QWidget, QWidget, QScrollArea]:
        rail = QWidget()
        rail.setObjectName("RailLeft")
        rail.setFixedWidth(252)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("RailHeader")
        header.setFixedHeight(66)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(11, 10, 11, 8)
        header_layout.setSpacing(9)
        settings = QPushButton("⚙")
        settings.setProperty("kind", "icon")
        settings.setToolTip("scrcpy 版本设置")
        settings.setCursor(Qt.CursorShape.PointingHandCursor)
        settings.clicked.connect(self.open_tool_settings)
        header_layout.addWidget(settings, 0, Qt.AlignmentFlag.AlignTop)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.addWidget(make_label("VERSIONS", role="eyebrow"))
        title_row = QHBoxLayout()
        title_row.setSpacing(5)
        title_row.addWidget(make_label("scrcpy 版本", role="railTitle"))
        self.tool_count = make_label("0", role="countBadge")
        title_row.addWidget(self.tool_count)
        title_row.addStretch(1)
        title_box.addLayout(title_row)
        header_layout.addLayout(title_box, 1)
        add = QPushButton("＋")
        add.setProperty("kind", "add")
        add.setToolTip("添加 scrcpy 版本")
        add.setCursor(Qt.CursorShape.PointingHandCursor)
        add.clicked.connect(self.add_tool)
        header_layout.addWidget(add, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(header)

        caption = QWidget()
        caption.setObjectName("RailCaption")
        caption.setFixedHeight(27)
        caption_layout = QHBoxLayout(caption)
        caption_layout.setContentsMargins(13, 0, 13, 0)
        caption_layout.setSpacing(6)
        dot = QLabel("●")
        dot.setStyleSheet("color:#5eead4; font-size:5px;")
        caption_layout.addWidget(dot)
        self.tool_caption = make_label("只作用于当前终端", role="caption")
        caption_layout.addWidget(self.tool_caption)
        caption_layout.addStretch(1)
        layout.addWidget(caption)

        scroll = QScrollArea()
        scroll.setObjectName("RailScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(7, 5, 7, 12)
        content_layout.setSpacing(2)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        footer = QWidget()
        footer.setObjectName("RailFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(10, 8, 10, 9)
        footer_layout.setSpacing(6)
        hint = make_label("ⓘ  右键空白处添加或设置", role="faint")
        hint.setStyleSheet("font-size:8px; color:#46566a;")
        footer_layout.addWidget(hint)
        adb_pill = ClickableFrame()
        adb_pill.setObjectName("AdbPill")
        adb_pill.setCursor(Qt.CursorShape.PointingHandCursor)
        adb_pill.clicked.connect(self.open_network_settings)
        adb_layout = QHBoxLayout(adb_pill)
        adb_layout.setContentsMargins(8, 6, 8, 6)
        adb_layout.setSpacing(7)
        self.adb_dot = QLabel()
        self.adb_dot.setObjectName("StatusDot")
        self.adb_dot.setProperty("state", "idle")
        adb_layout.addWidget(self.adb_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        adb_copy = QVBoxLayout()
        adb_copy.setSpacing(1)
        self.adb_label = make_label("ADB 检测中", role="faint")
        self.adb_label.setStyleSheet("font-size:9px;color:#9aabbe;")
        self.adb_source = make_label("—", role="faint")
        self.adb_source.setStyleSheet("font-size:7px;color:#4b5b70;")
        adb_copy.addWidget(self.adb_label)
        adb_copy.addWidget(self.adb_source)
        adb_layout.addLayout(adb_copy, 1)
        arrow = make_label("›", role="faint")
        adb_layout.addWidget(arrow)
        footer_layout.addWidget(adb_pill)
        self.about_button = QPushButton(f"关于 Scrcpy Dock   v{__version__}")
        self.about_button.setProperty("kind", "link")
        self.about_button.setIcon(app_icon())
        self.about_button.setIconSize(QSize(14, 14))
        self.about_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.about_button.setToolTip("版本、运行环境与数据路径（F1）")
        self.about_button.clicked.connect(self.open_about)
        footer_layout.addWidget(self.about_button)
        layout.addWidget(footer)
        return rail, content, scroll

    def _build_terminal_workspace(self) -> QWidget:
        workspace = QWidget()
        workspace.setObjectName("TerminalWorkspace")
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tabbar = QWidget()
        tabbar.setObjectName("TabBar")
        tabbar.setFixedHeight(48)
        tab_layout = QHBoxLayout(tabbar)
        tab_layout.setContentsMargins(6, 6, 8, 0)
        tab_layout.setSpacing(5)
        self.tab_scroll = TabScrollArea()
        tab_content = QWidget()
        self.tab_content = tab_content
        self.tab_layout = QHBoxLayout(tab_content)
        self.tab_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_layout.setSpacing(4)
        self.tab_layout.addStretch(1)
        self.tab_scroll.setWidget(tab_content)
        tab_layout.addWidget(self.tab_scroll, 1)
        plus = QPushButton("＋")
        plus.setProperty("kind", "tabAdd")
        plus.setToolTip("新建终端")
        plus.setCursor(Qt.CursorShape.PointingHandCursor)
        plus.clicked.connect(self.create_terminal)
        tab_layout.addWidget(plus, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(tabbar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.empty_page = self._build_empty_page()
        self.stack.addWidget(self.empty_page)
        self.stack.setCurrentWidget(self.empty_page)
        return workspace

    def _build_empty_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.addStretch(1)
        icon = QLabel()
        icon.setObjectName("IdleIcon")
        icon.setFixedSize(62, 62)
        icon.setPixmap(app_pixmap(62))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)
        title = QLabel("打开一个终端")
        title.setObjectName("IdleTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        text = QLabel(
            "每个终端独立绑定 scrcpy 版本与设备。\n左侧和右侧栏都只作用于当前显示的终端。"
        )
        text.setObjectName("IdleText")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text)
        button = QPushButton("＋ 新建终端")
        button.setProperty("kind", "primary")
        button.clicked.connect(self.create_terminal)
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        return page

    def _build_network_rail(self) -> tuple[QWidget, QWidget, QScrollArea]:
        rail = QWidget()
        rail.setObjectName("RailRight")
        rail.setFixedWidth(306)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("RailHeader")
        header.setFixedHeight(66)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(11, 10, 11, 8)
        header_layout.setSpacing(9)
        settings = QPushButton("⚙")
        settings.setProperty("kind", "icon")
        settings.setToolTip("IP 与 ADB 设置")
        settings.setCursor(Qt.CursorShape.PointingHandCursor)
        settings.clicked.connect(self.open_network_settings)
        header_layout.addWidget(settings, 0, Qt.AlignmentFlag.AlignTop)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.addWidget(make_label("DEVICES", role="eyebrow"))
        title_row = QHBoxLayout()
        title_row.setSpacing(5)
        title_row.addWidget(make_label("IP / 设备", role="railTitle"))
        self.network_count = make_label("0", role="countBadge")
        title_row.addWidget(self.network_count)
        title_row.addStretch(1)
        title_box.addLayout(title_row)
        header_layout.addLayout(title_box, 1)
        add = QPushButton("＋")
        add.setProperty("kind", "add")
        add.setToolTip("添加 IP")
        add.setCursor(Qt.CursorShape.PointingHandCursor)
        add.clicked.connect(self.add_network)
        header_layout.addWidget(add, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(header)

        caption = QWidget()
        caption.setObjectName("RailCaption")
        caption.setFixedHeight(27)
        caption_layout = QHBoxLayout(caption)
        caption_layout.setContentsMargins(13, 0, 13, 0)
        caption_layout.setSpacing(6)
        dot = QLabel("●")
        dot.setStyleSheet("color:#78a9ff; font-size:5px;")
        caption_layout.addWidget(dot)
        caption_layout.addWidget(make_label("点击端口，一键连接到当前终端", role="caption"))
        caption_layout.addStretch(1)
        layout.addWidget(caption)

        scroll = QScrollArea()
        scroll.setObjectName("RailScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(7, 5, 7, 12)
        content_layout.setSpacing(2)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        footer = QWidget()
        footer.setObjectName("RailFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(10, 8, 10, 9)
        footer_layout.setSpacing(5)
        count_row = QHBoxLayout()
        count_row.setSpacing(5)
        self.device_footer = make_label("0 台 ADB 设备", role="faint")
        self.device_footer.setStyleSheet("font-size:8px;color:#4e5f74;")
        count_row.addWidget(self.device_footer, 1)
        refresh = QPushButton("⟳")
        refresh.setProperty("kind", "favorite")
        refresh.setFixedSize(20, 20)
        refresh.setToolTip("刷新 ADB 设备与名称")
        refresh.clicked.connect(lambda: self.refresh_devices(silent=False))
        count_row.addWidget(refresh)
        footer_layout.addLayout(count_row)
        hint = make_label("ⓘ  右键 IP 或空白处设置", role="faint")
        hint.setStyleSheet("font-size:8px; color:#46566a;")
        footer_layout.addWidget(hint)
        layout.addWidget(footer)
        return rail, content, scroll

    def _bind_manager(self) -> None:
        self.manager.created.connect(self._terminal_created)
        self.manager.updated.connect(self._terminal_updated)
        self.manager.output.connect(self._terminal_output)
        self.manager.removed.connect(self._terminal_removed)

    def _bind_shortcuts(self) -> None:
        shortcuts = (
            (QKeySequence("Ctrl+N"), self.create_terminal),
            (QKeySequence("Ctrl+,"), self.open_network_settings),
            (QKeySequence("Ctrl+Tab"), self._next_terminal),
            (QKeySequence("Ctrl+Shift+Tab"), self._previous_terminal),
            (QKeySequence("F1"), self.open_about),
        )
        for sequence, slot in shortcuts:
            shortcut = QShortcut(sequence, self)
            shortcut.activated.connect(slot)

    def _bind_rail_contexts(self) -> None:
        tool_widgets = [
            self.tool_rail,
            self.tool_scroll,
            self.tool_scroll.viewport(),
            self.tool_scroll_content,
        ]
        tool_widgets.extend(
            child
            for child in self.tool_rail.findChildren(QWidget)
            if child.objectName() in {"RailHeader", "RailCaption", "RailFooter"}
        )
        for widget in tool_widgets:
            widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            widget.customContextMenuRequested.connect(
                lambda pos, source=widget: self._tool_rail_menu(source.mapToGlobal(pos))
            )
        network_widgets = [
            self.network_rail,
            self.network_scroll,
            self.network_scroll.viewport(),
            self.network_scroll_content,
        ]
        network_widgets.extend(
            child
            for child in self.network_rail.findChildren(QWidget)
            if child.objectName() in {"RailHeader", "RailCaption", "RailFooter"}
        )
        for widget in network_widgets:
            widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            widget.customContextMenuRequested.connect(
                lambda pos, source=widget: self._network_rail_menu(source.mapToGlobal(pos))
            )
        self.tab_content.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab_content.customContextMenuRequested.connect(
            lambda pos: self._tab_empty_menu(self.tab_content.mapToGlobal(pos))
        )

    # --------------------------------------------------------------- geometry

    def _restore_geometry(self) -> None:
        saved = self.config.window_state
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        width = int(saved.get("width", 1280))
        height = int(saved.get("height", 820))
        if available:
            width = min(width, max(940, available.width() - 32))
            height = min(height, max(620, available.height() - 48))
        self.resize(width, height)
        x, y = saved.get("x"), saved.get("y")
        if isinstance(x, int) and isinstance(y, int):
            saved_rect = QRect(x, y, width, height)
            if any(
                screen.availableGeometry().intersects(saved_rect)
                for screen in QApplication.screens()
            ):
                self.move(x, y)
        elif available:
            self.move(
                available.x() + max(0, (available.width() - width) // 2),
                available.y() + max(0, (available.height() - height) // 2),
            )
        if saved.get("maximized"):
            QTimer.singleShot(0, self.showMaximized)
        self._update_rail_widths()

    def _save_geometry(self) -> None:
        maximized = self.isMaximized()
        geometry = self.normalGeometry() if maximized else self.geometry()
        self.config.update_window_state(
            {
                "width": geometry.width(),
                "height": geometry.height(),
                "x": geometry.x(),
                "y": geometry.y(),
                "maximized": maximized,
            }
        )

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        apply_dark_titlebar(self)

    # -------------------------------------------------------------- terminal

    def _ensure_initial_terminal(self) -> None:
        if not self.manager.sessions:
            self.manager.create()

    def create_terminal(self) -> None:
        snapshot = self.active_snapshot()
        tool_id = (snapshot or {}).get("tool_id") or self.config.last_tool_id
        self.manager.create(tool_id)

    def _next_terminal(self) -> None:
        ids = list(self.manager.sessions)
        if not ids:
            return
        index = ids.index(self.active_terminal_id) if self.active_terminal_id in ids else -1
        self.set_active_terminal(ids[(index + 1) % len(ids)])

    def _previous_terminal(self) -> None:
        ids = list(self.manager.sessions)
        if not ids:
            return
        index = ids.index(self.active_terminal_id) if self.active_terminal_id in ids else 0
        self.set_active_terminal(ids[(index - 1) % len(ids)])

    def _terminal_created(self, terminal_id: str) -> None:
        if terminal_id in self.pages:
            return
        snapshot = self.manager.snapshot(terminal_id)
        page = TerminalPanel(terminal_id, len(self.pages) + 1)
        page.set_max_lines(int(self.config.settings.get("max_terminal_lines", 5000)))
        page.action_requested.connect(self._page_action)
        page.command_requested.connect(self.run_terminal_command)
        page.interrupt_requested.connect(self.interrupt_terminal)
        self.pages[terminal_id] = page
        self.stack.addWidget(page)
        self._update_page(terminal_id)
        self.set_active_terminal(terminal_id)
        self.refresh_tabs()

    def _terminal_updated(self, terminal_id: str) -> None:
        if terminal_id not in self.pages:
            return
        snapshot = self.manager.snapshot(terminal_id)
        previous = self.status_cache.get(terminal_id)
        self.status_cache[terminal_id] = snapshot["status"]
        self._update_page(terminal_id)
        self.refresh_tabs()
        if self.active_terminal_id == terminal_id:
            self.refresh_tool_rail()
            self.refresh_network_rail()
            self.refresh_adb_status()
            self.refresh_window_title()
        if snapshot["status"] == "failed" and previous != "failed":
            self.toast(
                "error",
                "终端连接失败",
                snapshot.get("error") or "scrcpy 或 ADB 进程退出",
            )
        if snapshot["status"] == "running" and previous != "running":
            QTimer.singleShot(350, lambda: self.refresh_devices(silent=True))

    def _terminal_output(self, terminal_id: str, lines: list[dict[str, Any]]) -> None:
        page = self.pages.get(terminal_id)
        if page:
            page.append_lines(lines)

    def _terminal_removed(self, terminal_id: str) -> None:
        page = self.pages.pop(terminal_id, None)
        if page:
            self.stack.removeWidget(page)
            page.deleteLater()
        was_active = self.active_terminal_id == terminal_id
        remaining = list(self.manager.sessions)
        if was_active:
            self.active_terminal_id = remaining[-1] if remaining else None
        self.refresh_tabs()
        if self.active_terminal_id:
            self.set_active_terminal(self.active_terminal_id)
        else:
            self.stack.setCurrentWidget(self.empty_page)
            self.refresh_tool_rail()
            self.refresh_network_rail()
            self.refresh_adb_status()
            self.refresh_window_title()

    def _update_page(self, terminal_id: str) -> None:
        page = self.pages.get(terminal_id)
        if not page:
            return
        snapshot = self.manager.snapshot(terminal_id)
        snapshot["_auto_adb"] = bool(self.config.settings.get("auto_adb_connect"))
        page.update_snapshot(snapshot)
        page.set_idle_context(
            has_tools=bool(self.config.tools),
            has_networks=bool(self.config.networks),
            has_connectable=any(network.get("ports") for network in self.config.networks),
        )
        if self.active_terminal_id == terminal_id:
            self.refresh_window_title()

    def set_active_terminal(self, terminal_id: str) -> None:
        if terminal_id not in self.manager.sessions:
            return
        self.active_terminal_id = terminal_id
        page = self.pages.get(terminal_id)
        if page:
            self.stack.setCurrentWidget(page)
            self._update_page(terminal_id)
            if page.stack.currentWidget() is page.console_page:
                page.command_text.setFocus()
        self.refresh_tabs()
        self.refresh_tool_rail()
        self.refresh_network_rail()
        self.refresh_adb_status()
        self.refresh_window_title()

    def refresh_tabs(self) -> None:
        bar = self.tab_scroll.horizontalScrollBar()
        value = bar.value()
        while self.tab_layout.count():
            item = self.tab_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        ids = list(self.manager.sessions)
        if not ids:
            label = make_label("暂无终端，点击 ＋ 新建", role="faint")
            label.setContentsMargins(8, 8, 8, 8)
            self.tab_layout.addWidget(label)
            self.tab_layout.addStretch(1)
            return
        for terminal_id in ids:
            snapshot = self.manager.snapshot(terminal_id)
            tab = TerminalTab(snapshot, active=terminal_id == self.active_terminal_id)
            tab.selected.connect(self.set_active_terminal)
            tab.close_requested.connect(self.close_terminal)
            tab.menu_requested.connect(self._tab_menu)
            self.tab_layout.addWidget(tab)
        self.tab_layout.addStretch(1)
        QTimer.singleShot(0, lambda: bar.setValue(min(value, bar.maximum())))
        QTimer.singleShot(
            0,
            lambda: self._scroll_active_tab_visible(),
        )

    def _scroll_active_tab_visible(self) -> None:
        if not self.active_terminal_id:
            return
        for tab in self.tab_content.findChildren(TerminalTab):
            if tab.terminal_id == self.active_terminal_id:
                self.tab_scroll.ensureWidgetVisible(tab, 24, 0)
                break

    def refresh_window_title(self) -> None:
        """Keep the application window name stable and free of session data."""
        self.setWindowTitle("Scrcpy Dock")

    def active_snapshot(self) -> dict[str, Any] | None:
        if not self.active_terminal_id or not self.manager.exists(self.active_terminal_id):
            return None
        return self.manager.snapshot(self.active_terminal_id)

    def run_terminal_command(self, terminal_id: str, command: str) -> None:
        if not self.manager.exists(terminal_id):
            return
        try:
            self.manager.run_command(terminal_id, command)
        except AppError as exc:
            self.toast_error(exc)

    def interrupt_terminal(self, terminal_id: str) -> None:
        if not self.manager.exists(terminal_id):
            return
        try:
            self.manager.interrupt(terminal_id)
        except AppError as exc:
            self.toast_error(exc)

    def _page_action(self, terminal_id: str, action: str) -> None:
        snapshot = self.manager.snapshot(terminal_id) if self.manager.exists(terminal_id) else None
        if not snapshot:
            return
        if action == "stop":
            self.manager.stop(terminal_id)
        elif action == "clear":
            page = self.pages.get(terminal_id)
            if page:
                page.clear_console()
            self.manager.clear(terminal_id)
        elif action == "copy":
            command = self._terminal_command(snapshot)
            if command:
                QApplication.clipboard().setText(command)
                self.toast("success", "已复制", command, duration=2200)
        elif action == "log":
            self.open_log(terminal_id)
        elif action == "reconnect":
            target = snapshot.get("target")
            if target:
                try:
                    self.manager.open_device(
                        terminal_id,
                        target["host"],
                        target["port"],
                        network_id=target.get("network_id"),
                    )
                except AppError as exc:
                    self.toast_error(exc)
        elif action == "add_network":
            self.add_network()
        elif action == "idle_primary":
            if not self.config.tools:
                self.add_tool()
            elif not self.config.networks:
                self.add_network()
            else:
                network = next(
                    (item for item in self.config.networks if item.get("ports")), None
                )
                if network:
                    self.connect_port(network["id"], network["ports"][0]["port"])
                else:
                    first = self.config.networks[0]
                    self.expanded_networks.add(first["id"])
                    self.refresh_network_rail()
                    self.scan_network(first["id"])

    def close_terminal(self, terminal_id: str) -> None:
        if not self.manager.exists(terminal_id):
            return
        snapshot = self.manager.snapshot(terminal_id)
        if self.manager.is_active_id(terminal_id):
            confirmed = ConfirmDialog.ask(
                self,
                "关闭终端",
                f"“{self._terminal_title(snapshot)}” 仍在运行",
                "关闭会先停止当前 scrcpy 进程，并移除这个终端。",
                confirm_text="停止并关闭",
                danger=True,
            )
            if not confirmed:
                return
            self.manager.stop(terminal_id)
        try:
            self.manager.dismiss(terminal_id)
        except AppError as exc:
            self.toast_error(exc)

    def _terminal_title(self, snapshot: dict[str, Any]) -> str:
        target = snapshot.get("target") or {}
        return (
            snapshot.get("label")
            or target.get("network_label")
            or target.get("device_name")
            or target.get("host")
            or "终端"
        )

    def open_log(self, terminal_id: str) -> None:
        try:
            path = self.manager.open_log_path(terminal_id)
        except AppError as exc:
            self.toast_error(exc)
            return
        try:
            if sys.platform == "win32":
                subprocess.Popen(
                    ["explorer.exe", f"/select,{path}"],
                    creationflags=0x08000000,
                )
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except OSError as exc:
            self.toast("error", "无法打开日志", str(exc))

    # ---------------------------------------------------------------- tools

    def refresh_tool_rail(self) -> None:
        bar = self.tool_scroll.verticalScrollBar()
        value = bar.value()
        while self.tool_scroll_content.layout().count():
            item = self.tool_scroll_content.layout().takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        layout = self.tool_scroll_content.layout()
        tools = self.config.tools
        self.tool_count.setText(str(len(tools)))
        snapshot = self.active_snapshot()
        current_tool = snapshot.get("tool_id") if snapshot else None
        self.tool_caption.setText(
            f"当前终端 · {display_version(snapshot.get('tool_version'))}"
            if snapshot and snapshot.get("tool_id")
            else "当前终端尚未选择版本"
            if snapshot
            else "没有活跃终端"
        )

        if not tools:
            empty = self._rail_empty(
                "app",
                "还没有 scrcpy 版本",
                "添加完整解压后的 scrcpy 文件夹，自动识别版本，随时切换。",
                [("＋ 添加版本", self.add_tool), ("▣ 批量扫描", self.add_tool_batch)],
            )
            layout.addWidget(empty)
            layout.addStretch(1)
            return

        def decorated(tool: dict[str, Any]) -> dict[str, Any]:
            data = dict(tool)
            data["missing"] = not Path(tool["scrcpy_path"]).is_file()
            data["adb_available"] = bool(
                tool.get("adb_path") and Path(tool["adb_path"]).is_file()
            )
            return data

        favorites = [tool for tool in tools if tool.get("favorite")]
        others = [tool for tool in tools if not tool.get("favorite")]
        if favorites:
            layout.addWidget(make_label("★  收藏", role="sectionGold"))
            for tool in favorites:
                card = ToolCard(decorated(tool), active=tool["id"] == current_tool)
                card.selected.connect(self.select_tool)
                card.favorite_toggled.connect(self.toggle_favorite)
                card.menu_requested.connect(self._tool_menu)
                layout.addWidget(card)
        if others or not favorites:
            layout.addWidget(
                make_label("其他版本" if favorites else "全部版本", role="section")
            )
            for tool in others:
                card = ToolCard(decorated(tool), active=tool["id"] == current_tool)
                card.selected.connect(self.select_tool)
                card.favorite_toggled.connect(self.toggle_favorite)
                card.menu_requested.connect(self._tool_menu)
                layout.addWidget(card)
        if favorites and not others:
            note = make_label("全部版本已收藏", role="faint")
            note.setAlignment(Qt.AlignmentFlag.AlignCenter)
            note.setContentsMargins(0, 6, 0, 6)
            layout.addWidget(note)
        layout.addStretch(1)
        QTimer.singleShot(0, lambda: bar.setValue(min(value, bar.maximum())))

    def select_tool(self, tool_id: str) -> None:
        if not self.active_terminal_id or not self.manager.exists(self.active_terminal_id):
            self.manager.create(tool_id)
            return
        snapshot = self.manager.snapshot(self.active_terminal_id)
        if snapshot.get("tool_id") == tool_id and snapshot.get("status") != "failed":
            return
        try:
            self.manager.assign_tool(self.active_terminal_id, tool_id)
            tool = self.config.get_tool(tool_id)
            self.toast(
                "info",
                "版本已切换",
                f"当前终端使用 {display_version(tool['version'] if tool else '')}",
                duration=2200,
            )
        except AppError as exc:
            self.toast_error(exc)

    def toggle_favorite(self, tool_id: str) -> None:
        tool = self.config.get_tool(tool_id)
        if not tool:
            return
        self.config.update_tool(tool_id, {"favorite": not tool.get("favorite")})
        self.refresh_tool_rail()

    @staticmethod
    def _color_icon(color: str) -> QIcon:
        pixmap = QPixmap(14, 14)
        pixmap.fill(QColor(color))
        return QIcon(pixmap)

    def set_tool_color(self, tool_id: str, color: str) -> None:
        tool = self.config.get_tool(tool_id)
        if not tool:
            return
        try:
            self.config.update_tool(tool_id, {"color": color})
        except AppError as exc:
            self.toast_error(exc)
            return
        self.refresh_tool_rail()
        self.toast("success", "颜色已更新", f"scrcpy {tool['version']} · {color}")

    def pick_tool_color(self, tool_id: str) -> None:
        tool = self.config.get_tool(tool_id)
        if not tool:
            return
        color = QColorDialog.getColor(
            QColor(tool.get("color") or "#5eead4"),
            self,
            "选择 scrcpy 版本颜色",
        )
        if color.isValid():
            self.set_tool_color(tool_id, color.name())

    def add_tool(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择 scrcpy 工具文件夹")
        if not folder:
            return

        def job() -> dict[str, Any]:
            return inspect_tool_folder(folder)

        def success(info: dict[str, Any]) -> None:
            try:
                tool = self.config.add_tool(info)
            except AppError as exc:
                self.toast_error(exc)
                return
            self.refresh_tool_rail()
            self.refresh_network_rail()
            self.refresh_adb_status()
            self.refresh_pages_context()
            self.refresh_devices(silent=True)
            warnings = "；".join(info.get("warnings") or [])
            self.toast(
                "success",
                "scrcpy 版本已添加",
                f"{display_version(tool['version'])}" + (f"\n{warnings}" if warnings else ""),
            )

        self._start_task(job, success, busy_text="正在识别 scrcpy 版本…")

    def add_tool_batch(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择包含多个 scrcpy 版本的父文件夹")
        if not folder:
            return

        def job() -> dict[str, Any]:
            return inspect_tool_parent(folder)

        def success(result: dict[str, Any]) -> None:
            added = 0
            duplicates = 0
            errors = list(result.get("errors") or [])
            for info in result.get("tools") or []:
                try:
                    self.config.add_tool(info)
                    added += 1
                except AppError as exc:
                    if exc.code == "TOOL_DUPLICATE":
                        duplicates += 1
                    else:
                        errors.append({"folder": info.get("folder", ""), "message": exc.message})
            self.refresh_tool_rail()
            self.refresh_network_rail()
            self.refresh_adb_status()
            self.refresh_pages_context()
            parts = [f"发现 {result.get('found', 0)} 个版本", f"新增 {added} 个"]
            if duplicates:
                parts.append(f"已存在 {duplicates} 个")
            if errors:
                parts.append(f"失败 {len(errors)} 个")
            self.toast(
                "warning" if errors else "success",
                "批量添加完成",
                " · ".join(parts),
                duration=5000,
            )
            self.refresh_devices(silent=True)

        self._start_task(job, success, busy_text="正在扫描父文件夹中的 scrcpy 版本…")

    def rescan_tool(self, tool_id: str) -> None:
        tool = self.config.get_tool(tool_id)
        if not tool:
            return

        def job() -> dict[str, Any]:
            return rescan_tool(tool)

        def success(info: dict[str, Any]) -> None:
            self.config.update_tool(tool_id, info)
            self.refresh_tool_rail()
            if self.active_snapshot():
                self._update_page(self.active_terminal_id)
            self.refresh_tabs()
            self.toast("success", "版本检测完成", display_version(info["detected_version"]))

        self._start_task(job, success, busy_text="正在重新读取版本…")

    def rescan_all_tools(self) -> None:
        tools = self.config.tools
        if not tools:
            return

        def job() -> list[dict[str, Any]]:
            results = []
            for tool in tools:
                try:
                    results.append({"tool": tool, "info": rescan_tool(tool), "error": None})
                except Exception as exc:
                    results.append({"tool": tool, "info": None, "error": str(exc)})
            return results

        def success(results: list[dict[str, Any]]) -> None:
            errors = 0
            for result in results:
                if result["info"]:
                    self.config.update_tool(result["tool"]["id"], result["info"])
                else:
                    errors += 1
            self.refresh_tool_rail()
            self.refresh_tabs()
            if self.active_terminal_id:
                self._update_page(self.active_terminal_id)
            self.toast(
                "warning" if errors else "success",
                "版本检测完成",
                f"{errors} 个版本读取失败" if errors else "所有版本已重新识别。",
            )

        self._start_task(job, success, busy_text="正在重新检测全部版本…")

    def remove_tool(self, tool_id: str) -> None:
        tool = self.config.get_tool(tool_id)
        if not tool:
            return
        confirmed = ConfirmDialog.ask(
            self,
            "移除 scrcpy 版本",
            f"确定移除 {display_version(tool['version'])}？",
            "只从版本列表移除，不会删除磁盘文件。已绑定该版本的终端将无法继续连接。",
            confirm_text="移除",
            danger=True,
        )
        if not confirmed:
            return
        self.config.remove_tool(tool_id)
        self.refresh_tool_rail()
        self.refresh_tabs()
        if self.active_terminal_id:
            self._update_page(self.active_terminal_id)
        self.refresh_adb_status()
        self.refresh_devices(silent=True)
        self.toast("success", "已移除", display_version(tool["version"]))

    def edit_tool_version(self, tool_id: str) -> None:
        tool = self.config.get_tool(tool_id)
        if not tool:
            return
        dialog = VersionDialog(tool, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.config.update_tool(tool_id, dialog.value())
        self.refresh_tool_rail()
        self.refresh_tabs()
        if self.active_terminal_id:
            self._update_page(self.active_terminal_id)
        self.toast("success", "版本标签已更新")

    def open_tool_folder(self, tool_id: str) -> None:
        tool = self.config.get_tool(tool_id)
        if not tool:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(tool["folder"]))

    def _tool_menu(self, tool_id: str, position: QPoint) -> None:
        tool = self.config.get_tool(tool_id)
        if not tool:
            return
        menu = QMenu(self)
        current = self.active_snapshot()
        action = menu.addAction("◎ 设为当前终端版本")
        action.setEnabled(bool(self.active_terminal_id) and current.get("tool_id") != tool_id)
        action.triggered.connect(lambda: self.select_tool(tool_id))
        action = menu.addAction("★ 取消收藏" if tool.get("favorite") else "☆ 收藏版本")
        action.triggered.connect(lambda: self.toggle_favorite(tool_id))
        color_menu = menu.addMenu("◈ 图标颜色")
        current_color = str(tool.get("color") or "").lower()
        for color, color_name in TOOL_COLOR_PALETTE:
            action = color_menu.addAction(self._color_icon(color), color_name)
            action.setCheckable(True)
            action.setChecked(current_color == color)
            action.triggered.connect(
                lambda _checked=False, value=color: self.set_tool_color(tool_id, value)
            )
        color_menu.addSeparator()
        action = color_menu.addAction("自定义颜色…")
        action.triggered.connect(lambda: self.pick_tool_color(tool_id))
        menu.addSeparator()
        action = menu.addAction("✎ 修改版本标签")
        action.triggered.connect(lambda: self.edit_tool_version(tool_id))
        action = menu.addAction("⟳ 重新检测版本")
        action.triggered.connect(lambda: self.rescan_tool(tool_id))
        action = menu.addAction("▣ 打开工具文件夹")
        action.triggered.connect(lambda: self.open_tool_folder(tool_id))
        menu.addSeparator()
        action = menu.addAction("✕ 从列表移除")
        action.triggered.connect(lambda: self.remove_tool(tool_id))
        menu.exec(position)

    def _tool_rail_menu(self, position: QPoint) -> None:
        menu = QMenu(self)
        action = menu.addAction("＋ 添加 scrcpy 版本")
        action.triggered.connect(self.add_tool)
        action = menu.addAction("▣ 批量扫描父文件夹")
        action.triggered.connect(self.add_tool_batch)
        action = menu.addAction("⟳ 重新检测全部版本")
        action.triggered.connect(self.rescan_all_tools)
        menu.addSeparator()
        action = menu.addAction("⚙ 版本与启动设置")
        action.triggered.connect(self.open_tool_settings)
        action = menu.addAction(f"ⓘ 关于 Scrcpy Dock v{__version__}")
        action.triggered.connect(self.open_about)
        menu.exec(position)

    def open_tool_settings(self) -> None:
        if self.tool_settings_dialog and self.tool_settings_dialog.isVisible():
            self.tool_settings_dialog.raise_()
            self.tool_settings_dialog.activateWindow()
            return
        dialog = ToolSettingsDialog(self.config, self)
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        dialog.add_requested.connect(self.add_tool)
        dialog.batch_requested.connect(self.add_tool_batch)
        dialog.rescan_requested.connect(self.rescan_all_tools)
        dialog.edit_version_requested.connect(self._edit_current_tool_version)
        dialog.accepted.connect(lambda: self._save_tool_settings(dialog))
        dialog.finished.connect(self._tool_settings_closed)
        self.tool_settings_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _save_tool_settings(self, dialog: ToolSettingsDialog) -> None:
        self.config.update_settings({"default_args": dialog.default_args_value()})
        self.toast("success", "scrcpy 设置已保存")
        self.refresh_pages_context()

    def _edit_current_tool_version(self) -> None:
        snapshot = self.active_snapshot()
        tool_id = (snapshot or {}).get("tool_id")
        if not tool_id:
            self.toast(
                "warning",
                "没有可编辑的版本",
                "先在左侧选择一个 scrcpy 版本，或添加新版本。",
            )
            return
        self.edit_tool_version(tool_id)

    def _tool_settings_closed(self, _result: int) -> None:
        dialog = self.tool_settings_dialog
        self.tool_settings_dialog = None
        if dialog:
            dialog.deleteLater()

    # -------------------------------------------------------------- networks

    def refresh_network_rail(self) -> None:
        bar = self.network_scroll.verticalScrollBar()
        value = bar.value()
        while self.network_scroll_content.layout().count():
            item = self.network_scroll_content.layout().takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        layout = self.network_scroll_content.layout()
        networks = self.config.networks
        self.network_count.setText(str(len(networks)))
        snapshot = self.active_snapshot()
        target = snapshot.get("target") if snapshot else None
        active_network_id = None
        active_port = None
        if target:
            network = self.config.get_network(target.get("network_id")) or self.config.find_network_by_ip(
                target.get("host", "")
            )
            if network:
                active_network_id = network["id"]
                active_port = target.get("port")
                # Do not force-expand here: the user must be able to collapse
                # the IP group even while its port is connected.

        if not networks:
            empty = self._rail_empty(
                "◎",
                "还没有保存的 IP",
                "添加设备 IP，自动扫描端口。点击端口即可在当前终端一键连接。",
                [("＋ 添加 IP", self.add_network), ("▣ 手动添加", self.add_network)],
            )
            layout.addWidget(empty)
            layout.addStretch(1)
            self._refresh_device_footer()
            QTimer.singleShot(0, lambda: bar.setValue(min(value, bar.maximum())))
            return

        online_ports = self._online_ports()
        fallback_name = (target or {}).get("device_name", "")
        for network in networks:
            card = NetworkCard(
                network,
                expanded=network["id"] in self.expanded_networks,
                current=network["id"] == active_network_id,
                active_port=active_port if network["id"] == active_network_id else None,
                online_ports=online_ports.get(network["ip"], set()),
                scanning=network["id"] in self.scanning_networks,
                fallback_name=fallback_name if network["id"] == active_network_id else "",
            )
            card.toggle_requested.connect(self._toggle_network)
            card.port_clicked.connect(self.connect_port)
            card.scan_requested.connect(lambda nid: self.scan_network(nid, full=True))
            card.quick_scan_requested.connect(lambda nid: self.scan_network(nid, full=False))
            card.add_port_requested.connect(self.add_port)
            card.menu_requested.connect(self._network_menu)
            card.port_context_requested.connect(self._port_menu)
            layout.addWidget(card)
        layout.addStretch(1)
        self._refresh_device_footer()
        QTimer.singleShot(0, lambda: bar.setValue(min(value, bar.maximum())))

    def _toggle_network(self, network_id: str) -> None:
        if network_id in self.expanded_networks:
            self.expanded_networks.discard(network_id)
        else:
            self.expanded_networks.add(network_id)
        self.refresh_network_rail()

    def _online_ports(self) -> dict[str, set[int]]:
        result: dict[str, set[int]] = {}
        for device in self.devices:
            if not device.get("online") or not device.get("wireless"):
                continue
            serial = str(device.get("serial") or "")
            if ":" not in serial:
                continue
            host, port_text = serial.rsplit(":", 1)
            try:
                port = int(port_text)
            except ValueError:
                continue
            result.setdefault(host, set()).add(port)
        return result

    def _refresh_device_footer(self) -> None:
        online = sum(1 for device in self.devices if device.get("online"))
        if self.devices_error:
            self.device_footer.setText("设备列表不可用")
            self.device_footer.setToolTip(self.devices_error)
        else:
            self.device_footer.setText(f"{online} 台在线 · {len(self.devices)} 台 ADB 设备")
            self.device_footer.setToolTip("")

    def add_network(self) -> None:
        dialog = AddNetworkDialog(
            bool(self.config.settings.get("auto_scan")),
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            network = self.config.add_network(
                values["ip"],
                label=values["label"],
                port=values["port"],
                source="manual",
            )
        except AppError as exc:
            self.toast_error(exc)
            return
        self.expanded_networks.add(network["id"])
        self.refresh_network_rail()
        self.refresh_pages_context()
        if values["auto_scan"]:
            full = bool(self.config.settings.get("scan_full", True))
            self.toast(
                "info",
                "IP 已添加",
                "正在执行全端口扫描，可能需要几十秒…" if full else "正在扫描常用端口…",
                duration=2600,
            )
            self.scan_network(network["id"], full=full)
        else:
            self.toast("success", "IP 已添加", f"{network['ip']} 已保存")

    def edit_network(self, network_id: str) -> None:
        network = self.config.get_network(network_id)
        if not network:
            return
        dialog = EditNetworkDialog(network, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.config.update_network(network_id, dialog.values())
        except AppError as exc:
            self.toast_error(exc)
            return
        self.refresh_network_rail()
        self.refresh_tabs()
        if self.active_terminal_id:
            self._update_page(self.active_terminal_id)

    def remove_network(self, network_id: str) -> None:
        network = self.config.get_network(network_id)
        if not network:
            return
        confirmed = ConfirmDialog.ask(
            self,
            "移除 IP",
            f"移除 {network.get('label') or network['ip']}？",
            "会同时移除这个 IP 下保存的所有端口，不影响正在运行的终端。",
            confirm_text="移除",
            danger=True,
        )
        if confirmed:
            self.config.remove_network(network_id)
            self.expanded_networks.discard(network_id)
            self.refresh_network_rail()
            self.refresh_pages_context()

    def remove_port(self, network_id: str, port: int) -> None:
        network = self.config.get_network(network_id)
        if not network:
            return
        confirmed = ConfirmDialog.ask(
            self,
            "移除端口",
            f"移除 {network['ip']}:{port}？",
            "只移除端口记录，不会断开已连接设备。",
            confirm_text="移除",
            danger=True,
        )
        if confirmed:
            self.config.remove_network_port(network_id, port)
            self.refresh_network_rail()
            self.refresh_pages_context()

    def add_port(self, network_id: str) -> None:
        network = self.config.get_network(network_id)
        if not network:
            return
        dialog = AddPortDialog(network, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.config.add_network_port(network_id, dialog.port(), source="manual")
        except AppError as exc:
            self.toast_error(exc)
            return
        self.expanded_networks.add(network_id)
        self.refresh_network_rail()
        self.toast("success", "端口已添加", f"{network['ip']}:{dialog.port()}")

    def scan_network(self, network_id: str, *, full: bool = True) -> None:
        network = self.config.get_network(network_id)
        if not network or network_id in self.scanning_networks:
            return
        settings = self.config.settings
        self.scanning_networks.add(network_id)
        self.expanded_networks.add(network_id)
        self.refresh_network_rail()
        scan_start = 1 if full else int(settings["scan_start"])
        scan_end = 65535 if full else int(settings["scan_end"])
        scan_timeout = 150 if full else int(settings["scan_timeout_ms"])

        def job() -> dict[str, Any]:
            docker_ports = (
                discover_docker_ports()
                if settings.get("use_docker_ports", True)
                else []
            )
            result = scan_ports(
                network["ip"],
                start=scan_start,
                end=scan_end,
                timeout_ms=scan_timeout,
                extra_ports=[
                    *[entry["port"] for entry in network.get("ports") or []],
                    *[entry["port"] for entry in docker_ports],
                ],
                verify_adb=True,
            )
            result["docker_ports"] = docker_ports
            result["full_scan"] = full
            return result

        def success(result: dict[str, Any]) -> None:
            self.scanning_networks.discard(network_id)
            if not self.config.get_network(network_id):
                return
            open_ports = result.get("open_ports") or []
            adb_ports = set(result.get("adb_ports") or [])
            # 5555-5585 is the conventional adb range; keep those even if a
            # device is slow to answer the handshake. Other open services
            # (SMB, RPC, web...) are excluded unless the ADB handshake passed.
            adb_ports.update(
                item["port"]
                for item in open_ports
                if 5555 <= int(item["port"]) <= 5585
            )
            for port in sorted(adb_ports):
                self.config.add_network_port(network_id, port, source="scan")
            docker_ports = result.get("docker_ports") or []
            for entry in docker_ports:
                self.config.add_network_port(
                    network_id,
                    entry["port"],
                    device_name=entry.get("container", ""),
                    source="docker",
                )
            self.refresh_network_rail()
            self.refresh_pages_context()
            self.refresh_devices(silent=True)
            count = len(adb_ports)
            docker_count = len(docker_ports)
            other_open = max(0, len(open_ports) - len(adb_ports))
            if count or docker_count:
                ports = ", ".join(str(port) for port in sorted(adb_ports))
                details = []
                if ports:
                    details.append(f"ADB 端口：{ports}")
                if docker_count:
                    details.append(f"Docker 映射：{docker_count} 个")
                if other_open:
                    details.append(f"其他开放端口 {other_open} 个已忽略")
                self.toast(
                    "success",
                    "全端口扫描完成" if full else "快速扫描完成",
                    f"{network['ip']} · " + " · ".join(details),
                    duration=5200,
                )
            else:
                self.toast(
                    "info",
                    "没有发现 ADB 端口",
                    f"扫描了 {result.get('scanned', 0)} 个端口。"
                    + ("可确认容器端口映射或检查网络。" if full else "可尝试全端口扫描。"),
                )

        def failure(exc: Exception) -> None:
            self.scanning_networks.discard(network_id)
            self.refresh_network_rail()
            self.toast_error(exc if isinstance(exc, AppError) else AppError(str(exc)), "扫描失败")

        self._start_task(job, success, failure)

    def connect_port(self, network_id: str, port: int) -> None:
        network = self.config.get_network(network_id)
        if not network or not is_valid_port(port):
            return
        if not self.config.tools:
            self.toast("warning", "还没有 scrcpy 版本", "请先在左侧添加一个 scrcpy 文件夹。")
            return
        if not self.active_terminal_id or not self.manager.exists(self.active_terminal_id):
            self.manager.create(self.config.last_tool_id)
        if not self.active_terminal_id:
            return
        self.expanded_networks.add(network_id)
        try:
            self.manager.open_device(
                self.active_terminal_id,
                network["ip"],
                int(port),
                network_id=network_id,
            )
        except AppError as exc:
            self.toast_error(exc)

    def _network_menu(self, network_id: str, position: QPoint) -> None:
        network = self.config.get_network(network_id)
        if not network:
            return
        menu = QMenu(self)
        action = menu.addAction("▶ 连接到当前终端")
        action.setEnabled(bool(self.active_terminal_id) and bool(network.get("ports")))
        if network.get("ports"):
            action.triggered.connect(
                lambda: self.connect_port(network_id, network["ports"][0]["port"])
            )
        action = menu.addAction("✎ 编辑 IP / 名称")
        action.triggered.connect(lambda: self.edit_network(network_id))
        action = menu.addAction("◉ 全端口扫描（1–65535）")
        action.triggered.connect(lambda: self.scan_network(network_id, full=True))
        action = menu.addAction("⟳ 快速扫描（常用范围）")
        action.triggered.connect(lambda: self.scan_network(network_id, full=False))
        action = menu.addAction("＋ 添加端口")
        action.triggered.connect(lambda: self.add_port(network_id))
        action = menu.addAction("⧉ 复制 IP")
        action.triggered.connect(lambda: self._copy(network["ip"]))
        menu.addSeparator()
        action = menu.addAction("✕ 移除 IP")
        action.triggered.connect(lambda: self.remove_network(network_id))
        menu.exec(position)

    def _port_menu(self, network_id: str, port: int, position: QPoint) -> None:
        network = self.config.get_network(network_id)
        if not network:
            return
        menu = QMenu(self)
        action = menu.addAction("▶ 连接到当前终端")
        action.setEnabled(bool(self.active_terminal_id))
        action.triggered.connect(lambda: self.connect_port(network_id, port))
        action = menu.addAction("⧉ 复制 IP:端口")
        action.triggered.connect(lambda: self._copy(f"{network['ip']}:{port}"))
        menu.addSeparator()
        action = menu.addAction("✕ 移除端口")
        action.triggered.connect(lambda: self.remove_port(network_id, port))
        menu.exec(position)

    def _network_rail_menu(self, position: QPoint) -> None:
        menu = QMenu(self)
        action = menu.addAction("＋ 添加 IP")
        action.triggered.connect(self.add_network)
        action = menu.addAction("⟳ 刷新 ADB 设备与名称")
        action.triggered.connect(lambda: self.refresh_devices(silent=False))
        menu.addSeparator()
        action = menu.addAction("⚙ IP 与 ADB 设置")
        action.triggered.connect(self.open_network_settings)
        action = menu.addAction(f"ⓘ 关于 Scrcpy Dock v{__version__}")
        action.triggered.connect(self.open_about)
        menu.exec(position)

    def _tab_menu(self, terminal_id: str, position: QPoint) -> None:
        if not self.manager.exists(terminal_id):
            return
        snapshot = self.manager.snapshot(terminal_id)
        menu = QMenu(self)
        action = menu.addAction("✕ 关闭终端")
        action.triggered.connect(lambda: self.close_terminal(terminal_id))
        action = menu.addAction("⌫ 清空输出")
        action.triggered.connect(
            lambda: (
                self.pages[terminal_id].clear_console()
                if terminal_id in self.pages
                else None,
                self.manager.clear(terminal_id),
            )
        )
        action = menu.addAction("⧉ 复制连接命令")
        action.setEnabled(bool(snapshot.get("command")))
        action.triggered.connect(
            lambda: self._copy(self._terminal_command(snapshot))
        )
        action = menu.addAction("■ 停止投屏" if self.manager.is_active_id(terminal_id) else "▶ 重连")
        action.triggered.connect(
            lambda: (
                self.manager.stop(terminal_id)
                if self.manager.is_active_id(terminal_id)
                else self._page_action(terminal_id, "reconnect")
            )
        )
        menu.exec(position)

    def _tab_empty_menu(self, position: QPoint) -> None:
        menu = QMenu(self)
        action = menu.addAction("＋ 新建终端")
        action.triggered.connect(self.create_terminal)
        menu.exec(position)

    # -------------------------------------------------------------- settings

    def open_network_settings(self) -> None:
        dialog = NetworkSettingsDialog(self.config, self.adb.get_adb_info(self._active_tool_id()), self)
        dialog.open_data_requested.connect(self.open_data_dir)
        dialog.open_logs_requested.connect(self.open_logs_dir)
        dialog.refresh_requested.connect(lambda: self.refresh_devices(silent=False))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if values["adb_path"]:
            path = Path(values["adb_path"])
            if not path.is_file() or path.name.casefold() != "adb.exe":
                self.toast("error", "ADB 路径无效", "请选择名为 adb.exe 的文件。")
                return
        self.config.update_settings(values)
        for page in self.pages.values():
            page.set_max_lines(int(self.config.settings.get("max_terminal_lines", 5000)))
        self.refresh_adb_status()
        self.refresh_pages_context()
        self.refresh_devices(silent=True)
        self.toast("success", "设置已保存")

    def open_data_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.config.data_dir)))

    def open_logs_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.config.logs_dir)))

    def open_about(self) -> None:
        if getattr(sys, "frozen", False):
            executable = Path(sys.executable)
        else:
            executable = Path(__file__).resolve().parents[2] / "run.py"
        try:
            build_time = datetime.fromtimestamp(executable.stat().st_mtime).strftime(
                "%Y-%m-%d %H:%M"
            )
        except OSError:
            build_time = "未知"

        adb = self.adb.get_adb_info(self._active_tool_id())
        ports_count = sum(len(network.get("ports") or []) for network in self.config.networks)
        terminals_total = len(self.manager.sessions)
        terminals_running = self.manager.active_count()
        info = {
            "version": __version__,
            "build_time": build_time,
            "qt": qVersion(),
            "pyside": pyside_version,
            "python": platform.python_version(),
            "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
            "executable": str(executable),
            "tools_count": len(self.config.tools),
            "favorites": sum(1 for tool in self.config.tools if tool.get("favorite")),
            "networks_count": len(self.config.networks),
            "ports_count": ports_count,
            "terminals_total": terminals_total,
            "terminals_running": terminals_running,
            "adb": (
                f"{adb.get('source_label', '')} · {adb.get('path')}"
                if adb.get("path")
                else adb.get("source_label", "未找到 ADB")
            ),
            "data_dir": str(self.config.data_dir),
            "logs_dir": str(self.config.logs_dir),
            "config_path": str(self.config.config_path),
        }
        dialog = AboutDialog(
            info,
            on_open_data=self.open_data_dir,
            on_open_logs=self.open_logs_dir,
            on_copy=lambda: self._copy_about_info(info),
            parent=self,
        )
        dialog.exec()

    def _copy_about_info(self, info: dict[str, Any]) -> None:
        lines = [
            f"Scrcpy Dock {info['version']}",
            f"Build: {info['build_time']}",
            f"Qt: {info['qt']}",
            f"PySide6: {info['pyside']}",
            f"Python: {info['python']}",
            f"OS: {info['os']}",
            f"Executable: {info['executable']}",
            f"ADB: {info['adb']}",
            f"Tools: {info['tools_count']} (favorites {info['favorites']})",
            f"Networks: {info['networks_count']} / ports {info['ports_count']}",
            f"Terminals: {info['terminals_total']} (running {info['terminals_running']})",
            f"Data: {info['data_dir']}",
            f"Logs: {info['logs_dir']}",
            f"Config: {info['config_path']}",
        ]
        QApplication.clipboard().setText("\n".join(lines))
        self.toast("success", "诊断信息已复制", "可以直接粘贴到反馈中。", duration=2400)

    # -------------------------------------------------------------- devices

    def _active_tool_id(self) -> str | None:
        snapshot = self.active_snapshot()
        return (snapshot or {}).get("tool_id") or self.config.last_tool_id

    def refresh_devices(self, *, silent: bool = False) -> None:
        if self.device_task is not None:
            return
        tool_id = self._active_tool_id()
        if not tool_id:
            self.devices = []
            self.devices_error = ""
            self._refresh_device_footer()
            return

        def job() -> dict[str, Any]:
            return self.adb.list_devices(tool_id)

        def success(result: dict[str, Any]) -> None:
            self.device_task = None
            self.devices = result.get("devices") or []
            self.devices_error = ""
            self.config.apply_device_names(
                self.devices,
                auto_import=bool(self.config.settings.get("auto_import_adb_devices", True)),
            )
            self.refresh_network_rail()
            self.refresh_adb_status()
            if self.active_terminal_id:
                self._update_page(self.active_terminal_id)
            if not silent:
                self.toast(
                    "success",
                    "设备列表已刷新",
                    f"{sum(1 for device in self.devices if device.get('online'))} 台在线",
                    duration=2200,
                )

        def failure(exc: Exception) -> None:
            self.device_task = None
            self.devices = []
            self.devices_error = str(exc)
            self.refresh_network_rail()
            self.refresh_adb_status()
            if not silent:
                self.toast_error(exc, "设备列表不可用")

        self.device_task = self._start_task(job, success, failure)

    def refresh_adb_status(self) -> None:
        info = self.adb.get_adb_info(self._active_tool_id())
        self.adb_label.setText("ADB 就绪" if info.get("available") else "ADB 未就绪")
        source = info.get("source_label", "未找到")
        path = info.get("path")
        self.adb_source.setText(f"{source} · {Path(path).name}" if path else source)
        self.adb_source.setToolTip(path or info.get("missing_path", ""))
        self.adb_dot.setProperty(
            "state", "online" if info.get("available") else "error"
        )
        repolish(self.adb_dot)

    # ---------------------------------------------------------------- helpers

    def _rail_empty(
        self,
        glyph: str,
        title: str,
        text: str,
        actions: list[tuple[str, Callable[[], None]]],
    ) -> QFrame:
        frame = QFrame()
        frame.setObjectName("RailEmpty")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 24, 15, 24)
        layout.setSpacing(7)
        icon = QLabel(glyph if glyph != "app" else "")
        icon.setObjectName("RailEmptyIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if glyph == "app":
            icon.setFixedSize(38, 38)
            icon.setPixmap(app_pixmap(38))
            icon.setStyleSheet("background:transparent;border:none;")
        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)
        title_label = QLabel(title)
        title_label.setObjectName("RailEmptyTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        body = QLabel(text)
        body.setObjectName("RailEmptyText")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(body)
        for index, (label, callback) in enumerate(actions):
            button = QPushButton(label)
            button.setProperty("kind", "primary" if index == 0 else "link")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(callback)
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
        return frame

    def _terminal_command(self, snapshot: dict[str, Any]) -> str:
        command = snapshot.get("command") or ""
        if not command:
            return ""
        cwd = snapshot.get("working_directory") or ""
        return f'cd /d "{cwd}" && {command}' if cwd else command

    def _copy(self, text: str) -> None:
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.toast("success", "已复制", text, duration=1800)

    def refresh_pages_context(self) -> None:
        for terminal_id in list(self.pages):
            self._update_page(terminal_id)
        if not self.active_terminal_id:
            self.refresh_tool_rail()
            self.refresh_network_rail()

    def toast(
        self,
        kind: str,
        title: str,
        message: str = "",
        *,
        duration: int = 4200,
    ) -> None:
        frame = ToastFrame(self, kind, title, message, self._dismiss_toast)
        self.toasts.append(frame)
        while len(self.toasts) > 4:
            oldest = self.toasts.pop(0)
            oldest.deleteLater()
        self._position_toasts()
        frame.show()
        frame.raise_()
        QTimer.singleShot(duration, lambda: self._dismiss_toast(frame))

    def toast_error(self, error: Exception, title: str = "操作失败") -> None:
        if isinstance(error, AppError):
            message = error.user_text()
        else:
            message = str(error)
        self.toast("error", title, message, duration=5400)

    def _dismiss_toast(self, frame: ToastFrame) -> None:
        if frame in self.toasts:
            self.toasts.remove(frame)
        frame.deleteLater()
        self._position_toasts()

    def _position_toasts(self) -> None:
        y = self.centralWidget().height() - 18
        for frame in reversed(self.toasts):
            frame.adjustSize()
            x = self.centralWidget().width() - frame.width() - 18
            y -= frame.height()
            frame.move(max(10, x), max(10, y))
            frame.raise_()
            y -= 7

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_rail_widths()
        self._position_toasts()

    def _update_rail_widths(self) -> None:
        width = self.width()
        if width < 1180:
            left, right = 208, 260
        elif width < 1380:
            left, right = 226, 282
        else:
            left, right = 252, 306
        if self.tool_rail.width() != left:
            self.tool_rail.setFixedWidth(left)
        if self.network_rail.width() != right:
            self.network_rail.setFixedWidth(right)

    # ------------------------------------------------------------------ tasks

    def _start_task(
        self,
        function: Callable[[], Any],
        success: Callable[[Any], None],
        failure: Callable[[Exception], None] | None = None,
        *,
        busy_text: str | None = None,
    ) -> int:
        self._task_seq += 1
        task_id = self._task_seq
        busy = BusyDialog(busy_text, self) if busy_text else None
        if busy:
            busy.show()
            busy.raise_()
            QApplication.processEvents()
        thread = threading.Thread(
            target=self._run_task,
            args=(task_id, function),
            name=f"ScrcpyDockTask-{task_id}",
            daemon=True,
        )
        self.tasks[task_id] = {
            "thread": thread,
            "success": success,
            "failure": failure,
            "busy": busy,
            "finished": False,
        }
        thread.start()
        return task_id

    def _run_task(self, task_id: int, function: Callable[[], Any]) -> None:
        """Executed on a plain Python thread.

        Worker functions must not touch Qt widgets. Results are relayed through
        a main-thread QObject signal; this avoids the GIL/Qt-mutex deadlock that
        QThread + deleteLater can produce.
        """
        try:
            value = function()
        except Exception as exc:  # noqa: BLE001 - delivered to the UI
            self.task_signals.failed.emit(task_id, exc)
        else:
            self.task_signals.result.emit(task_id, value)
        finally:
            self.task_signals.finished.emit(task_id)

    @Slot(int, object)
    def _task_result(self, task_id: int, value: Any) -> None:
        task = self.tasks.get(task_id)
        if not task or task.get("finished"):
            return
        task["finished"] = True
        busy = task.get("busy")
        if busy:
            busy.close()
        try:
            task["success"](value)
        except Exception as exc:  # noqa: BLE001
            self.toast_error(exc, "处理结果失败")
        if task_id == self.device_task:
            self.device_task = None

    @Slot(int, object)
    def _task_failure(self, task_id: int, error: Exception) -> None:
        task = self.tasks.get(task_id)
        if not task or task.get("finished"):
            return
        task["finished"] = True
        busy = task.get("busy")
        if busy:
            busy.close()
        callback = task.get("failure")
        if callback:
            try:
                callback(error)
            except Exception as exc:  # noqa: BLE001
                self.toast_error(exc)
        else:
            self.toast_error(error)
        if task_id == self.device_task:
            self.device_task = None

    @Slot(int)
    def _task_finished(self, task_id: int) -> None:
        task = self.tasks.pop(task_id, None)
        if not task:
            return
        busy = task.get("busy")
        if busy:
            busy.close()

    def _wait_for_tasks(self) -> None:
        deadline = time.monotonic() + 6.0
        for task in list(self.tasks.values()):
            thread = task.get("thread")
            if not thread:
                continue
            remaining = max(0.0, deadline - time.monotonic())
            if remaining <= 0:
                break
            thread.join(remaining)

    # ----------------------------------------------------------------- close

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        active = self.manager.active_count()
        if active and not self._closing:
            confirmed = ConfirmDialog.ask(
                self,
                "退出 Scrcpy Dock",
                f"仍有 {active} 个终端正在运行",
                "退出会同时结束所有 scrcpy 进程。",
                confirm_text="停止并退出",
                danger=True,
            )
            if not confirmed:
                event.ignore()
                return
        self._closing = True
        self._save_geometry()
        if self.tool_settings_dialog:
            self.tool_settings_dialog.close()
        self.manager.stop_all()
        self._wait_for_tasks()
        self.device_timer.stop()
        event.accept()
