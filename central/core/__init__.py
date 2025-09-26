"""Public interface for the Central chat client package."""

from __future__ import annotations

from .client import ChatClient, DEFAULT_URL
from .helper_prompt import load_helper_prompt
from .payloads import build_payload
from .reasoning import extract_public_segments, strip_chain_of_thought

# Backwards compat: tests import the private helper with a leading underscore.
_extract_public_segments = extract_public_segments
_load_helper_prompt = load_helper_prompt

__all__ = [
    "ChatClient",
    "DEFAULT_URL",
    "build_payload",
    "load_helper_prompt",
    "extract_public_segments",
    "strip_chain_of_thought",
    "_extract_public_segments",
    "_load_helper_prompt",
]
