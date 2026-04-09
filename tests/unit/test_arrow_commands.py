"""Tests for arrow and atom-mapping commands."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from bondforge.core.commands import (  # noqa: E402
    AddArrowCommand,
    DeleteArrowCommand,
    SetAtomMapNumberCommand,
)
from bondforge.core.model.arrow import ArrowKind  # noqa: E402
from bondforge.core.model.document import Document  # noqa: E402
from bondforge.core.model.molecule import Molecule  # noqa: E402


class _FakeScene:
    """Minimal scene stand-in exposing the bits arrow commands need."""

    def __init__(self) -> None:
        self._document = Document(molecule=Molecule())
        self.rebuilds = 0

    @property
    def document(self) -> Document:
        return self._document

    @property
    def molecule(self) -> Molecule:
        return self._document.molecule

    def rebuild(self) -> None:
        self.rebuilds += 1


def test_add_arrow_command_round_trip() -> None:
    scene = _FakeScene()
    cmd = AddArrowCommand(scene, ArrowKind.FORWARD, 0, 0, 100, 0)
    cmd.redo()
    assert len(scene.document.arrows) == 1
    assert cmd.created_arrow_id == 1
    arrow = scene.document.arrows[1]
    assert arrow.kind == ArrowKind.FORWARD
    assert arrow.x2 == 100

    cmd.undo()
    assert len(scene.document.arrows) == 0


def test_add_arrow_preserves_id_across_redo_cycles() -> None:
    scene = _FakeScene()
    cmd = AddArrowCommand(scene, ArrowKind.EQUILIBRIUM, 0, 0, 50, 50)
    cmd.redo()
    original_id = cmd.created_arrow_id
    cmd.undo()
    cmd.redo()
    assert cmd.created_arrow_id == original_id
    assert original_id in scene.document.arrows


def test_delete_arrow_command_round_trip() -> None:
    scene = _FakeScene()
    arrow = scene.document.add_arrow(ArrowKind.FORWARD, 0, 0, 80, 0, label="H2SO4")
    cmd = DeleteArrowCommand(scene, arrow.id)
    cmd.redo()
    assert arrow.id not in scene.document.arrows
    cmd.undo()
    restored = scene.document.arrows[arrow.id]
    assert restored.kind == ArrowKind.FORWARD
    assert restored.label == "H2SO4"
    assert restored.x2 == 80


def test_set_atom_map_number_command_round_trip() -> None:
    scene = _FakeScene()
    atom = scene.molecule.add_atom("C", 0, 0)
    cmd = SetAtomMapNumberCommand(scene, atom.id, 1)
    cmd.redo()
    assert scene.molecule.atoms[atom.id].map_number == 1
    cmd.undo()
    assert scene.molecule.atoms[atom.id].map_number == 0
