"""Tests for the command layer.

These tests don't spin up a QApplication; they instantiate the commands
directly against a fake scene that exposes only the bits the commands
actually touch (``molecule`` and ``rebuild``). This keeps the tests fast
and lets them run without an X server.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from bondforge.core.model.bond import BondOrder  # noqa: E402
from bondforge.core.model.molecule import Molecule  # noqa: E402


class _FakeScene:
    def __init__(self, molecule: Molecule) -> None:
        self.molecule = molecule
        self.rebuilds = 0

    def rebuild(self) -> None:
        self.rebuilds += 1


def _build_ethanol() -> tuple[_FakeScene, dict[str, int]]:
    mol = Molecule()
    c1 = mol.add_atom("C", 0, 0)
    c2 = mol.add_atom("C", 50, 0)
    o = mol.add_atom("O", 100, 0)
    b1 = mol.add_bond(c1.id, c2.id)
    b2 = mol.add_bond(c2.id, o.id)
    return _FakeScene(mol), {"c1": c1.id, "c2": c2.id, "o": o.id, "b1": b1.id, "b2": b2.id}


def test_set_charge_command_round_trip() -> None:
    from bondforge.core.commands import SetChargeCommand

    scene, ids = _build_ethanol()
    cmd = SetChargeCommand(scene, ids["o"], +1)
    cmd.redo()
    assert scene.molecule.atoms[ids["o"]].charge == 1
    cmd.undo()
    assert scene.molecule.atoms[ids["o"]].charge == 0


def test_cycle_bond_order_command() -> None:
    from bondforge.core.commands import CycleBondOrderCommand

    scene, ids = _build_ethanol()
    cmd = CycleBondOrderCommand(scene, ids["b1"], 2)
    cmd.redo()
    assert scene.molecule.bonds[ids["b1"]].order == BondOrder.DOUBLE
    cmd.undo()
    assert scene.molecule.bonds[ids["b1"]].order == BondOrder.SINGLE


def test_change_element_command() -> None:
    from bondforge.core.commands import ChangeElementCommand

    scene, ids = _build_ethanol()
    cmd = ChangeElementCommand(scene, ids["c1"], "N")
    cmd.redo()
    assert scene.molecule.atoms[ids["c1"]].element == "N"
    cmd.undo()
    assert scene.molecule.atoms[ids["c1"]].element == "C"


def test_delete_selection_command_round_trip() -> None:
    from bondforge.core.commands import DeleteSelectionCommand

    scene, ids = _build_ethanol()
    before_atoms = len(scene.molecule.atoms)
    before_bonds = len(scene.molecule.bonds)
    cmd = DeleteSelectionCommand(scene, [ids["c2"]])
    cmd.redo()
    assert len(scene.molecule.atoms) == before_atoms - 1
    assert len(scene.molecule.bonds) == 0  # both bonds touched c2
    cmd.undo()
    assert len(scene.molecule.atoms) == before_atoms
    assert len(scene.molecule.bonds) == before_bonds


def test_cleanup_structure_command_undo_restores_positions() -> None:
    pytest.importorskip("rdkit")
    from bondforge.core.commands import CleanupStructureCommand

    scene, ids = _build_ethanol()
    # Force ugly positions.
    scene.molecule.atoms[ids["c1"]].x = 1.0
    scene.molecule.atoms[ids["c1"]].y = 1.0
    scene.molecule.atoms[ids["c2"]].x = 1.5
    scene.molecule.atoms[ids["c2"]].y = 1.5
    scene.molecule.atoms[ids["o"]].x = 2.0
    scene.molecule.atoms[ids["o"]].y = 2.0
    snapshot = {a.id: (a.x, a.y) for a in scene.molecule.iter_atoms()}

    cmd = CleanupStructureCommand(scene)
    cmd.redo()
    # After cleanup, positions should differ.
    moved = any(snapshot[a.id] != (a.x, a.y) for a in scene.molecule.iter_atoms())
    assert moved
    cmd.undo()
    for atom in scene.molecule.iter_atoms():
        assert (atom.x, atom.y) == snapshot[atom.id]
