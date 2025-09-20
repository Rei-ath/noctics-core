from __future__ import annotations

from central.core import _extract_public_segments, strip_chain_of_thought


def test_strip_chain_of_thought_removes_block() -> None:
    text = "<think>internal</think> Visible answer."
    assert strip_chain_of_thought(text) == "Visible answer."


def test_strip_chain_of_thought_empty_when_only_think() -> None:
    assert strip_chain_of_thought("<think>internal</think>") == ""


def test_extract_public_segments_handles_partial_open() -> None:
    public, remainder = _extract_public_segments("Hello <think>secret")
    assert public == "Hello "
    assert remainder == "<think>secret"


def test_extract_public_segments_multiple_blocks() -> None:
    buf = "A<think>x</think>B<think>y</think>C"
    public, remainder = _extract_public_segments(buf)
    assert public == "ABC"
    assert remainder == ""
