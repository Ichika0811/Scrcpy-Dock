"""Left and right rail cards built with Qt widgets."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QContextMenuEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

SOURCE_LABELS = {
    "scan": "扫描发现",
    "connect": "已连接",
    "manual": "手动添加",
    "device": "ADB 识别",
    "history": "历史记录",
    "docker": "Docker 映射",
}


def repolish(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def make_label(
    text: str,
    *,
    role: str = "",
    object_name: str = "",
    word_wrap: bool = False,
) -> QLabel:
    label = QLabel(text)
    if role:
        label.setProperty("role", role)
    if object_name:
        label.setObjectName(object_name)
    label.setWordWrap(word_wrap)
    return label


def display_version(version: str) -> str:
    if not version or version == "未选择版本":
        return "未选择版本"
    return version if version.lower().startswith("scrcpy") else f"scrcpy {version}"


class ToolBadge(QWidget):
    """Small Android-head mark tinted with the version color."""

    def __init__(self, color: str, *, active: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor(color or "#5eead4")
        if not self._color.isValid():
            self._color = QColor("#5eead4")
        self._active = active
        self.setObjectName("ToolBadge")
        self.setFixedSize(32, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("右键可更改图标颜色")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            background = QColor(self._color)
            background.setAlpha(38 if self._active else 20)
            border = QColor(self._color)
            border.setAlpha(115 if self._active else 68)
            painter.setPen(QPen(border, 1))
            painter.setBrush(background)
            painter.drawRoundedRect(QRectF(1.5, 1.5, 29, 29), 8, 8)

            head = QColor(self._color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(head)
            painter.drawEllipse(QRectF(8, 10, 16, 11))
            painter.drawRect(QRectF(8, 15.5, 16, 6.5))

            antenna = QPen(head, 1.8)
            antenna.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(antenna)
            painter.drawLine(QPointF(11.5, 14.5), QPointF(8.8, 10.4))
            painter.drawLine(QPointF(20.5, 14.5), QPointF(23.2, 10.4))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#07110d"))
            painter.drawEllipse(QRectF(12.0, 16.4, 2.8, 2.8))
            painter.drawEllipse(QRectF(19.2, 16.4, 2.8, 2.8))
        finally:
            painter.end()


class ToolCard(QFrame):
    selected = Signal(str)
    favorite_toggled = Signal(str)
    menu_requested = Signal(str, QPoint)

    def __init__(self, tool: dict[str, Any], *, active: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tool = tool
        self.setObjectName("ToolCard")
        self.setProperty("active", "true" if active else "false")
        self.setProperty("missing", "true" if tool.get("missing") else "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(tool.get("scrcpy_path", ""))

        root = QVBoxLayout(self)
        root.setContentsMargins(9, 8, 7, 7)
        root.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(8)
        badge = ToolBadge(
            str(tool.get("color") or "#5eead4"),
            active=active,
        )
        badge.setToolTip(
            f"scrcpy {tool.get('version', '')} · 右键可更改图标颜色"
        )
        top.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setSpacing(2)
        name_row = QHBoxLayout()
        name_row.setSpacing(5)
        name = make_label(display_version(tool.get("version", "")), role="toolName")
        name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        name_row.addWidget(name, 1)
        tag = make_label("AUTO" if tool.get("version_auto", True) else "自定义", role="autoTag" if tool.get("version_auto", True) else "customTag")
        if not tool.get("version_auto", True):
            tag.setToolTip(f"自动检测到：scrcpy {tool.get('detected_version', '未知版本')}")
        name_row.addWidget(tag, 0)
        copy.addLayout(name_row)
        path = make_label(PathTail.of(tool.get("folder", "")), role="toolPath")
        path.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        copy.addWidget(path)
        top.addLayout(copy, 1)

        self.favorite_button = QPushButton("★" if tool.get("favorite") else "☆")
        self.favorite_button.setProperty("kind", "favorite")
        self.favorite_button.setProperty("favorite", "true" if tool.get("favorite") else "false")
        self.favorite_button.setToolTip("取消收藏" if tool.get("favorite") else "收藏")
        self.favorite_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.favorite_button.clicked.connect(lambda: self.favorite_toggled.emit(self.tool["id"]))
        top.addWidget(self.favorite_button, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(40, 0, 1, 0)
        bottom.setSpacing(5)
        adb = make_label(
            "● 内置 ADB" if tool.get("adb_available") else "○ 共享 ADB",
            object_name="ToolAdb",
        )
        adb.setProperty("ok", "true" if tool.get("adb_available") else "false")
        bottom.addWidget(adb)
        if tool.get("missing"):
            missing = make_label("路径失效", object_name="CurrentMark")
            missing.setStyleSheet("color:#d88490;")
            bottom.addWidget(missing)
        if active:
            bottom.addStretch(1)
            current = make_label("当前终端", object_name="CurrentMark")
            bottom.addWidget(current)
        root.addLayout(bottom)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.tool["id"])
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: Any) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.selected.emit(self.tool["id"])
            event.accept()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self.menu_requested.emit(self.tool["id"], event.globalPos())
        event.accept()


class PathTail:
    @staticmethod
    def of(path: str) -> str:
        parts = [part for part in str(path or "").replace("\\", "/").split("/") if part]
        return parts[-1] if parts else str(path or "")


class ClickableFrame(QFrame):
    clicked = Signal()
    context_requested = Signal(QPoint)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self.context_requested.emit(event.globalPos())
        event.accept()


class PortRow(QFrame):
    clicked = Signal(str, int)
    menu_requested = Signal(str, int, QPoint)

    def __init__(
        self,
        network_id: str,
        entry: dict[str, Any],
        *,
        active: bool,
        online: bool,
        fallback_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.network_id = network_id
        self.port = int(entry["port"])
        self.setObjectName("PortRow")
        self.setProperty("active", "true" if active else "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"连接到当前终端：端口 {self.port}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 4, 6, 4)
        layout.setSpacing(7)

        state = "online" if online else (
            "running" if entry.get("last_status") == "success" else "failed" if entry.get("last_status") == "failed" else "idle"
        )
        dot = QLabel()
        dot.setObjectName("StatusDot")
        dot.setProperty("state", state)
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)

        copy = QVBoxLayout()
        copy.setSpacing(1)
        line = QHBoxLayout()
        line.setSpacing(5)
        port_label = make_label(str(self.port), object_name="PortNumber")
        device = make_label(
            entry.get("device_name") or fallback_name or "待识别设备",
            object_name="PortDevice",
        )
        device.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        line.addWidget(port_label)
        line.addWidget(device, 1)
        copy.addLayout(line)
        source = SOURCE_LABELS.get(entry.get("source", ""), "端口")
        if online:
            source += " · 在线"
        copy.addWidget(make_label(source, object_name="PortSource"))
        layout.addLayout(copy, 1)

        arrow = make_label("›", object_name="PortArrow")
        layout.addWidget(arrow, 0, Qt.AlignmentFlag.AlignVCenter)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.network_id, self.port)
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self.menu_requested.emit(self.network_id, self.port, event.globalPos())
        event.accept()


class NetworkCard(QFrame):
    toggle_requested = Signal(str)
    port_clicked = Signal(str, int)
    port_context_requested = Signal(str, int, QPoint)
    menu_requested = Signal(str, QPoint)
    scan_requested = Signal(str)
    quick_scan_requested = Signal(str)
    add_port_requested = Signal(str)

    def __init__(
        self,
        network: dict[str, Any],
        *,
        expanded: bool,
        current: bool,
        active_port: int | None,
        online_ports: set[int],
        scanning: bool,
        fallback_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.network = network
        self.setObjectName("NetworkCard")
        self.setProperty("current", "true" if current else "false")
        self.setProperty("expanded", "true" if expanded else "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = ClickableFrame()
        header.setObjectName("NetworkHeader")
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.clicked.connect(lambda: self.toggle_requested.emit(self.network["id"]))
        header.context_requested.connect(
            lambda pos: self.menu_requested.emit(self.network["id"], pos)
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 8, 7, 7)
        header_layout.setSpacing(7)

        chevron = make_label("⌄" if expanded else "›", object_name="Chevron")
        chevron.setFixedWidth(12)
        header_layout.addWidget(chevron, 0, Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setSpacing(2)
        name_row = QHBoxLayout()
        name_row.setSpacing(5)
        name = make_label(network.get("label") or network["ip"], object_name="NetworkName")
        name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        name_row.addWidget(name, 1)
        online = bool(online_ports)
        dot = QLabel()
        dot.setObjectName("StatusDot")
        dot.setProperty("state", "online" if online else "idle")
        name_row.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        copy.addLayout(name_row)
        ip_text = (
            network["ip"]
            if network.get("label")
            else f"{len(network.get('ports') or [])} 个端口"
        )
        copy.addWidget(make_label(ip_text, object_name="NetworkIp"))
        header_layout.addLayout(copy, 1)

        count = make_label(f"{len(network.get('ports') or [])}")
        count.setObjectName("PortCount")
        count.setToolTip("保存的端口数量")
        header_layout.addWidget(count, 0, Qt.AlignmentFlag.AlignTop)
        root.addWidget(header)

        if expanded:
            body = QWidget()
            body_layout = QVBoxLayout(body)
            body_layout.setContentsMargins(28, 0, 6, 6)
            body_layout.setSpacing(2)
            ports = list(network.get("ports") or [])
            ports.sort(
                key=lambda entry: (
                    not (active_port == entry["port"] and current),
                    -(entry.get("last_connected_at") or entry.get("last_attempt_at") or 0),
                    entry["port"],
                )
            )
            if ports:
                for entry in ports:
                    row = PortRow(
                        network["id"],
                        entry,
                        active=bool(current and active_port == entry["port"]),
                        online=entry["port"] in online_ports,
                        fallback_name=fallback_name,
                    )
                    row.clicked.connect(self.port_clicked)
                    row.menu_requested.connect(self.port_context_requested)
                    body_layout.addWidget(row)
            else:
                empty = QFrame()
                empty.setObjectName("NetworkEmpty")
                empty_layout = QHBoxLayout(empty)
                empty_layout.setContentsMargins(7, 5, 7, 5)
                empty_layout.addWidget(make_label("尚未发现端口", object_name="PortSource"), 1)
                scan = QPushButton("全端口")
                scan.setProperty("kind", "ghost")
                scan.setFixedHeight(22)
                scan.setToolTip("扫描 1–65535")
                scan.clicked.connect(lambda: self.scan_requested.emit(self.network["id"]))
                empty_layout.addWidget(scan)
                body_layout.addWidget(empty)

            actions = QHBoxLayout()
            actions.setContentsMargins(0, 3, 0, 0)
            actions.setSpacing(4)
            full_scan_button = QPushButton("◉ 全端口" if not scanning else "◌ 正在扫描…")
            full_scan_button.setProperty("kind", "link")
            full_scan_button.setEnabled(not scanning)
            full_scan_button.setToolTip("扫描 1–65535，并验证 ADB 端口；需要几十秒")
            full_scan_button.clicked.connect(lambda: self.scan_requested.emit(self.network["id"]))
            quick_button = QPushButton("⟳ 快速")
            quick_button.setProperty("kind", "link")
            quick_button.setEnabled(not scanning)
            quick_button.setToolTip("只扫描设置的常用端口范围")
            quick_button.clicked.connect(
                lambda: self.quick_scan_requested.emit(self.network["id"])
            )
            add_port = QPushButton("＋ 手动端口")
            add_port.setProperty("kind", "link")
            add_port.clicked.connect(lambda: self.add_port_requested.emit(self.network["id"]))
            actions.addWidget(full_scan_button)
            actions.addWidget(quick_button)
            actions.addWidget(add_port)
            actions.addStretch(1)
            body_layout.addLayout(actions)
            root.addWidget(body)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self.menu_requested.emit(self.network["id"], event.globalPos())
        event.accept()
