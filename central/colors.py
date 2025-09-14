"""
Tiny ANSI color helpers for CLI output.

Respects NO_COLOR to disable. Enables only when stdout is a TTY unless
FORCE_COLOR is set.
"""

from __future__ import annotations

import os
import sys


def _enabled() -> bool:
    if os.getenv("NO_COLOR") is not None:
        return False
    if os.getenv("FORCE_COLOR") is not None:
        return True
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


_ON = _enabled()


class _Codes:
    RESET = "\x1b[0m"
    BOLD = "\x1b[1m"
    DIM = "\x1b[2m"
    RED = "\x1b[31m"
    GREEN = "\x1b[32m"
    YELLOW = "\x1b[33m"
    BLUE = "\x1b[34m"
    MAGENTA = "\x1b[35m"
    CYAN = "\x1b[36m"


def color(text: str, *, fg: str | None = None, bold: bool = False) -> str:
    if not _ON or (fg is None and not bold):
        return text
    parts: list[str] = []
    if bold:
        parts.append(_Codes.BOLD)
    if fg:
        parts.append(getattr(_Codes, fg.upper(), ""))
    return "".join(parts) + text + _Codes.RESET

