"""Application icon loading with a packaged-path fallback."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap


def assets_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).resolve().parent.parent.parent / "assets"


def app_icon() -> QIcon:
    icon_path = assets_dir() / "icon.ico"
    if icon_path.is_file():
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            return icon
    return QIcon(app_pixmap(64))


def app_pixmap(size: int) -> QPixmap:
    """High-resolution in-app logo, loaded from the same icon artwork."""
    png_path = assets_dir() / "icon.png"
    if png_path.is_file():
        pixmap = QPixmap(str(png_path))
        if not pixmap.isNull():
            return pixmap.scaled(
                int(size),
                int(size),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
    return _fallback_pixmap(int(size))


def _fallback_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#06080b"))
        painter.drawRoundedRect(QRectF(2, 2, 60, 60), 14, 14)
        painter.setBrush(QColor("#0b0f13"))
        painter.setPen(QColor("#2b333a"))
        painter.drawRoundedRect(QRectF(8, 10, 48, 46), 6, 6)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#13191f"))
        painter.drawRoundedRect(QRectF(8, 10, 48, 12), 6, 6)
        painter.drawRect(QRectF(8, 18, 48, 4))
        painter.setBrush(QColor("#0a1110"))
        painter.drawRect(QRectF(10, 24, 44, 30))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#3f5b4a"))
        painter.drawEllipse(QRectF(17, 28, 30, 19))
        painter.drawRect(QRectF(17, 37, 30, 9))
        painter.setPen(QColor("#3f5b4a"))
        painter.drawLine(26, 32, 22, 27)
        painter.drawLine(38, 32, 42, 27)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#c2d8c9"))
        painter.drawEllipse(QRectF(23, 34, 6, 6))
        painter.drawEllipse(QRectF(35, 34, 6, 6))
    finally:
        painter.end()
    if size != 64:
        pixmap = pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return pixmap
