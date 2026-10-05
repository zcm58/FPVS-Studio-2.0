"""Safe data-sharing failures, without server bodies or credentials."""

from __future__ import annotations


class DataSharingError(RuntimeError):
    def __init__(self, message: str, *, code: str = "unavailable", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class DataSharingCancelled(DataSharingError):
    def __init__(self) -> None:
        super().__init__("Data sharing was canceled.", code="cancelled")
