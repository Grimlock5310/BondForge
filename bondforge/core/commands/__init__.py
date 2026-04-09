"""QUndoCommand subclasses that mutate a :class:`Molecule` via the scene.

Every interactive edit goes through one of these commands so that the
``QUndoStack`` owned by the document can step backward and forward
through the user's actions.
"""

from __future__ import annotations

from PySide6.QtGui import QUndoCommand

from bondforge.canvas.scene import BondForgeScene
from bondforge.core.model.bond import BondOrder, BondStereo


class AddAtomCommand(QUndoCommand):
    """Add a single atom to the scene's molecule.

    The original atom ID is preserved across redo-after-undo cycles so
    that any downstream commands (e.g. :class:`AddBondCommand`) that
    reference it still resolve after the stack walks back and forth.
    """

    def __init__(self, scene: BondForgeScene, element: str, x: float, y: float) -> None:
        super().__init__(f"Add {element}")
        self._scene = scene
        self._element = element
        self._x = x
        self._y = y
        self.created_atom_id: int = -1

    def redo(self) -> None:
        mol = self._scene.molecule
        atom = mol.add_atom(self._element, self._x, self._y)
        if self.created_atom_id == -1:
            self.created_atom_id = atom.id
        elif atom.id != self.created_atom_id:
            # Second-or-later redo: the molecule's ID counter has moved on
            # since the first run, so ``add_atom`` handed us a fresh ID.
            # Re-key the atom under its original ID so sibling commands
            # (which cached the original) remain valid.
            mol.atoms.pop(atom.id)
            atom.id = self.created_atom_id
            mol.atoms[self.created_atom_id] = atom
            mol._next_atom_id = max(mol._next_atom_id, self.created_atom_id + 1)
        self._scene.rebuild()

    def undo(self) -> None:
        if self.created_atom_id != -1:
            self._scene.molecule.remove_atom(self.created_atom_id)
            self._scene.rebuild()


class AddBondCommand(QUndoCommand):
    """Add a single bond between two existing atoms.

    Like :class:`AddAtomCommand`, the bond's ID is preserved across
    redo-after-undo cycles so any command that references it (none today,
    but the invariant is cheap to maintain) still resolves.
    """

    def __init__(
        self,
        scene: BondForgeScene,
        begin_atom_id: int,
        end_atom_id: int,
        order: BondOrder = BondOrder.SINGLE,
        stereo: BondStereo = BondStereo.NONE,
    ) -> None:
        super().__init__("Add bond")
        self._scene = scene
        self._begin = begin_atom_id
        self._end = end_atom_id
        self._order = order
        self._stereo = stereo
        self.created_bond_id: int = -1

    def redo(self) -> None:
        mol = self._scene.molecule
        bond = mol.add_bond(self._begin, self._end, self._order, self._stereo)
        if self.created_bond_id == -1:
            self.created_bond_id = bond.id
        elif bond.id != self.created_bond_id:
            mol.bonds.pop(bond.id)
            bond.id = self.created_bond_id
            mol.bonds[self.created_bond_id] = bond
            mol._next_bond_id = max(mol._next_bond_id, self.created_bond_id + 1)
        self._scene.rebuild()

    def undo(self) -> None:
        if self.created_bond_id != -1:
            self._scene.molecule.remove_bond(self.created_bond_id)
            self._scene.rebuild()


class DeleteSelectionCommand(QUndoCommand):
    """Delete a set of atoms (and incident bonds) by ID."""

    def __init__(self, scene: BondForgeScene, atom_ids: list[int]) -> None:
        super().__init__("Delete selection")
        self._scene = scene
        self._atom_ids = list(atom_ids)
        self._snapshot_atoms: list[tuple[int, str, float, float, int]] = []
        self._snapshot_bonds: list[tuple[int, int, int, BondOrder, BondStereo]] = []

    def redo(self) -> None:
        mol = self._scene.molecule
        # Snapshot first so undo can restore.
        self._snapshot_atoms.clear()
        self._snapshot_bonds.clear()
        targets = set(self._atom_ids)
        for atom_id in self._atom_ids:
            atom = mol.atoms.get(atom_id)
            if atom is None:
                continue
            self._snapshot_atoms.append((atom.id, atom.element, atom.x, atom.y, atom.charge))
        for bond in list(mol.iter_bonds()):
            if bond.begin_atom_id in targets or bond.end_atom_id in targets:
                self._snapshot_bonds.append(
                    (bond.id, bond.begin_atom_id, bond.end_atom_id, bond.order, bond.stereo)
                )
        for atom_id in self._atom_ids:
            if atom_id in mol.atoms:
                mol.remove_atom(atom_id)
        self._scene.rebuild()

    def undo(self) -> None:
        mol = self._scene.molecule
        for aid, element, x, y, charge in self._snapshot_atoms:
            atom = mol.add_atom(element, x, y, charge=charge)
            # Restore the original ID so bonds can find it again.
            mol.atoms.pop(atom.id)
            atom.id = aid
            mol.atoms[aid] = atom
            mol._next_atom_id = max(mol._next_atom_id, aid + 1)
        for bid, begin, end, order, stereo in self._snapshot_bonds:
            bond = mol.add_bond(begin, end, order, stereo)
            mol.bonds.pop(bond.id)
            bond.id = bid
            mol.bonds[bid] = bond
            mol._next_bond_id = max(mol._next_bond_id, bid + 1)
        self._scene.rebuild()


