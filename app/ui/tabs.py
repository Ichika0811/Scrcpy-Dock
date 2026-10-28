"""Custom multi-line terminal tabs."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QContextMenuEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .rails import display_version


class TerminalTab(QFrame):
    selected = Signal(str)
    close_requested = Signal(str)
    menu_requested = Signal(str, QPoint)

    def __init__(self, snapshot: dict[str, Any], *, active: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.terminal_id = snapshot["id"]
        self.setObjectName("TerminalTab")
        self.setProperty("active", "true" if active else "false")
        self.setProperty("notool", "false" if snapshot.get("tool_id") else "true")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(178)
        self.setFixedHeight(36)
        self.setToolTip(
            f"{display_version(snapshot.get('tool_version', ''))} · "
            f"{(snapshot.get('target') or {}).get('serial', '未连接设备')}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 3, 5, 3)
        layout.setSpacing(6)

        self.status_dot = QLabel()
        self.status_dot.setObjectName("StatusDot")
        self.status_dot.setProperty("state", snapshot.get("status", "idle"))
        layout.addWidget(self.status_dot, 0, Qt.AlignmentFlag.AlignVCenter)

        copy = QVBoxLayout()
        copy.setSpacing(0)
        self.version_label = QLabel(display_version(snapshot.get("tool_version", "")))
        self.version_label.setObjectName("TabVersion")
        self.version_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        target = snapshot.get("target") or {}
        self.target_label = QLabel(target.get("serial") or "未连接设备")
        self.target_label.setObjectName("TabTarget")
        self.target_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        copy.addWidget(self.version_label)
        copy.addWidget(self.target_label)
        layout.addLayout(copy, 1)

        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("TabClose")
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setToolTip("关闭终端")
        self.close_button.clicked.connect(lambda: self.close_requested.emit(self.terminal_id))
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignVCenter)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.terminal_id)
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self.menu_requested.emit(self.terminal_id, event.globalPos())
        event.accept()


class TabScrollArea(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TerminalTabs")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def wheelEvent(self, event: QWheelEvent) -> None:
        bar = self.horizontalScrollBar()
        if bar.maximum() > 0:
            delta = event.angleDelta().y() or event.angleDelta().x()
            bar.setValue(bar.value() - delta // 2)
            event.accept()
            return
        super().wheelEvent(event)
