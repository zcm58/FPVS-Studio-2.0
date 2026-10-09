"""Forward Qt's own warnings and fatal messages to application diagnostics."""

from __future__ import annotations

import logging
import os
from typing import Any

from PySide6.QtCore import QtMsgType, qInstallMessageHandler, qVersion

from fpvs_studio.support.diagnostics import bounded_text, record_qt_fatal, redact

_LOGGER = logging.getLogger(__name__)
_installed = False
_previous_handler: Any = None


def _qt_message(kind: QtMsgType, context: Any, message: str) -> None:
    level = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }.get(kind, logging.WARNING)
    _LOGGER.log(level, "Qt: %s", bounded_text(message, 8192))
    if kind == QtMsgType.QtFatalMsg:
        record_qt_fatal(message)
        # Qt aborts immediately after this callback: the asynchronous log queue may
        # never drain. Preserve a small redacted breadcrumb on console launches too.
        try:
            text = "Qt fatal: " + redact(bounded_text(message, 8192)) + "\n"
            os.write(2, text.encode("utf-8", errors="replace"))
        except OSError:
            pass  # Windowed frozen executables may have no stderr handle.
    if _previous_handler is not None:
        _previous_handler(kind, context, message)


def install_qt_diagnostics() -> None:
    """Install once, before QApplication construction can issue startup warnings."""

    global _installed, _previous_handler
    if not _installed:
        _previous_handler = qInstallMessageHandler(_qt_message)
        _installed = True
        _LOGGER.info("Qt diagnostics installed (Qt %s)", qVersion())
