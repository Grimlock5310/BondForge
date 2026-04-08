"""Shared pytest configuration.

Some tests import Qt classes (``QObject``, ``QGraphicsScene``) that
require a live ``QApplication`` even when no window is ever shown. We
create one in offscreen mode so headless CI and local test runs both
work without an X server.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def _qapp():
    """Ensure a single ``QApplication`` exists for the whole test session."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        yield None
        return
    app = QApplication.instance() or QApplication([])
    yield app
