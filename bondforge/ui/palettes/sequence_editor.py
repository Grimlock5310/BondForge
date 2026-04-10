"""Sequence editor — dock widget for entering biopolymer sequences.

Provides a text input for entering peptide, DNA, or RNA sequences, a
type selector combo box, and an "Insert" button that places the
biopolymer on the canvas via an undo command.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bondforge.core.model.monomer import PolymerType


class SequenceEditor(QDockWidget):
    """Dock widget for typing biopolymer sequences and inserting them."""

    sequence_submitted = Signal(str, PolymerType)  # sequence, polymer_type

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Sequence Editor", parent)
        self.setAllowedAreas(
            # Allow docking on any side.
            __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.DockWidgetArea.AllDockWidgetAreas
        )

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)

        # Type selector row.
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Type:"))
        self._type_combo = QComboBox()
        self._type_combo.addItem("Peptide", PolymerType.PEPTIDE)
        self._type_combo.addItem("DNA", PolymerType.DNA)
        self._type_combo.addItem("RNA", PolymerType.RNA)
        type_row.addWidget(self._type_combo)
        layout.addLayout(type_row)

        # Sequence input.
        layout.addWidget(QLabel("Sequence:"))
        self._text_edit = QPlainTextEdit()
        self._text_edit.setPlaceholderText(
            "Enter sequence (e.g. ACDEFGHIKLMNPQRSTVWY for peptide, ACGT for DNA)"
        )
        self._text_edit.setMaximumHeight(100)
        layout.addWidget(self._text_edit)

        # Template buttons row.
        template_row = QHBoxLayout()
        igg_btn = QPushButton("IgG Template")
        igg_btn.setToolTip("Insert a pre-built IgG antibody template")
        igg_btn.clicked.connect(self._insert_igg_template)
        template_row.addWidget(igg_btn)
        template_row.addStretch()
        layout.addLayout(template_row)

        # Insert button.
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._insert_btn = QPushButton("Insert Sequence")
        self._insert_btn.clicked.connect(self._on_insert)
        btn_row.addWidget(self._insert_btn)
        layout.addLayout(btn_row)

        layout.addStretch()
        self.setWidget(container)

    def _on_insert(self) -> None:
        seq = self._text_edit.toPlainText().strip()
        if not seq:
            return
        # Remove whitespace and newlines from sequence.
        seq = "".join(seq.split())
        ptype = self._type_combo.currentData()
        self.sequence_submitted.emit(seq, ptype)

    def _insert_igg_template(self) -> None:
        """Emit a signal to insert the IgG template (handled by main window)."""
        self.sequence_submitted.emit("__IGG_TEMPLATE__", PolymerType.PEPTIDE)


__all__ = ["SequenceEditor"]
