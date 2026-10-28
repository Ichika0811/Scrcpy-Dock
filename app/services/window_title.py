"""Win32 window-title override for the native scrcpy window.

scrcpy 1.x appends ``(serial)`` to a custom ``--window-title``. To display
exactly ``ip:port deviceName`` we locate the SDL window owned by the scrcpy
process and set its caption directly.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


def set_scrcpy_window_title(pid: int, title: str) -> bool:
    if sys.platform != "win32" or not pid or not title:
        return False
    user32 = ctypes.windll.user32
    windows: list[tuple[int, str, str]] = []
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def collect(hwnd: int, _lparam: int) -> bool:
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != int(pid) or not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        text = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, text, length + 1)
        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name, 256)
        windows.append((int(hwnd), text.value, class_name.value))
        return True

    try:
        user32.EnumWindows(enum_proc(collect), 0)
    except Exception:
        return False

    # SDL2 top-level windows are usually class "SDL_app". Fall back to the
    # single visible top-level window if SDL uses a custom class.
    targets = [item for item in windows if item[2].lower().startswith("sdl")]
    if not targets:
        targets = [item for item in windows if item[1]]
    if not targets:
        return False

    changed = False
    for hwnd, _current, _class_name in targets:
        try:
            if user32.SetWindowTextW(hwnd, str(title)):
                changed = True
        except Exception:
            pass
    return changed
