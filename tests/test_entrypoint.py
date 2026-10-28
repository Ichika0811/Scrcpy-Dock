"""Entry-point import smoke tests."""

from __future__ import annotations

import unittest


class EntrypointTests(unittest.TestCase):
    def test_run_module_imports(self) -> None:
        import run

        self.assertTrue(callable(run.main))

    def test_qt_network_single_instance_types(self) -> None:
        from PySide6.QtNetwork import QLocalServer, QLocalSocket

        self.assertTrue(QLocalServer)
        self.assertTrue(QLocalSocket)


if __name__ == "__main__":
    unittest.main()
