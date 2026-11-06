"""Device-disconnect log detection."""

from __future__ import annotations

import unittest

from app.services.terminals import is_device_disconnect_message


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


if __name__ == "__main__":
    unittest.main()
