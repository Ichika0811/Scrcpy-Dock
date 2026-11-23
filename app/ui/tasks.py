"""Background task runner and progress relay for the main window."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QApplication, QWidget

from ..errors import AppError
from .dialogs import BusyDialog


class _TaskSignals(QObject):
    result = Signal(int, object)
    failed = Signal(int, object)
    finished = Signal(int)
    progress = Signal(int, int, int)


class TaskRunner(QObject):
    """Run Python jobs off the UI thread and relay results through Qt signals."""

    def __init__(
        self,
        busy_parent: QWidget,
        on_error: Callable[[Exception, str], None],
        on_cancelled: Callable[[str], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._busy_parent = busy_parent
        self._on_error = on_error
        self._on_cancelled = on_cancelled
        self._seq = 0
        self._tasks: dict[int, dict[str, Any]] = {}
        self.signals = _TaskSignals(self)
        self.signals.result.connect(self._on_result)
        self.signals.failed.connect(self._on_failure)
        self.signals.finished.connect(self._on_finished)
        self.signals.progress.connect(self._on_progress)

    def start(
        self,
        function: Callable[..., Any],
        success: Callable[[Any], None],
        failure: Callable[[Exception], None] | None = None,
        *,
        busy_text: str | None = None,
        progress: bool = False,
        cancel_event: threading.Event | None = None,
    ) -> int:
        self._seq += 1
        task_id = self._seq
        busy = (
            BusyDialog(busy_text, self._busy_parent, cancelable=bool(cancel_event))
            if busy_text
            else None
        )
        if busy:
            if cancel_event is not None:
                busy.cancel_requested.connect(cancel_event.set)
                busy.cancel_requested.connect(
                    lambda: busy.set_status("正在取消，请稍候…")
                )
            busy.show()
            busy.raise_()
            QApplication.processEvents()
        thread = threading.Thread(
            target=self._run,
            args=(task_id, function, progress),
            name=f"ScrcpyDockTask-{task_id}",
            daemon=True,
        )
        self._tasks[task_id] = {
            "thread": thread,
            "success": success,
            "failure": failure,
            "busy": busy,
            "finished": False,
        }
        thread.start()
        return task_id

    def _run(
        self,
        task_id: int,
        function: Callable[..., Any],
        progress: bool,
    ) -> None:
        try:
            if progress:
                value = function(
                    lambda written, total: self.signals.progress.emit(
                        task_id, int(written), int(total)
                    )
                )
            else:
                value = function()
        except Exception as exc:  # noqa: BLE001 - delivered to the UI
            self.signals.failed.emit(task_id, exc)
        else:
            self.signals.result.emit(task_id, value)
        finally:
            self.signals.finished.emit(task_id)

    @Slot(int, object)
    def _on_result(self, task_id: int, value: Any) -> None:
        task = self._tasks.get(task_id)
        if not task or task.get("finished"):
            return
        task["finished"] = True
        self._close_busy(task)
        try:
            task["success"](value)
        except Exception as exc:  # noqa: BLE001
            self._on_error(exc, "处理结果失败")

    @Slot(int, object)
    def _on_failure(self, task_id: int, error: Exception) -> None:
        task = self._tasks.get(task_id)
        if not task or task.get("finished"):
            return
        task["finished"] = True
        self._close_busy(task)
        if isinstance(error, AppError) and error.code == "DOWNLOAD_CANCELLED":
            self._on_cancelled("下载已取消，未安装任何文件。")
            return
        callback = task.get("failure")
        if callback:
            try:
                callback(error)
            except Exception as exc:  # noqa: BLE001
                self._on_error(exc, "任务失败")
        else:
            self._on_error(error, "操作失败")

    @Slot(int, int, int)
    def _on_progress(self, task_id: int, written: int, total: int) -> None:
        task = self._tasks.get(task_id)
        if not task or task.get("finished"):
            return
        busy = task.get("busy")
        if busy:
            busy.set_progress(written, total)

    @Slot(int)
    def _on_finished(self, task_id: int) -> None:
        task = self._tasks.pop(task_id, None)
        if task:
            self._close_busy(task)

    @staticmethod
    def _close_busy(task: dict[str, Any]) -> None:
        busy = task.get("busy")
        if busy:
            try:
                busy.close()
            except RuntimeError:
                pass

    def wait(self, timeout: float = 6.0) -> None:
        deadline = time.monotonic() + timeout
        for task in list(self._tasks.values()):
            thread = task.get("thread")
            if not thread:
                continue
            remaining = max(0.0, deadline - time.monotonic())
            if remaining <= 0:
                break
            thread.join(remaining)
