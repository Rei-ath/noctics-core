"""Compatibility shim keeping legacy helper APIs available."""

from __future__ import annotations

from .instrument import (
    anonymize_for_instrument,
    choose_instrument_interactively,
    describe_instrument_status,
    extract_instrument_query,
    get_instrument_candidates,
    instrument_automation_enabled,
    print_sanitized_instrument_query,
)

extract_helper_query = extract_instrument_query
anonymize_for_helper = anonymize_for_instrument
print_sanitized_helper_query = print_sanitized_instrument_query
get_helper_candidates = get_instrument_candidates
helper_automation_enabled = instrument_automation_enabled
describe_helper_status = describe_instrument_status
choose_helper_interactively = choose_instrument_interactively

__all__ = [
    "extract_helper_query",
    "anonymize_for_helper",
    "print_sanitized_helper_query",
    "get_helper_candidates",
    "helper_automation_enabled",
    "describe_helper_status",
    "choose_helper_interactively",
]
