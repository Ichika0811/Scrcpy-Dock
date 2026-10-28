"""Application dialogs, styled to match the three-column workspace."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..parsers import is_valid_host, is_valid_port
from .native import apply_dark_titlebar
from .resources import app_pixmap


def _label(text: str, object_name: str = "", role: str = "", wrap: bool = False) -> QLabel:
    label = QLabel(text)
    if object_name:
        label.setObjectName(object_name)
    if role:
        label.setProperty("role", role)
    label.setWordWrap(wrap)
    return label


class AppDialog(QDialog):
    def __init__(
        self,
        title: str,
        description: str = "",
        *,
        width: int = 540,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("Scrcpy Dock")
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(width)
        self.setMaximumWidth(width + 180)
        self.setSizeGripEnabled(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("DialogHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 15, 18, 12)
        header_layout.setSpacing(3)
        header_layout.addWidget(_label(title, "DialogTitle"))
        if description:
            header_layout.addWidget(_label(description, "DialogDescription", wrap=True))
        root.addWidget(header)

        self.body = QWidget()
        self.body.setObjectName("DialogBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(18, 14, 18, 15)
        self.body_layout.setSpacing(12)
        self.body_scroll = QScrollArea()
        self.body_scroll.setObjectName("DialogScroll")
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.body_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body_scroll.setWidget(self.body)
        self.body_scroll.setMinimumHeight(120)
        root.addWidget(self.body_scroll, 1)
        self._sized_once = False

        self.footer = QFrame()
        self.footer.setObjectName("DialogFooter")
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(18, 10, 18, 10)
        footer_layout.setSpacing(7)
        footer_layout.addStretch(1)
        self._footer_layout = footer_layout
        root.addWidget(self.footer)

    def add_footer_button(self, text: str, *, kind: str = "ghost", slot=None) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("kind", kind)
        button.setMinimumHeight(30)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        if slot:
            button.clicked.connect(slot)
        self._footer_layout.addWidget(button)
        return button

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        apply_dark_titlebar(self)
        if not self._sized_once:
            self._sized_once = True
            screen = self.screen().availableGeometry() if self.screen() else None
            header_height = 88
            footer_height = self.footer.sizeHint().height() if not self.footer.isHidden() else 0
            body_height = self.body.sizeHint().height()
            target_height = header_height + body_height + footer_height + 8
            max_height = (screen.height() - 50) if screen else 720
            self.setMaximumHeight(max_height)
            self.resize(self.width(), max(280, min(target_height, max_height)))

    def add_error(self) -> QLabel:
        error = _label("", "ModalError", wrap=True)
        error.hide()
        self.body_layout.addWidget(error)
        return error

    @staticmethod
    def show_error(label: QLabel, message: str) -> None:
        label.setText(message)
        label.show()

    @staticmethod
    def clear_error(label: QLabel) -> None:
        label.hide()
        label.setText("")


def group_box(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("SettingsGroup")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(11, 9, 11, 10)
    layout.setSpacing(7)
    layout.addWidget(_label(title, "GroupTitle"))
    return frame, layout


def field_row(label_text: str, widget: QWidget, help_text: str = "") -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    label = _label(label_text, "FieldLabel")
    label.setFixedWidth(138)
    label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    layout.addWidget(label, 0, Qt.AlignmentFlag.AlignTop)
    right = QVBoxLayout()
    right.setSpacing(3)
    right.addWidget(widget)
    if help_text:
        right.addWidget(_label(help_text, "FormHelp", wrap=True))
    layout.addLayout(right, 1)
    return row


def form_field(label_text: str, widget: QWidget, help_text: str = "") -> QWidget:
    row = QWidget()
    layout = QVBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(_label(label_text, "FieldLabel"))
    layout.addWidget(widget)
    if help_text:
        layout.addWidget(_label(help_text, "FormHelp", wrap=True))
    return row


def inline_note(text: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("InlineNote")
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(8, 6, 8, 6)
    icon = _label("ⓘ", "InlineNoteText")
    icon.setStyleSheet("color:#5b8d85; font-size:12px;")
    layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
    layout.addWidget(_label(text, "InlineNoteText", wrap=True), 1)
    return frame


class ConfirmDialog(AppDialog):
    def __init__(
        self,
        title: str,
        message: str,
        detail: str = "",
        *,
        confirm_text: str = "确认",
        cancel_text: str = "取消",
        danger: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, "", width=420, parent=parent)
        content = QWidget()
        layout = QHBoxLayout(content)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(11)
        icon = QFrame()
        icon.setObjectName("ConfirmIcon")
        icon.setProperty("danger", "true" if danger else "false")
        icon_layout = QHBoxLayout(icon)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.addWidget(_label("⚠" if danger else "ⓘ"), 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        copy = QVBoxLayout()
        copy.setSpacing(4)
        copy.addWidget(_label(message, "ConfirmTitle", wrap=True))
        if detail:
            copy.addWidget(_label(detail, "ConfirmText", wrap=True))
        layout.addLayout(copy, 1)
        self.body_layout.addWidget(content)
        self.add_footer_button(cancel_text, kind="ghost", slot=self.reject)
        confirm = self.add_footer_button(
            confirm_text, kind="danger" if danger else "primary", slot=self.accept
        )
        confirm.setDefault(True)

    @classmethod
    def ask(
        cls,
        parent: QWidget | None,
        title: str,
        message: str,
        detail: str = "",
        *,
        confirm_text: str = "确认",
        danger: bool = False,
    ) -> bool:
        dialog = cls(
            title,
            message,
            detail,
            confirm_text=confirm_text,
            danger=danger,
            parent=parent,
        )
        return dialog.exec() == QDialog.DialogCode.Accepted


class VersionDialog(AppDialog):
    def __init__(self, tool: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(
            "修改版本标签",
            "自动识别来自 scrcpy --version；也可以使用自定义标签区分不同构建。",
            width=460,
            parent=parent,
        )
        self.auto_check = QCheckBox("自动使用检测到的版本")
        self.auto_check.setChecked(bool(tool.get("version_auto", True)))
        self.version_input = QLineEdit(tool.get("version", ""))
        self.version_input.setProperty("mono", "true")
        self.version_input.setEnabled(not self.auto_check.isChecked())
        self.auto_check.toggled.connect(
            lambda checked: self.version_input.setEnabled(not checked)
        )
        self.auto_check.toggled.connect(
            lambda checked: self.version_input.setText(tool.get("detected_version", ""))
            if checked
            else None
        )
        self.body_layout.addWidget(
            form_field("版本标签", self.version_input, "例如 3.1、3.1-mod、客厅盒子专用版")
        )
        self.body_layout.addWidget(self.auto_check)
        self.body_layout.addWidget(
            inline_note(f"当前检测结果：{tool.get('detected_version', '未知版本')}")
        )
        self.error = self.add_error()
        self.add_footer_button("取消", slot=self.reject)
        save = self.add_footer_button("保存", kind="primary", slot=self._save)
        save.setDefault(True)

    def _save(self) -> None:
        self.clear_error(self.error)
        if not self.auto_check.isChecked() and not self.version_input.text().strip():
            self.show_error(self.error, "版本标签不能为空")
            return
        self.accept()

    def value(self) -> dict[str, Any]:
        if self.auto_check.isChecked():
            return {"version_auto": True}
        return {"version": self.version_input.text().strip()}


class AddNetworkDialog(AppDialog):
    def __init__(self, auto_scan: bool, parent: QWidget | None = None) -> None:
        super().__init__(
            "添加设备 IP",
            "保存一个无线设备地址。可以在添加后自动扫描端口。",
            width=500,
            parent=parent,
        )
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("192.168.1.100")
        self.ip_input.setProperty("mono", "true")
        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("可选，例如 客厅电视")
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("可选，例如 5555")
        self.port_input.setProperty("mono", "true")
        self.auto_scan = QCheckBox("添加后自动扫描端口")
        self.auto_scan.setChecked(auto_scan)
        self.body_layout.addWidget(form_field("IP 地址 / 主机名", self.ip_input))
        self.body_layout.addWidget(form_field("设备名称", self.label_input))
        self.body_layout.addWidget(form_field("初始端口", self.port_input))
        self.body_layout.addWidget(self.auto_scan)
        self.body_layout.addWidget(
            inline_note("扫描只检查端口是否开放；点击端口时会再执行 adb connect 验证。")
        )
        self.error = self.add_error()
        self.add_footer_button("取消", slot=self.reject)
        save = self.add_footer_button("添加 IP", kind="primary", slot=self._save)
        save.setDefault(True)
        self.ip_input.setFocus()

    def _save(self) -> None:
        self.clear_error(self.error)
        ip = self.ip_input.text().strip()
        if not is_valid_host(ip):
            self.show_error(self.error, "请输入有效的 IP 地址或主机名")
            return
        port_text = self.port_input.text().strip()
        if port_text and not is_valid_port(port_text):
            self.show_error(self.error, "端口号必须在 1–65535 之间")
            return
        self.accept()

    def values(self) -> dict[str, Any]:
        port_text = self.port_input.text().strip()
        return {
            "ip": self.ip_input.text().strip(),
            "label": self.label_input.text().strip(),
            "port": int(port_text) if port_text else None,
            "auto_scan": self.auto_scan.isChecked(),
        }


class EditNetworkDialog(AppDialog):
    def __init__(self, network: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__("编辑 IP", "名称会显示在右侧设备栏和终端标签中。", width=450, parent=parent)
        self.ip_input = QLineEdit(network.get("ip", ""))
        self.ip_input.setProperty("mono", "true")
        self.label_input = QLineEdit(network.get("label", ""))
        self.body_layout.addWidget(form_field("IP 地址 / 主机名", self.ip_input))
        self.body_layout.addWidget(form_field("设备名称", self.label_input))
        self.error = self.add_error()
        self.add_footer_button("取消", slot=self.reject)
        save = self.add_footer_button("保存", kind="primary", slot=self._save)
        save.setDefault(True)

    def _save(self) -> None:
        self.clear_error(self.error)
        if not is_valid_host(self.ip_input.text().strip()):
            self.show_error(self.error, "请输入有效的 IP 地址或主机名")
            return
        self.accept()

    def values(self) -> dict[str, str]:
        return {"ip": self.ip_input.text().strip(), "label": self.label_input.text().strip()}


class AddPortDialog(AppDialog):
    def __init__(self, network: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(
            f"添加端口 · {network.get('ip', '')}",
            "用于扫描范围以外的端口，例如随机无线调试端口。",
            width=400,
            parent=parent,
        )
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("5555")
        self.port_input.setProperty("mono", "true")
        self.body_layout.addWidget(form_field("端口号", self.port_input))
        self.error = self.add_error()
        self.add_footer_button("取消", slot=self.reject)
        save = self.add_footer_button("添加端口", kind="primary", slot=self._save)
        save.setDefault(True)
        self.port_input.setFocus()

    def _save(self) -> None:
        self.clear_error(self.error)
        if not is_valid_port(self.port_input.text().strip()):
            self.show_error(self.error, "端口号必须在 1–65535 之间")
            return
        self.accept()

    def port(self) -> int:
        return int(self.port_input.text().strip())


class ToolSettingsDialog(AppDialog):
    add_requested = Signal()
    batch_requested = Signal()
    rescan_requested = Signal()
    edit_version_requested = Signal()

    def __init__(
        self,
        config,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            "scrcpy 版本设置",
            "管理版本库，并配置所有终端共用的 scrcpy 参数。",
            width=600,
            parent=parent,
        )
        sheet = config.settings
        tools = config.tools
        group, layout = group_box("版本库")
        stats = _label(
            f"已添加 {len(tools)} 个版本 · 收藏 {sum(1 for tool in tools if tool.get('favorite'))} 个",
            "FormHelp",
        )
        layout.addWidget(stats)
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        add = QPushButton("＋ 单个添加")
        add.setProperty("kind", "ghost")
        add.clicked.connect(self.add_requested.emit)
        batch = QPushButton("▣ 批量扫描父文件夹")
        batch.setProperty("kind", "ghost")
        batch.clicked.connect(self.batch_requested.emit)
        rescan = QPushButton("⟳ 重新检测全部")
        rescan.setProperty("kind", "ghost")
        rescan.clicked.connect(self.rescan_requested.emit)
        edit_version = QPushButton("✎ 修改当前版本")
        edit_version.setProperty("kind", "ghost")
        edit_version.clicked.connect(self.edit_version_requested.emit)
        buttons.addWidget(add)
        buttons.addWidget(batch)
        buttons.addWidget(rescan)
        buttons.addWidget(edit_version)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.body_layout.addWidget(group)

        group2, layout2 = group_box("启动参数")
        self.default_args = QTextEdit()
        self.default_args.setPlainText(str(sheet.get("default_args") or ""))
        self.default_args.setFixedHeight(74)
        self.default_args.setPlaceholderText("--max-size=1920 --video-bit-rate=8M")
        layout2.addWidget(
            form_field(
                "默认附加参数",
                self.default_args,
                "会追加到每条 scrcpy 命令。参数是否可用取决于所选 scrcpy 版本。",
            )
        )
        self.body_layout.addWidget(group2)
        self.add_footer_button("取消", slot=self.reject)
        save = self.add_footer_button("保存设置", kind="primary", slot=self.accept)
        save.setDefault(True)

    def default_args_value(self) -> str:
        return self.default_args.toPlainText().strip()


class NetworkSettingsDialog(AppDialog):
    open_data_requested = Signal()
    open_logs_requested = Signal()
    refresh_requested = Signal()

    def __init__(
        self,
        config,
        adb_info: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            "IP 与 ADB 设置",
            "无线连接、端口扫描与终端缓冲设置。",
            width=620,
            parent=parent,
        )
        sheet = config.settings
        group, layout = group_box("ADB")
        adb_row = QWidget()
        adb_layout = QHBoxLayout(adb_row)
        adb_layout.setContentsMargins(0, 0, 0, 0)
        adb_layout.setSpacing(5)
        self.adb_path = QLineEdit(str(sheet.get("adb_path") or ""))
        self.adb_path.setPlaceholderText("自动检测（推荐）")
        self.adb_path.setProperty("mono", "true")
        browse = QPushButton("浏览")
        browse.setProperty("kind", "ghost")
        browse.clicked.connect(self._browse_adb)
        auto = QPushButton("自动")
        auto.setProperty("kind", "ghost")
        auto.clicked.connect(lambda: self.adb_path.setText(""))
        adb_layout.addWidget(self.adb_path, 1)
        adb_layout.addWidget(browse)
        adb_layout.addWidget(auto)
        layout.addWidget(form_field("ADB 可执行文件", adb_row))
        current = adb_info.get("path") if adb_info.get("available") else "未找到 ADB"
        layout.addWidget(_label(f"当前生效：{current}", "FormHelp", wrap=True))
        self.auto_connect = QCheckBox("点击端口时先执行 adb connect")
        self.auto_connect.setChecked(bool(sheet.get("auto_adb_connect")))
        layout.addWidget(self.auto_connect)
        self.auto_import = QCheckBox("自动导入 ADB 已连接的无线设备")
        self.auto_import.setChecked(bool(sheet.get("auto_import_adb_devices", True)))
        layout.addWidget(self.auto_import)
        self.body_layout.addWidget(group)

        group2, layout2 = group_box("端口扫描")
        self.auto_scan = QCheckBox("添加 IP 后自动扫描端口")
        self.auto_scan.setChecked(bool(sheet.get("auto_scan")))
        layout2.addWidget(self.auto_scan)
        self.scan_full = QCheckBox("自动扫描使用全端口 1–65535（较慢，推荐远端 Docker）")
        self.scan_full.setChecked(bool(sheet.get("scan_full", True)))
        layout2.addWidget(self.scan_full)
        self.use_docker = QCheckBox("合并 docker ps 中发布的 Android / ADB 端口")
        self.use_docker.setChecked(bool(sheet.get("use_docker_ports", True)))
        layout2.addWidget(self.use_docker)
        range_row = QWidget()
        range_layout = QHBoxLayout(range_row)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.setSpacing(6)
        self.scan_start = QSpinBox()
        self.scan_start.setRange(1, 65535)
        self.scan_start.setValue(int(sheet.get("scan_start", 5555)))
        self.scan_end = QSpinBox()
        self.scan_end.setRange(1, 65535)
        self.scan_end.setValue(int(sheet.get("scan_end", 5585)))
        self.timeout = QComboBox()
        for value in (150, 250, 420, 650, 900, 1200):
            self.timeout.addItem(f"{value} ms", value)
        index = self.timeout.findData(int(sheet.get("scan_timeout_ms", 420)))
        self.timeout.setCurrentIndex(max(0, index))
        full_button = QPushButton("全端口")
        full_button.setProperty("kind", "link")
        full_button.setToolTip("设置 1–65535，并临时使用 150 ms 超时")
        full_button.clicked.connect(self._use_full_range)
        range_layout.addWidget(self.scan_start)
        range_layout.addWidget(_label("—", "FormHelp"))
        range_layout.addWidget(self.scan_end)
        range_layout.addSpacing(8)
        range_layout.addWidget(self.timeout)
        range_layout.addWidget(full_button)
        range_layout.addStretch(1)
        layout2.addWidget(
            form_field(
                "端口范围 / 超时",
                range_row,
                "支持 1–65535 全端口扫描；全端口较慢，Docker 映射端口会自动加入候选。",
            )
        )
        self.body_layout.addWidget(group2)

        group3, layout3 = group_box("终端与文件")
        self.max_lines = QComboBox()
        for value in (2000, 5000, 10000, 20000):
            self.max_lines.addItem(f"{value} 行", value)
        idx = self.max_lines.findData(int(sheet.get("max_terminal_lines", 5000)))
        self.max_lines.setCurrentIndex(max(0, idx))
        layout3.addWidget(form_field("输出缓冲", self.max_lines))
        links = QHBoxLayout()
        links.setSpacing(5)
        data_button = QPushButton("▣ 数据目录")
        data_button.setProperty("kind", "ghost")
        data_button.clicked.connect(self.open_data_requested.emit)
        logs_button = QPushButton("▤ 日志目录")
        logs_button.setProperty("kind", "ghost")
        logs_button.clicked.connect(self.open_logs_requested.emit)
        refresh_button = QPushButton("⟳ 刷新设备名")
        refresh_button.setProperty("kind", "ghost")
        refresh_button.clicked.connect(self.refresh_requested.emit)
        links.addWidget(data_button)
        links.addWidget(logs_button)
        links.addWidget(refresh_button)
        links.addStretch(1)
        layout3.addLayout(links)
        self.body_layout.addWidget(group3)

        self.error = self.add_error()
        self.add_footer_button("取消", slot=self.reject)
        save = self.add_footer_button("保存设置", kind="primary", slot=self._save)
        save.setDefault(True)

    def _browse_adb(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 adb.exe",
            self.adb_path.text() or "",
            "ADB (adb.exe);;Executable (*.exe)",
        )
        if path:
            self.adb_path.setText(path)

    def _use_full_range(self) -> None:
        self.scan_start.setValue(1)
        self.scan_end.setValue(65535)
        index = self.timeout.findData(150)
        if index >= 0:
            self.timeout.setCurrentIndex(index)

    def _save(self) -> None:
        self.clear_error(self.error)
        if self.scan_start.value() > self.scan_end.value():
            self.show_error(self.error, "扫描起始端口不能大于结束端口")
            return
        path = self.adb_path.text().strip()
        if path and not path.lower().endswith("adb.exe"):
            self.show_error(self.error, "请选择名为 adb.exe 的文件")
            return
        self.accept()

    def values(self) -> dict[str, Any]:
        return {
            "adb_path": self.adb_path.text().strip(),
            "auto_adb_connect": self.auto_connect.isChecked(),
            "auto_import_adb_devices": self.auto_import.isChecked(),
            "use_docker_ports": self.use_docker.isChecked(),
            "auto_scan": self.auto_scan.isChecked(),
            "scan_full": self.scan_full.isChecked(),
            "scan_start": self.scan_start.value(),
            "scan_end": self.scan_end.value(),
            "scan_timeout_ms": int(self.timeout.currentData()),
            "max_terminal_lines": int(self.max_lines.currentData()),
        }


class BusyDialog(AppDialog):
    """Small indeterminate progress dialog for filesystem/version work."""

    def __init__(self, message: str, parent: QWidget | None = None) -> None:
        super().__init__("请稍候", message, width=380, parent=parent)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        bar = QProgressBar()
        bar.setRange(0, 0)
        bar.setTextVisible(False)
        bar.setFixedHeight(5)
        self.body_layout.addWidget(bar)
        self.footer.hide()
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)


class AboutDialog(AppDialog):
    """In-app software/version/runtime information page."""

    def __init__(
        self,
        info: dict[str, Any],
        *,
        on_open_data,
        on_open_logs,
        on_copy,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            "关于 Scrcpy Dock",
            "软件版本、运行环境和本地数据路径。",
            width=640,
            parent=parent,
        )

        hero = QWidget()
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(0, 0, 0, 2)
        hero_layout.setSpacing(14)
        logo = QLabel()
        logo.setFixedSize(64, 64)
        logo.setPixmap(app_pixmap(64))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)
        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(3)
        title = _label("Scrcpy Dock", "AboutAppName")
        version = _label(f"版本 {info.get('version', '')}", "AboutVersion")
        subtitle = _label(
            "多版本 scrcpy · 无线设备 · 多终端统一工作台",
            "AboutSubtitle",
        )
        hero_copy.addWidget(title)
        hero_copy.addWidget(version)
        hero_copy.addWidget(subtitle)
        hero_layout.addLayout(hero_copy, 1)
        self.body_layout.addWidget(hero)
        self.body_layout.addWidget(inline_note(
            "scrcpy 画面使用 scrcpy 原生窗口；Scrcpy Dock 负责版本、ADB、端口、进程和日志管理。"
        ))

        version_group, version_layout = group_box("版本与运行环境")
        version_layout.addWidget(self._row("软件版本", info.get("version", ""), mono=True))
        version_layout.addWidget(self._row("构建日期", info.get("build_time", "")))
        version_layout.addWidget(self._row("Qt / PySide6", f"{info.get('qt', '')} / {info.get('pyside', '')}", mono=True))
        version_layout.addWidget(self._row("Python", info.get("python", ""), mono=True))
        version_layout.addWidget(self._row("操作系统", info.get("os", "")))
        version_layout.addWidget(self._row("可执行文件", info.get("executable", ""), mono=True, wrap=True))
        self.body_layout.addWidget(version_group)

        stats_group, stats_layout = group_box("当前工作区")
        stats_layout.addWidget(
            self._row(
                "scrcpy 版本",
                f"{info.get('tools_count', 0)} 个（收藏 {info.get('favorites', 0)} 个）",
            )
        )
        stats_layout.addWidget(
            self._row(
                "IP / 端口",
                f"{info.get('networks_count', 0)} 个 IP，{info.get('ports_count', 0)} 个端口",
            )
        )
        stats_layout.addWidget(
            self._row(
                "终端",
                f"{info.get('terminals_total', 0)} 个，运行中 {info.get('terminals_running', 0)} 个",
            )
        )
        stats_layout.addWidget(self._row("ADB", info.get("adb", ""), mono=True, wrap=True))
        self.body_layout.addWidget(stats_group)

        data_group, data_layout = group_box("数据位置")
        data_layout.addWidget(self._row("数据目录", info.get("data_dir", ""), mono=True, wrap=True))
        data_layout.addWidget(self._row("日志目录", info.get("logs_dir", ""), mono=True, wrap=True))
        data_layout.addWidget(self._row("配置文件", info.get("config_path", ""), mono=True, wrap=True))
        links = QHBoxLayout()
        links.setSpacing(6)
        data_button = QPushButton("▣ 打开数据目录")
        data_button.setProperty("kind", "ghost")
        data_button.clicked.connect(on_open_data)
        log_button = QPushButton("▤ 打开日志目录")
        log_button.setProperty("kind", "ghost")
        log_button.clicked.connect(on_open_logs)
        copy_button = QPushButton("⧉ 复制诊断信息")
        copy_button.setProperty("kind", "ghost")

        def copy_diagnostics() -> None:
            on_copy()
            copy_button.setText("✓ 已复制")
            reset = QTimer(copy_button)
            reset.setSingleShot(True)
            reset.timeout.connect(lambda: copy_button.setText("⧉ 复制诊断信息"))
            reset.start(1800)

        copy_button.clicked.connect(copy_diagnostics)
        links.addWidget(data_button)
        links.addWidget(log_button)
        links.addWidget(copy_button)
        links.addStretch(1)
        data_layout.addLayout(links)
        self.body_layout.addWidget(data_group)

        credits = _label(
            "Scrcpy Dock 1.x · Python + PySide6 · 使用 Genymobile scrcpy 与 Android platform-tools。",
            "FormHelp",
            wrap=True,
        )
        self.body_layout.addWidget(credits)
        self.add_footer_button("关闭", kind="primary", slot=self.accept)

    @staticmethod
    def _row(label_text: str, value: str, *, mono: bool = False, wrap: bool = False) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        label = _label(label_text, "FieldLabel")
        label.setFixedWidth(105)
        label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(label, 0, Qt.AlignmentFlag.AlignTop)
        text = _label(str(value or "—"), "FormHelp" if not mono else "FormHelp", wrap=wrap)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if mono:
            text.setStyleSheet(
                'font-family:"Cascadia Mono","Cascadia Code",Consolas,monospace;font-size:9px;color:#7d8da3;'
            )
        text.setWordWrap(wrap)
        layout.addWidget(text, 1)
        return row

