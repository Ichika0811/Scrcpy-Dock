"""Application-level exceptions with user-facing messages."""

from __future__ import annotations


class AppError(Exception):
    """An expected error that can be shown directly to the user."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "APP_ERROR",
        hint: str = "",
        detail: str = "",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.hint = hint
        self.detail = detail

    def user_text(self) -> str:
        return "\n".join(part for part in (self.message, self.hint) if part)
