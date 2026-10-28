"""Configuration persistence tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.config import ConfigStore, TOOL_COLORS


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.store = ConfigStore(self.data_dir)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_add_tools_and_versions(self) -> None:
        tool = self.store.add_tool(
            {
                "folder": r"C:\scrcpy",
                "scrcpy_path": r"C:\scrcpy\scrcpy.exe",
                "adb_path": r"C:\scrcpy\adb.exe",
                "detected_version": "3.1",
            }
        )
        self.assertEqual(tool["version"], "3.1")
        self.assertTrue(tool["version_auto"])
        self.store.update_tool(tool["id"], {"version": "3.1-mod"})
        updated = self.store.get_tool(tool["id"])
        self.assertEqual(updated["version"], "3.1-mod")
        self.assertFalse(updated["version_auto"])
        self.store.update_tool(tool["id"], {"version_auto": True})
        self.assertEqual(self.store.get_tool(tool["id"])["version"], "3.1")
        self.store.update_tool(tool["id"], {"favorite": True})
        self.assertTrue(self.store.get_tool(tool["id"])["favorite"])
        self.assertIn(tool["color"], TOOL_COLORS)
        self.store.update_tool(tool["id"], {"color": "#123456"})
        self.assertEqual(self.store.get_tool(tool["id"])["color"], "#123456")
        with self.assertRaises(Exception):
            self.store.update_tool(tool["id"], {"color": "not-a-color"})

    def test_tool_duplicate(self) -> None:
        payload = {
            "folder": r"C:\scrcpy",
            "scrcpy_path": r"C:\scrcpy\scrcpy.exe",
            "detected_version": "3.1",
        }
        self.store.add_tool(payload)
        with self.assertRaises(Exception):
            self.store.add_tool(payload)

    def test_networks_ports_and_persistence(self) -> None:
        network = self.store.add_network("192.168.1.5", label="Phone", port=5555)
        self.store.add_network_port(network["id"], 5556, source="scan")
        self.store.record_port_attempt(
            network["id"], 5555, success=True, device_name="SM G9910", message="connected"
        )
        reloaded = ConfigStore(self.data_dir)
        saved = reloaded.find_network_by_ip("192.168.1.5")
        self.assertIsNotNone(saved)
        self.assertEqual(saved["label"], "Phone")
        self.assertEqual(len(saved["ports"]), 2)
        port = next(item for item in saved["ports"] if item["port"] == 5555)
        self.assertEqual(port["device_name"], "SM G9910")
        self.assertEqual(port["last_status"], "success")

    def test_apply_device_names(self) -> None:
        network = self.store.add_network("192.168.1.8", label="TV", port=5555)
        changed = self.store.apply_device_names(
            [
                {
                    "serial": "192.168.1.8:5555",
                    "wireless": True,
                    "model": "Living Room TV",
                },
                {
                    "serial": "192.168.1.9:5555",
                    "wireless": True,
                    "model": "Other",
                },
            ]
        )
        self.assertTrue(changed)
        saved = self.store.get_network(network["id"])
        self.assertEqual(saved["ports"][0]["device_name"], "Living Room TV")
        self.assertIsNone(self.store.find_network_by_ip("192.168.1.9"))

    def test_auto_import_connected_wireless_device(self) -> None:
        changed = self.store.apply_device_names(
            [
                {
                    "serial": "192.0.2.10:55007",
                    "wireless": True,
                    "online": True,
                    "model": "Pixel 7",
                }
            ],
            auto_import=True,
        )
        self.assertTrue(changed)
        network = self.store.find_network_by_ip("192.0.2.10")
        self.assertIsNotNone(network)
        self.assertEqual(network["ports"][0]["port"], 55007)
        self.assertEqual(network["ports"][0]["device_name"], "Pixel 7")
        self.assertEqual(network["ports"][0]["source"], "device")

    def test_settings_and_corrupt_recovery(self) -> None:
        settings = self.store.update_settings(
            {"scan_start": 5600, "scan_end": 5700, "auto_scan": False}
        )
        self.assertEqual(settings["scan_start"], 5600)
        self.assertFalse(settings["auto_scan"])
        self.store.config_path.write_text("{not json", encoding="utf-8")
        recovered = ConfigStore(self.data_dir)
        self.assertEqual(recovered.settings["scan_start"], 5555)
        self.assertTrue(list(self.data_dir.glob("config.corrupt-*.json")))

    def test_snapshot_roundtrip(self) -> None:
        self.store.add_tool(
            {
                "folder": r"C:\scrcpy",
                "scrcpy_path": r"C:\scrcpy\scrcpy.exe",
                "detected_version": "2.4",
            }
        )
        self.store.add_network("10.0.0.2")
        raw = json.loads(json.dumps(self.store.snapshot()))
        self.assertEqual(raw["tools"][0]["detected_version"], "2.4")
        self.assertEqual(raw["networks"][0]["ip"], "10.0.0.2")


if __name__ == "__main__":
    unittest.main()
