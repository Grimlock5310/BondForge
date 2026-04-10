"""BondForgeScene — the QGraphicsScene that owns all canvas items.

The scene is the bridge between the display :class:`Document` model and
the Qt graphics items. It listens for model edits and reconciles items
on demand. v0.1 takes the simplest possible approach: rebuild all items
from the model whenever it changes. We'll move to incremental updates
when the snapshot tests show it matters.

v0.3 generalizes the model the scene owns from a bare :class:`Molecule`
to a :class:`Document` (molecule + arrows), but keeps the ``molecule``
property so existing call sites continue to work.

The scene also supports lightweight "preview" items used by interactive
tools to show a ghost of what they're about to create (e.g. the bond
preview line drawn while the user is dragging the bond tool).
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Signal
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene

from bondforge.canvas.geometry import DEFAULT_BOND_LENGTH
from bondforge.canvas.items.arrow_item import ArrowItem
from bondforge.canvas.items.atom_item import AtomItem
from bondforge.canvas.items.biopolymer_item import BiopolymerItem
from bondforge.canvas.items.bond_item import BondItem
from bondforge.canvas.items.text_item import TextItem
from bondforge.core.model.document import Document
from bondforge.core.model.molecule import Molecule

__all__ = ["BondForgeScene", "DEFAULT_BOND_LENGTH"]


class BondForgeScene(QGraphicsScene):
    """A scene that renders a single :class:`Document`."""

    model_changed = Signal()

    def __init__(
        self,
        molecule: Molecule | None = None,
        parent=None,
        *,
        document: Document | None = None,
    ) -> None:
        super().__init__(parent)
        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)
        self.setSceneRect(QRectF(-2000, -2000, 4000, 4000))
        if document is not None:
            self._document = document
        else:
            self._document = Document(molecule=molecule or Molecule())
        self._atom_items: dict[int, AtomItem] = {}
        self._bond_items: dict[int, BondItem] = {}
        self._arrow_items: dict[int, ArrowItem] = {}
        self._text_items: dict[int, TextItem] = {}
        self._biopolymer_items: dict[int, BiopolymerItem] = {}
        self._preview_items: list[QGraphicsItem] = []
        self.rebuild()

    @property
    def molecule(self) -> Molecule:
        return self._document.molecule

    @property
    def document(self) -> Document:
        return self._document

    def set_molecule(self, molecule: Molecule) -> None:
        """Replace the underlying molecule and redraw."""
        self._document = Document(molecule=molecule)
        self.rebuild()

    def set_document(self, document: Document) -> None:
        """Replace the underlying document and redraw."""
        self._document = document
        self.rebuild()

    def rebuild(self) -> None:
        """Drop and recreate all items from the model."""
        self.clear_previews()
        stale: list[QGraphicsItem] = (
            list(self._atom_items.values())
            + list(self._bond_items.values())
            + list(self._arrow_items.values())
            + list(self._text_items.values())
            + list(self._biopolymer_items.values())
        )
        for item in stale:
            self.removeItem(item)
        self._atom_items.clear()
        self._bond_items.clear()
        self._arrow_items.clear()
        self._text_items.clear()
        self._biopolymer_items.clear()

        molecule = self._document.molecule
        for atom in molecule.iter_atoms():
            item = AtomItem(atom)
            self.addItem(item)
            self._atom_items[atom.id] = item

        for bond in molecule.iter_bonds():
            begin = self._atom_items[bond.begin_atom_id]
            end = self._atom_items[bond.end_atom_id]
            item = BondItem(bond, begin, end)
            self.addItem(item)
            self._bond_items[bond.id] = item

        for arrow in self._document.iter_arrows():
            item = ArrowItem(arrow)
            self.addItem(item)
            self._arrow_items[arrow.id] = item

        for text in self._document.iter_texts():
            item = TextItem(text)
            self.addItem(item)
            self._text_items[text.id] = item

        for bp in self._document.iter_biopolymers():
            item = BiopolymerItem(bp)
            self.addItem(item)
            self._biopolymer_items[bp.id] = item

        self.model_changed.emit()

    def atom_item(self, atom_id: int) -> AtomItem | None:
        return self._atom_items.get(atom_id)

    def bond_item(self, bond_id: int) -> BondItem | None:
        return self._bond_items.get(bond_id)

    def arrow_item(self, arrow_id: int) -> ArrowItem | None:
        return self._arrow_items.get(arrow_id)

    def text_item(self, text_id: int) -> TextItem | None:
        return self._text_items.get(text_id)

    def biopolymer_item(self, bp_id: int) -> BiopolymerItem | None:
        return self._biopolymer_items.get(bp_id)

    # ----- preview items ------------------------------------------------

    def add_preview_item(self, item: QGraphicsItem) -> QGraphicsItem:
        """Add an ephemeral item that lives outside the molecule model.

        Tools use this for drag previews. Cleared by :meth:`clear_previews`
        and on every :meth:`rebuild`.
        """
        item.setZValue(10.0)
        self.addItem(item)
        self._preview_items.append(item)
        return item

    def clear_previews(self) -> None:
        for item in self._preview_items:
            self.removeItem(item)
        self._preview_items.clear()