class ChangeElementCommand(QUndoCommand):
    """Change the element of an existing atom."""

    def __init__(self, scene: BondForgeScene, atom_id: int, element: str) -> None:
        super().__init__(f"Change to {element}")
        self._scene = scene
        self._atom_id = atom_id
        self._new_element = element
        self._old_element: str | None = None

    def redo(self) -> None:
        atom = self._scene.molecule.atoms.get(self._atom_id)
        if atom is None:
            return
        self._old_element = atom.element
        atom.element = self._new_element
        self._scene.rebuild()

    def undo(self) -> None:
        atom = self._scene.molecule.atoms.get(self._atom_id)
        if atom is None or self._old_element is None:
            return
        atom.element = self._old_element
        self._scene.rebuild()


class SetChargeCommand(QUndoCommand):
    """Adjust an atom's formal charge by ``delta`` (positive or negative)."""

    def __init__(self, scene: BondForgeScene, atom_id: int, delta: int) -> None:
        super().__init__("Change charge")
        self._scene = scene
        self._atom_id = atom_id
        self._delta = delta
        self._applied = 0

    def redo(self) -> None:
        atom = self._scene.molecule.atoms.get(self._atom_id)
        if atom is None:
            self._applied = 0
            return
        atom.charge += self._delta
        self._applied = self._delta
        self._scene.rebuild()

    def undo(self) -> None:
        atom = self._scene.molecule.atoms.get(self._atom_id)
        if atom is None or self._applied == 0:
            return
        atom.charge -= self._applied
        self._scene.rebuild()


class SetBondOrderCommand(QUndoCommand):
    """Set a bond's order to a specific :class:`BondOrder` value."""

    def __init__(self, scene: BondForgeScene, bond_id: int, order: BondOrder) -> None:
        super().__init__(f"Set bond to {order.name.lower()}")
        self._scene = scene
        self._bond_id = bond_id
        self._new_order = order
        self._old_order: BondOrder | None = None

    def redo(self) -> None:
        bond = self._scene.molecule.bonds.get(self._bond_id)
        if bond is None:
            return
        self._old_order = bond.order
        bond.order = self._new_order
        self._scene.rebuild()

    def undo(self) -> None:
        bond = self._scene.molecule.bonds.get(self._bond_id)
        if bond is None or self._old_order is None:
            return
        bond.order = self._old_order
        self._scene.rebuild()


class CycleBondOrderCommand(QUndoCommand):
    """Set a bond's order. Used by the ``1`` / ``2`` / ``3`` hotkeys."""

    _ORDERS = {
        1: BondOrder.SINGLE,
        2: BondOrder.DOUBLE,
        3: BondOrder.TRIPLE,
    }

    def __init__(self, scene: BondForgeScene, bond_id: int, order_index: int) -> None:
        super().__init__(f"Set bond order {order_index}")
        self._scene = scene
        self._bond_id = bond_id
        self._new_order = self._ORDERS.get(order_index, BondOrder.SINGLE)
        self._old_order: BondOrder | None = None

    def redo(self) -> None:
        bond = self._scene.molecule.bonds.get(self._bond_id)
        if bond is None:
            return
        self._old_order = bond.order
        bond.order = self._new_order
        self._scene.rebuild()

    def undo(self) -> None:
        bond = self._scene.molecule.bonds.get(self._bond_id)
        if bond is None or self._old_order is None:
            return
        bond.order = self._old_order
        self._scene.rebuild()


class CleanupStructureCommand(QUndoCommand):
    """Re-lay out the entire molecule with RDKit's 2D coordinate generator.

    The command snapshots the prior coordinates so an undo restores them
    exactly. Cleanup is whole-molecule and idempotent — running it twice
    in a row produces no further changes.
    """

    def __init__(self, scene: BondForgeScene) -> None:
        super().__init__("Clean up structure")
        self._scene = scene
        self._old_positions: dict[int, tuple[float, float]] = {}

    def redo(self) -> None:
        # Imported lazily to avoid pulling RDKit into modules that don't need it.
        from bondforge.engine.cleanup import compute_clean_2d_coords

        mol = self._scene.molecule
        self._old_positions = {a.id: (a.x, a.y) for a in mol.iter_atoms()}
        compute_clean_2d_coords(mol)
        self._scene.rebuild()

    def undo(self) -> None:
        mol = self._scene.molecule
        for atom_id, (x, y) in self._old_positions.items():
            atom = mol.atoms.get(atom_id)
            if atom is not None:
                atom.x = x
                atom.y = y
        self._scene.rebuild()


__all__ = [
    "AddAtomCommand",
    "AddBondCommand",
    "DeleteSelectionCommand",
    "ChangeElementCommand",
    "SetChargeCommand",
    "SetBondOrderCommand",
    "CycleBondOrderCommand",
    "CleanupStructureCommand",
]
