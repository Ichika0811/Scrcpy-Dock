"""Custom multi-line terminal tabs."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QContextMenuEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .icons import set_button_icon
from .rails import display_version

TAB_ACCENTS = (
    "#5eead4",
    "#78a9ff",
    "#c4a7ff",
    "#fb7185",
    "#fbbf24",
    "#4ade80",
    "#fb923c",
    "#67e8f9",
)


def tab_accent(index: int) -> str:
    """Return a stable, visually distinct accent for any tab number."""
    index = max(1, int(index))
    if index <= len(TAB_ACCENTS):
        return TAB_ACCENTS[index - 1]
    hue = int((index * 137.508) % 360)
    return QColor.fromHsl(hue, 165, 185).name()


def _rgba(color: str, alpha: int) -> str:
    value = QColor(color)
    return f"rgba({value.red()}, {value.green()}, {value.blue()}, {alpha})"


class TerminalTab(QFrame):
    selected = Signal(str)
    close_requested = Signal(str)
    menu_requested = Signal(str, QPoint)
    move_requested = Signal(str, str, bool)

    def __init__(
        self,
        snapshot: dict[str, Any],
        *,
        active: bool,
        index: int = 1,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.terminal_id = snapshot["id"]
        self.index = max(1, int(index))
        self.accent = tab_accent(self.index)
        self._press_pos: QPoint | None = None
        self._dragging = False
        self.setObjectName("TerminalTab")
        self.setProperty("active", "true" if active else "false")
        self.setProperty("notool", "false" if snapshot.get("tool_id") else "true")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(200)
        self.setFixedHeight(36)
        raw_version = display_version(snapshot.get("tool_version", ""))
        self.setToolTip(
            f"终端 {self.index} · {raw_version} · "
            f"{(snapshot.get('target') or {}).get('serial', '未连接设备')}\n"
            "拖动标签可调整顺序"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 3, 5, 3)
        layout.setSpacing(5)

        self.accent_bar = QFrame()
        self.accent_bar.setFixedWidth(3)
        self.accent_bar.setFixedHeight(26)
        self.accent_bar.setStyleSheet(
            f"background-color: {_rgba(self.accent, 220 if active else 120)};"
            "border-radius: 1px;"
        )
        layout.addWidget(self.accent_bar, 0, Qt.AlignmentFlag.AlignVCenter)

        self.number_label = QLabel(str(self.index))
        self.number_label.setObjectName("TabNumber")
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_label.setFixedSize(20, 20)
        self.number_label.setStyleSheet(
            f"background-color: {_rgba(self.accent, 235 if active else 24)};"
            f"border: 1px solid {_rgba(self.accent, 230 if active else 120)};"
            "border-radius: 10px;"
            f"color: {'#071018' if active else self.accent};"
            "font-size: 9px; font-weight: 700;"
        )
        layout.addWidget(self.number_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.status_dot = QLabel()
        self.status_dot.setObjectName("StatusDot")
        self.status_dot.setProperty("state", snapshot.get("status", "idle"))
        layout.addWidget(self.status_dot, 0, Qt.AlignmentFlag.AlignVCenter)

        copy = QVBoxLayout()
        copy.setSpacing(0)
        self.version_label = QLabel(f"终端 {self.index} · {raw_version}")
        self.version_label.setObjectName("TabVersion")
        self.version_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        target = snapshot.get("target") or {}
        self.target_label = QLabel(target.get("serial") or "未连接设备")
        self.target_label.setObjectName("TabTarget")
        self.target_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        copy.addWidget(self.version_label)
        copy.addWidget(self.target_label)
        layout.addLayout(copy, 1)

        self.close_button = QPushButton("")
        self.close_button.setObjectName("TabClose")
        set_button_icon(self.close_button, "close", 14)
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setToolTip("关闭终端")
        self.close_button.clicked.connect(lambda: self.close_requested.emit(self.terminal_id))
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignVCenter)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._press_pos is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and (event.position().toPoint() - self._press_pos).manhattanLength()
            >= QApplication.startDragDistance()
        ):
            self._dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        was_dragging = self._dragging
        if event.button() == Qt.MouseButton.LeftButton and not was_dragging:
            self.selected.emit(self.terminal_id)
        if was_dragging:
            content = self.parentWidget()
            target = None
            if content is not None:
                point = content.mapFromGlobal(event.globalPosition().toPoint())
                target = content.childAt(point)
                while target is not None and not isinstance(target, TerminalTab):
                    target = target.parentWidget()
            if target is not None and target.terminal_id != self.terminal_id:
                left = target.mapToGlobal(QPoint(0, 0)).x()
                before = event.globalPosition().x() < left + target.width() / 2
                self.move_requested.emit(self.terminal_id, target.terminal_id, before)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._press_pos = None
        self._dragging = False
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self.menu_requested.emit(self.terminal_id, event.globalPos())
        event.accept()


class TerminalSwitcherDialog(QDialog):
    """Searchable terminal switcher used by the tab-bar list button."""

    def __init__(
        self,
        entries: list[tuple[str, str]],
        current_id: str | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("切换终端")
        self.setModal(True)
        self.resize(460, 380)
        self.selected_id: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(8)
        title = QLabel("所有终端")
        title.setObjectName("DialogTitle")
        layout.addWidget(title)
        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText("搜索终端编号、版本或设备地址")
        layout.addWidget(self.search)
        self.list = QListWidget()
        self.list.setObjectName("TerminalSwitcherList")
        for terminal_id, label in entries:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, terminal_id)
            self.list.addItem(item)
            if terminal_id == current_id:
                self.list.setCurrentItem(item)
        layout.addWidget(self.list, 1)
        cancel = QPushButton("取消")
        cancel.setProperty("kind", "ghost")
        cancel.clicked.connect(self.reject)
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(cancel)
        layout.addLayout(footer)

        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self._choose_current)
        self.list.itemActivated.connect(self._choose)
        self.list.itemDoubleClicked.connect(self._choose)
        self.search.setFocus()

    def _filter(self, text: str) -> None:
        needle = str(text or "").strip().casefold()
        first_visible: QListWidgetItem | None = None
        for index in range(self.list.count()):
            item = self.list.item(index)
            hidden = bool(needle) and needle not in item.text().casefold()
            item.setHidden(hidden)
            if not hidden and first_visible is None:
                first_visible = item
        if first_visible is not None:
            self.list.setCurrentItem(first_visible)

    def _choose_current(self) -> None:
        item = self.list.currentItem()
        if item is not None and not item.isHidden():
            self._choose(item)

    def _choose(self, item: QListWidgetItem) -> None:
        self.selected_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if self.selected_id:
            self.accept()


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
            if not delta:
                delta = (event.pixelDelta().y() or event.pixelDelta().x()) * 8
            if delta:
                bar.setValue(bar.value() - delta // 2)
                event.accept()
                return
        super().wheelEvent(event)
