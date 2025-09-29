"""
Project entrypoint: calls the Central CLI.
"""

from __future__ import annotations

import sys

from central.cli import main as central_main


if __name__ == "__main__":
    raise SystemExit(central_main(sys.argv[1:]))

