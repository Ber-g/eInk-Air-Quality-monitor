#!/usr/bin/env python3
from __future__ import annotations
"""
Circular log buffer — thread-safe, no dependencies.
Keeps the last 200 lines in memory for the debug menu,
and optionally mirrors to a rotating file on disk.
"""
import time
import logging
import logging.handlers
import os
from collections import deque

_RING: deque[str] = deque(maxlen=200)
_LOG_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "app.log")

_file_handler: logging.handlers.RotatingFileHandler | None = None


def init_file_log() -> None:
    """Set up rotating file log (256 KB × 3 = ~768 KB max on SD card)."""
    global _file_handler
    os.makedirs(_LOG_DIR, exist_ok=True)
    _file_handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE, maxBytes=256 * 1024, backupCount=3, encoding="utf-8"
    )
    _file_handler.setFormatter(logging.Formatter("%(message)s"))


def _write(level: str, msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {level} {msg}"
    _RING.append(line)
    if _file_handler:
        record = logging.LogRecord("", logging.INFO, "", 0, line, (), None)
        _file_handler.emit(record)
    print(line)


def info(msg: str)    -> None: _write("INFO", msg)
def warning(msg: str) -> None: _write("WARN", msg)
def error(msg: str)   -> None: _write("ERR ", msg)


def tail(n: int = 10) -> list[str]:
    return list(_RING)[-n:]
