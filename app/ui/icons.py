"""DPI-aware loading for the built-in SVG action icons."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QPushButton

from .resources import assets_dir


def icon_path(name: str) -> Path:
    return assets_dir() / "icons" / f"{name}.svg"


def ui_icon(name: str) -> QIcon:
    path = icon_path(name)
    return QIcon(str(path)) if path.is_file() else QIcon()


def ui_pixmap(name: str, width: int, height: int | None = None) -> QPixmap:
    width = max(1, int(width))
    height = max(1, int(height or width))
    icon = ui_icon(name)
    screen = QApplication.primaryScreen()
    ratio = float(screen.devicePixelRatio()) if screen else 1.0
    try:
        pixmap = icon.pixmap(QSize(width, height), ratio)
    except TypeError:
        pixmap = icon.pixmap(QSize(width, height))
    if pixmap.isNull():
        pixmap = QPixmap(width, height)
        pixmap.fill()
    return pixmap


def set_button_icon(button: QPushButton, name: str, size: int = 18) -> None:
    button.setText("")
    button.setIcon(ui_icon(name))
    button.setIconSize(QSize(size, size))
