"""QApplication subclass that wires up the BondForge desktop app."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from bondforge import __version__


class BondForgeApp(QApplication):
    """The top-level Qt application object for BondForge."""

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        QCoreApplication.setOrganizationName("BondForge")
        QCoreApplication.setOrganizationDomain("bondforge.org")
        QCoreApplication.setApplicationName("BondForge")
        QCoreApplication.setApplicationVersion(__version__)

        from bondforge.ui.main_window import MainWindow

        self._main_window = MainWindow()
        self._main_window.show()
