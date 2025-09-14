"""Compatibility shim for the moved CLI.

The CLI now lives under the `central` package. This wrapper forwards
execution to `central.cli.main` to keep existing workflows working.
"""

from __future__ import annotations

import sys

from central.cli import main as central_main


if __name__ == "__main__":
    raise SystemExit(central_main(sys.argv[1:]))

