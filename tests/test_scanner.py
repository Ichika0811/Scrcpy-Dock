"""Local TCP port scanner tests."""

from __future__ import annotations

import socket
import threading
import unittest

from app.services.scanner import probe_adb, scan_ports


class ScannerTests(unittest.TestCase):
    def test_finds_open_ports(self) -> None:
        servers = []
        try:
            for port in (15555, 15557):
                server = socket.socket()
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind(("127.0.0.1", port))
                server.listen(4)
                servers.append(server)
                threading.Thread(
                    target=self._accept_loop,
                    args=(server,),
                    daemon=True,
                ).start()
            result = scan_ports(
                "127.0.0.1",
                start=15555,
                end=15558,
                timeout_ms=180,
                extra_ports=[],
                concurrency=8,
            )
            self.assertEqual(result["open"], [15555, 15557])
            self.assertEqual(result["scanned"], 4)
        finally:
            for server in servers:
                server.close()

    @staticmethod
    def _accept_loop(server: socket.socket) -> None:
        for _ in range(8):
            try:
                client, _address = server.accept()
                client.close()
            except OSError:
                return

    def test_invalid_host(self) -> None:
        with self.assertRaises(Exception):
            scan_ports("not a host", 5555, 5555)

    def test_adb_handshake_detection(self) -> None:
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        def serve() -> None:
            client, _ = server.accept()
            try:
                client.recv(64)
                client.sendall(b"CNXN" + b"\x00" * 20)
            finally:
                client.close()
                server.close()

        threading.Thread(target=serve, daemon=True).start()
        self.assertTrue(probe_adb("127.0.0.1", port, timeout=1.0))

    def test_adb_handshake_rejects_generic_service(self) -> None:
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        def serve() -> None:
            client, _ = server.accept()
            try:
                client.recv(64)
                client.sendall(b"HTTP")
            finally:
                client.close()
                server.close()

        threading.Thread(target=serve, daemon=True).start()
        self.assertFalse(probe_adb("127.0.0.1", port, timeout=1.0))


if __name__ == "__main__":
    unittest.main()
