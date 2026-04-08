"""BondForgeScene — the QGraphicsScene that owns all canvas items.

The scene is the bridge between the display :class:`Molecule` model and
the Qt graphics items. It listens for model edits and reconciles items
on demand. v0.1 takes the simplest possible approach: rebuild all items
from the model whenever it changes. We'll move to incremental updates
when the snapshot tests show it matters.

The scene also supports lightweight "preview" items used by interactive
tools to show a ghost of what they're about to create (e.g. the bond
preview line drawn while the user is dragging the bond tool).
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Signal
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene

from bondforge.canvas.geometry import DEFAULT_BOND_LENGTH
from bondforge.canvas.items.atom_item import AtomItem
from bondforge.canvas.items.bond_item import BondItem
from bondforge.core.model.molecule import Molecule

__all__ = ["BondForgeScene", "DEFAULT_BOND_LENGTH"]


class BondForgeScene(QGraphicsScene):
    """A scene that renders a single :class:`Molecule`."""

    model_changed = Signal()

    def __init__(self, molecule: Molecule | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)
        self.setSceneRect(QRectF(-2000, -2000, 4000, 4000))
        self._molecule = molecule or Molecule()
        self._atom_items: dict[int, AtomItem] = {}
        self._bond_items: dict[int, BondItem] = {}
        self._preview_items: list[QGraphicsItem] = []
        self.rebuild()

    @property
    def molecule(self) -> Molecule:
        return self._molecule

    def set_molecule(self, molecule: Molecule) -> None:
        """Replace the underlying molecule and redraw."""
        self._molecule = molecule
        self.rebuild()

    def rebuild(self) -> None:
        """Drop and recreate all atom and bond items from the model."""
        self.clear_previews()
        for item in list(self._atom_items.values()) + list(self._bond_items.values()):
            self.removeItem(item)
        self._atom_items.clear()
        self._bond_items.clear()

        for atom in self._molecule.iter_atoms():
            item = AtomItem(atom)
            self.addItem(item)
            self._atom_items[atom.id] = item

        for bond in self._molecule.iter_bonds():
            begin = self._atom_items[bond.begin_atom_id]
            end = self._atom_items[bond.end_atom_id]
            item = BondItem(bond, begin, end)
            self.addItem(item)
            self._bond_items[bond.id] = item

        self.model_changed.emit()

    def atom_item(self, atom_id: int) -> AtomItem | None:
        return self._atom_items.get(atom_id)

    def bond_item(self, bond_id: int) -> BondItem | None:
        return self._bond_items.get(bond_id)

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
