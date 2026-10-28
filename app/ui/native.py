"""Small Windows-native window helpers."""

from __future__ import annotations

import ctypes
import sys


def apply_dark_titlebar(widget) -> None:
    """Ask DWM to render the native title bar in dark mode when possible."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
        enabled = ctypes.c_int(1)
        for attribute in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)
            )
        # COLORREF is 0x00BBGGRR. A very dark navy border blends with the UI.
        border = ctypes.c_uint(0x00140D08)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 34, ctypes.byref(border), ctypes.sizeof(border)
        )
    except Exception:
        pass
