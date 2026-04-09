"""Name → Structure dialog backed by OPSIN.

The dialog takes a chemical name (IUPAC, common, or trivial), hands it
to :func:`bondforge.engine.naming.name_to_molecule`, and exposes the
resulting molecule via :meth:`NameToStructureDialog.result_molecule`
for the caller to paste onto the canvas.

If OPSIN is not available at import time we still let the dialog open,
so the user gets a friendly "install the opsin extra" message instead
of a hard crash on menu click.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from bondforge.core.model.molecule import Molecule
from bondforge.engine.naming import (
    OpsinError,
    OpsinUnavailable,
    is_opsin_available,
    name_to_molecule,
)


class NameToStructureDialog(QDialog):
    """Modal dialog that prompts for a chemical name and converts it."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Name → Structure")
        self._molecule: Molecule | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Enter a chemical name (IUPAC, common, or trivial):",
                self,
            )
        )
        self._name_edit = QLineEdit(self)
        self._name_edit.setPlaceholderText("e.g. 2-methylpropan-1-ol, caffeine, benzene")
        layout.addWidget(self._name_edit)

        status = (
            "OPSIN backend ready."
            if is_opsin_available()
            else ("OPSIN backend not installed. Install the 'opsin' extra to enable.")
        )
        self._status = QLabel(status, self)
        self._status.setStyleSheet("color: #666;")
        layout.addWidget(self._status)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._name_edit.returnPressed.connect(self._on_accept)

    def result_molecule(self) -> Molecule | None:
        """Return the molecule the user converted, or ``None`` if cancelled."""
        return self._molecule

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            return
        try:
            self._molecule = name_to_molecule(name)
        except OpsinUnavailable as exc:
            QMessageBox.information(self, "OPSIN unavailable", str(exc))
            return
        except OpsinError as exc:
            QMessageBox.warning(self, "Could not parse name", str(exc))
            return
        self.accept()
