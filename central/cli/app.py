"""Compatibility shim: central.cli.app moved to `noctics_cli.app`."""

from __future__ import annotations

from noctics_cli import app as _app
from noctics_cli.app import *  # noqa: F401,F403

# Legacy consumers expect this helper via the old module path.
_extract_visible_reply = _app._extract_visible_reply
