from __future__ import annotations

import os

from central.commands.helper import extract_helper_query, anonymize_for_helper


def test_extract_helper_query_basic():
    text = (
        "Some intro...\n"
        "[HELPER QUERY]\n"
        "Please summarize the following input from the user: foo bar.\n"
        "[/HELPER QUERY]\n"
        "Other text"
    )
    q = extract_helper_query(text)
    assert q is not None
    assert q.startswith("Please summarize")


def test_anonymize_for_helper_redacts_pii_and_names(monkeypatch):
    monkeypatch.setenv("CENTRAL_REDACT_NAMES", "Alice")
    src = (
        "From: Alice <alice@example.com>\n"
        "Call me at +1-415-555-1212, IP 192.168.0.1.\n"
        "Card: 4111 1111 1111 1111\n"
    )
    out = anonymize_for_helper(src, user_name="Jang")
    assert "[REDACTED:EMAIL]" in out
    assert "[REDACTED:PHONE]" in out
    assert "[REDACTED:IP]" in out
    # Luhn-like card redaction
    assert "[REDACTED:CARD]" in out
    # Alice should be redacted by env
    assert "Alice" not in out

