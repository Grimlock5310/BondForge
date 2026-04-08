"""BondForgeScene — the QGraphicsScene that owns all canvas items.

The scene is the bridge between the display :class:`Molecule` model and
the Qt graphics items. It listens for model edits and reconciles items
on demand. v0.1 takes the simplest possible approach: rebuild all items
from the model whenever it changes. We'll move to incremental updates
when the snapshot tests show it matters.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Signal
from PySide6.QtWidgets import QGraphicsScene

from bondforge.canvas.items.atom_item import AtomItem
from bondforge.canvas.items.bond_item import BondItem
from bondforge.core.model.molecule import Molecule

# Default bond length in scene units. Chosen to give a comfortable
# default font size for atom labels at zoom=1.
DEFAULT_BOND_LENGTH = 50.0


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
