"""Minimal developer-mode stubs for the public core CLI."""

from __future__ import annotations

import os

NOX_DEV_PASSPHRASE_ATTEMPT_ENV = "NOX_DEV_PASSPHRASE_ATTEMPT"


def resolve_dev_passphrase() -> str:
    """Return the configured developer passphrase, if any."""

    return os.environ.get("NOX_DEV_PASSPHRASE", "")


def require_dev_passphrase(passphrase: str | None, *, interactive: bool = True) -> bool:
    """Basic passphrase check compatible with the lightweight CLI."""

    if not passphrase:
        return False
    attempted = os.environ.get(NOX_DEV_PASSPHRASE_ATTEMPT_ENV)
    if attempted is not None:
        return attempted == passphrase
    return True


def validate_dev_passphrase(passphrase: str) -> bool:
    return bool(passphrase)


def main() -> int:  # pragma: no cover - simple stub
    print("Developer CLI features are only available in the full Noctics multitool.")
    return 1


__all__ = [
    "NOX_DEV_PASSPHRASE_ATTEMPT_ENV",
    "main",
    "require_dev_passphrase",
    "resolve_dev_passphrase",
    "validate_dev_passphrase",
]
