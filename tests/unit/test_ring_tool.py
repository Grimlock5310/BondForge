"""Tests for the ring tool: placement strategies and undo atomicity.

These tests exercise the ring tool's three placement modes directly —
``_place_centered``, ``_fuse_to_atom``, and ``_fuse_to_bond`` — without
synthesizing fake mouse events. They also verify that ring creation with
a real :class:`QUndoStack` is a single macro so one ``Ctrl+Z`` rolls back
the whole ring rather than undoing atom-by-atom.
"""

from __future__ import annotations

import math

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QUndoStack  # noqa: E402

from bondforge.canvas.items.atom_item import AtomItem  # noqa: E402
from bondforge.canvas.items.bond_item import BondItem  # noqa: E402
from bondforge.canvas.tools.ring_tool import RingTool  # noqa: E402
from bondforge.core.model.molecule import Molecule  # noqa: E402


class _FakeScene:
    """Minimal scene stand-in. The ring tool only touches ``molecule`` and
    ``rebuild``; it never iterates items directly when called via the
    private placement methods."""

    def __init__(self, molecule: Molecule) -> None:
        self.molecule = molecule
        self.rebuilds = 0

    def rebuild(self) -> None:
        self.rebuilds += 1

    def views(self) -> list:  # noqa: D401 — Qt-style API
        return []


def _edge_lengths(mol: Molecule) -> list[float]:
    out: list[float] = []
    for bond in mol.iter_bonds():
        a = mol.atoms[bond.begin_atom_id]
        b = mol.atoms[bond.end_atom_id]
        out.append(math.hypot(a.x - b.x, a.y - b.y))
    return out


def test_place_centered_creates_n_atoms_and_n_bonds() -> None:
    scene = _FakeScene(Molecule())
    tool = RingTool(scene, undo_stack=None, size=6, aromatic=True)
    tool._place_centered(100.0, 100.0)
    assert len(scene.molecule.atoms) == 6
    assert len(scene.molecule.bonds) == 6
    for ll in _edge_lengths(scene.molecule):
        assert ll == pytest.approx(50.0, rel=0.02)


def test_fuse_to_atom_shares_vertex() -> None:
    mol = Molecule()
    shared = mol.add_atom("C", 0.0, 0.0)
    scene = _FakeScene(mol)
    tool = RingTool(scene, undo_stack=None, size=6, aromatic=False)

    # Wrap the existing atom in a minimal AtomItem stub so ``_fuse_to_atom``
    # can read ``atom_item.atom`` and the molecule-level neighbor queries.
    class _FakeAtomItem:
        def __init__(self, atom) -> None:
            self.atom = atom

    tool._fuse_to_atom(_FakeAtomItem(shared))
    # Shared vertex reused → 5 new atoms, 6 new bonds.
    assert len(scene.molecule.atoms) == 6
    assert len(scene.molecule.bonds) == 6
    # The shared atom is still at its original position.
    assert scene.molecule.atoms[shared.id].x == 0.0
    assert scene.molecule.atoms[shared.id].y == 0.0
    # Every bond length equals the default.
    for ll in _edge_lengths(scene.molecule):
        assert ll == pytest.approx(50.0, rel=0.02)


def test_fuse_to_bond_shares_edge_and_adds_on_click_side() -> None:
    mol = Molecule()
    a = mol.add_atom("C", 0.0, 0.0)
    b = mol.add_atom("C", 50.0, 0.0)
    bond = mol.add_bond(a.id, b.id)
    scene = _FakeScene(mol)
    tool = RingTool(scene, undo_stack=None, size=6, aromatic=False)

    class _FakeBondItem:
        def __init__(self, bond) -> None:
            self.bond = bond

    # Click below the bond (positive y in scene coords = "down").
    tool._fuse_to_bond(_FakeBondItem(bond), QPointF(25.0, 50.0))
    # 2 existing atoms + 4 new atoms, 1 existing bond + 5 new bonds.
    assert len(scene.molecule.atoms) == 6
    assert len(scene.molecule.bonds) == 6

    # New atoms should all live on the "click side" (y > 0 on average).
    new_atoms = [at for at in scene.molecule.iter_atoms() if at.id not in (a.id, b.id)]
    assert all(at.y > 0 for at in new_atoms)

    # Edge lengths should still be uniform.
    for ll in _edge_lengths(scene.molecule):
        assert ll == pytest.approx(50.0, rel=0.02)


def test_fuse_to_bond_opposite_side_when_click_is_above() -> None:
    mol = Molecule()
    a = mol.add_atom("C", 0.0, 0.0)
    b = mol.add_atom("C", 50.0, 0.0)
    bond = mol.add_bond(a.id, b.id)
    scene = _FakeScene(mol)
    tool = RingTool(scene, undo_stack=None, size=6, aromatic=False)

    class _FakeBondItem:
        def __init__(self, bond) -> None:
            self.bond = bond

    # Click *above* the bond (negative y in Qt scene coords).
    tool._fuse_to_bond(_FakeBondItem(bond), QPointF(25.0, -50.0))
    new_atoms = [at for at in scene.molecule.iter_atoms() if at.id not in (a.id, b.id)]
    assert all(at.y < 0 for at in new_atoms)


def test_ring_creation_is_single_undo_macro() -> None:
    mol = Molecule()
    scene = _FakeScene(mol)
    undo_stack = QUndoStack()
    tool = RingTool(scene, undo_stack=undo_stack, size=6, aromatic=True)

    # Simulate a click on empty canvas. We don't bother faking a
    # QGraphicsSceneMouseEvent — the tool only uses ``scenePos()``.
    class _FakeEvent:
        def __init__(self, pos: QPointF) -> None:
            self._pos = pos

        def scenePos(self) -> QPointF:  # noqa: N802 — Qt-style
            return self._pos

    tool.mouse_press(_FakeEvent(QPointF(0.0, 0.0)))
    assert len(scene.molecule.atoms) == 6
    assert len(scene.molecule.bonds) == 6
    assert undo_stack.count() == 1

    undo_stack.undo()
    assert len(scene.molecule.atoms) == 0
    assert len(scene.molecule.bonds) == 0

    undo_stack.redo()
    assert len(scene.molecule.atoms) == 6
    assert len(scene.molecule.bonds) == 6


# Suppress the unused-import warning — AtomItem and BondItem are imported
# so the type hints in production code stay resolvable under the test's
# headless Qt environment.
_ = AtomItem
_ = BondItem
