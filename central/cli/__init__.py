"""Compatibility facade for the CLI now hosted in the top-level `noctics_cli` package."""

from __future__ import annotations

from noctics_cli import (
    CENTRAL_DEV_PASSPHRASE_ATTEMPT_ENV,
    RuntimeIdentity,
    main,
    parse_args,
    require_dev_passphrase,
    resolve_dev_passphrase,
    resolve_runtime_identity,
    validate_dev_passphrase,
)

__all__ = [
    "main",
    "parse_args",
    "RuntimeIdentity",
    "resolve_runtime_identity",
    "CENTRAL_DEV_PASSPHRASE_ATTEMPT_ENV",
    "require_dev_passphrase",
    "resolve_dev_passphrase",
    "validate_dev_passphrase",
]
