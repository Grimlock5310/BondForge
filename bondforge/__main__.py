"""Entry point for ``python -m bondforge`` and the ``bondforge`` console script."""

from __future__ import annotations

import sys


def main() -> int:
    """Launch the BondForge desktop application."""
    from bondforge.app import BondForgeApp

    app = BondForgeApp(sys.argv)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
