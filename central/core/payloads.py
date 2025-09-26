"""Payload helpers shared by the chat client."""

from __future__ import annotations

from typing import Any, Dict, List

__all__ = ["build_payload"]


def build_payload(
    *,
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float,
    max_tokens: int,
    stream: bool,
) -> Dict[str, Any]:
    """Return a JSON-serialisable payload for the chat completions endpoint."""

    return {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }

