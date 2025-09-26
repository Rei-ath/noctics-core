"""Reasoning sanitisation helpers for Central."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

__all__ = ["strip_chain_of_thought", "extract_public_segments"]

_THINK_PATTERN = re.compile(r"<think>.*?</think>\s*", re.IGNORECASE | re.DOTALL)


def strip_chain_of_thought(text: Optional[str]) -> Optional[str]:
    """Remove ``<think>...</think>`` segments while preserving public content."""

    if text is None:
        return None
    cleaned = _THINK_PATTERN.sub("", text)
    return cleaned.strip()


def extract_public_segments(buffer: str) -> Tuple[str, str]:
    """Return ``(public_text, remainder)`` preserving incomplete think blocks."""

    lower = buffer.lower()
    pos = 0
    public_parts: List[str] = []
    length = len(buffer)
    open_tag = "<think>"
    close_tag = "</think>"
    open_len = len(open_tag)
    close_len = len(close_tag)

    while pos < length:
        open_idx = lower.find(open_tag, pos)
        if open_idx == -1:
            public_parts.append(buffer[pos:])
            return "".join(public_parts), ""
        public_parts.append(buffer[pos:open_idx])
        close_search_start = open_idx + open_len
        close_idx = lower.find(close_tag, close_search_start)
        if close_idx == -1:
            return "".join(public_parts), buffer[open_idx:]
        pos = close_idx + close_len

    return "".join(public_parts), ""

