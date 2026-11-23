"""Device-disconnect log detection."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.config import ConfigStore
from app.services.adb import AdbService
from app.services.terminals import TerminalManager, is_device_disconnect_message


class DeviceDisconnectMessageTests(unittest.TestCase):
    def test_keep_alive_failure_is_disconnect(self) -> None:
        self.assertTrue(
            is_device_disconnect_message("! ERROR: Could not send keep alive to socket")
        )

    def test_device_disconnected_is_disconnect(self) -> None:
        self.assertTrue(is_device_disconnect_message("! WARN: Device disconnected"))

    def test_adb_offline_is_disconnect(self) -> None:
        self.assertTrue(is_device_disconnect_message("adb: device offline"))

    def test_normal_scrcpy_output_is_not_disconnect(self) -> None:
        output = "INFO: Renderer: opengl\nINFO: Texture: 1080x2400\nINFO: Device: Pixel 7"
        self.assertFalse(is_device_disconnect_message(output))

    def test_adb_poll_marks_running_terminal_disconnected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = ConfigStore(Path(temp))
            manager = TerminalManager(config, AdbService(config))
            terminal_id = manager.create(None)
            session = manager.require(terminal_id)
            session.status = "running"
            session.target = {"host": "192.0.2.10", "port": 5555, "network_id": None}
            self.assertTrue(manager.is_active_id(terminal_id))
            self.assertTrue(manager.mark_device_missing(terminal_id, "ADB 设备列表中未找到"))
            self.assertEqual(session.status, "disconnected")
            self.assertFalse(manager.is_active_id(terminal_id))
            manager.dismiss(terminal_id)


if __name__ == "__main__":
    unittest.main()
