"""Unit tests for pure parsing and command-line helpers."""

from __future__ import annotations

import unittest

from app.parsers import (
    build_scrcpy_args,
    evaluate_adb_connect,
    is_valid_host,
    is_valid_port,
    normalize_port_range,
    normalize_version,
    parse_adb_devices,
    parse_arg_string,
    parse_mdns_services,
    quote_arg,
    scrcpy_window_title,
    supports_window_title,
)


class ParserTests(unittest.TestCase):
    def test_version(self) -> None:
        self.assertEqual(
            normalize_version("scrcpy 3.1 <https://github.com/Genymobile/scrcpy>"),
            "3.1",
        )
        self.assertEqual(normalize_version("no version"), "未知版本")

    def test_args_quotes_and_windows_paths(self) -> None:
        self.assertEqual(
            parse_arg_string('--window-title="My Phone" --max-size=1280'),
            ["--window-title=My Phone", "--max-size=1280"],
        )
        self.assertEqual(
            parse_arg_string(r'--log="C:\Program Files\scrcpy log.txt"'),
            [r"--log=C:\Program Files\scrcpy log.txt"],
        )
        with self.assertRaises(ValueError):
            parse_arg_string('--window-title="oops')

    def test_build_args(self) -> None:
        args = build_scrcpy_args(
            "192.168.1.5:5555",
            window_title="Demo",
            extra_args="--max-fps=60",
        )
        self.assertEqual(args[0], "-s")
        self.assertIn("--window-title=Demo", args)
        self.assertIn("--max-fps=60", args)
        self.assertNotIn("--adb", " ".join(args))
        self.assertEqual(quote_arg("a b"), '"a b"')

    def test_hosts_and_ports(self) -> None:
        self.assertTrue(is_valid_host("192.168.1.5"))
        self.assertTrue(is_valid_host("phone.local"))
        self.assertFalse(is_valid_host("999.1.1.1"))
        self.assertFalse(is_valid_host("http://x"))
        self.assertTrue(is_valid_port(5555))
        self.assertFalse(is_valid_port(0))
        self.assertEqual(normalize_port_range(5555, 5585), (5555, 5585))
        self.assertEqual(normalize_port_range(1, 65535), (1, 65535))
        with self.assertRaises(ValueError):
            normalize_port_range(0, 100)

    def test_parse_devices(self) -> None:
        output = """List of devices attached
192.168.1.5:5555 device product:foo model:SM_G9910 device:o1 transport_id:1
192.168.1.6:5555 unauthorized product:foo model:Living_Room_TV device:o2
192.168.1.7:5555 offline
USB123 device product:bar model:Tablet device:o3
"""
        devices = parse_adb_devices(output)
        self.assertEqual(len(devices), 4)
        wireless = {device["serial"]: device for device in devices if device["wireless"]}
        self.assertEqual(wireless["192.168.1.5:5555"]["model"], "SM G9910")
        self.assertTrue(wireless["192.168.1.5:5555"]["online"])
        self.assertEqual(wireless["192.168.1.6:5555"]["status_label"], "未授权")
        self.assertEqual(wireless["192.168.1.7:5555"]["status"], "offline")

    def test_connect_evaluation(self) -> None:
        self.assertEqual(evaluate_adb_connect("connected to 1.2.3.4:5555")[0], True)
        self.assertEqual(evaluate_adb_connect("already connected to 1.2.3.4:5555")[0], True)
        self.assertEqual(
            evaluate_adb_connect("failed to connect to '1.2.3.4:5555': refused")[0],
            False,
        )

    def test_mdns(self) -> None:
        services = parse_mdns_services(
            "List of discovered mdns services\n"
            "adb-123 _adb-tls-connect._tcp. 192.168.1.5:37123\n"
            "adb-456 _adb-tls-pairing._tcp. 192.168.1.5:37124\n"
        )
        self.assertEqual(len(services), 2)
        self.assertFalse(services[0]["pairing"])
        self.assertTrue(services[1]["pairing"])

    def test_scrcpy_window_title(self) -> None:
        self.assertEqual(
            scrcpy_window_title("Pixel 7", "192.0.2.10:55007"),
            "192.0.2.10:55007 Pixel 7",
        )
        self.assertEqual(scrcpy_window_title("", "10.0.0.5:5555"), "10.0.0.5:5555")
        self.assertTrue(supports_window_title("1.19"))
        self.assertTrue(supports_window_title("1.24"))
        self.assertTrue(supports_window_title("3.3.4"))
        self.assertFalse(supports_window_title("1.18"))


if __name__ == "__main__":
    unittest.main()
