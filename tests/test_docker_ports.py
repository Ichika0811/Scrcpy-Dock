"""Docker published-port parsing tests."""

from __future__ import annotations

import unittest

from app.services.docker_ports import parse_docker_ps


class DockerPortTests(unittest.TestCase):
    def test_parses_redroid_adb_mappings(self) -> None:
        output = (
            "redroid-1\tredroid/redroid:13\t0.0.0.0:55007->5555/tcp, [::]:55007->5555/tcp, 0.0.0.0:9067->9067/tcp\n"
            "phone-2\tandroid:test\t127.0.0.1:55008->5555/tcp\n"
            "webserver\tnginx\t0.0.0.0:8080->80/tcp\n"
        )
        ports = parse_docker_ps(output)
        self.assertEqual([entry["port"] for entry in ports], [55007, 55008])
        self.assertEqual(ports[0]["container"], "redroid-1")
        self.assertEqual(ports[1]["container"], "phone-2")

    def test_deduplicates_ipv4_and_ipv6_mapping(self) -> None:
        output = "redroid\timg\t0.0.0.0:5555->5555/tcp, :::5555->5555/tcp\n"
        ports = parse_docker_ps(output)
        self.assertEqual(len(ports), 1)
        self.assertEqual(ports[0]["port"], 5555)

    def test_ignores_non_adb_container_ports(self) -> None:
        output = "web\tnginx\t0.0.0.0:8080->80/tcp\n"
        self.assertEqual(parse_docker_ps(output), [])


if __name__ == "__main__":
    unittest.main()
