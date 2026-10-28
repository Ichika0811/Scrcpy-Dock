"""Scrcpy Dock entry point."""

from __future__ import annotations

import ctypes
import logging
import sys
import traceback

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from app import __version__
from app.config import ConfigStore
from app.ui.main_window import MainWindow
from app.ui.resources import app_icon
from app.ui.theme import APP_QSS

INSTANCE_NAME = f"ScrcpyDock.Instance.{__version__}"


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.scrcpydock.app")
    except Exception:
        pass


def _configure_logging(config: ConfigStore) -> None:
    log_path = config.logs_dir / "app.log"
    handlers: list[logging.Handler] = [logging.FileHandler(log_path, encoding="utf-8")]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def _already_running() -> bool:
    socket = QLocalSocket()
    socket.connectToServer(INSTANCE_NAME)
    if socket.waitForConnected(220):
        socket.write(b"show")
        socket.flush()
        socket.waitForBytesWritten(220)
        socket.disconnectFromServer()
        return True
    return False


def main() -> int:
    _set_windows_app_id()
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Scrcpy Dock")
    app.setApplicationDisplayName("Scrcpy Dock")
    app.setOrganizationName("ScrcpyDock")
    app.setQuitOnLastWindowClosed(True)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI Variable Text", 9))
    app.setStyleSheet(APP_QSS)

    if _already_running():
        return 0

    config = ConfigStore()
    _configure_logging(config)
    app.setWindowIcon(app_icon())

    window = MainWindow(config)
    window.show()

    server = QLocalServer(window)
    QLocalServer.removeServer(INSTANCE_NAME)
    server.listen(INSTANCE_NAME)

    def bring_forward() -> None:
        socket = server.nextPendingConnection()
        if socket:
            socket.deleteLater()
        if window.isMinimized():
            window.showNormal()
        window.show()
        window.raise_()
        window.activateWindow()

    server.newConnection.connect(bring_forward)

    def exception_hook(exc_type, exc_value, exc_tb) -> None:
        logging.error("Unhandled exception:\n%s", "".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
        QMessageBox.critical(
            window,
            "Scrcpy Dock",
            f"程序遇到未处理的错误：\n\n{exc_value}\n\n详情已写入日志。",
        )

    sys.excepthook = exception_hook
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
