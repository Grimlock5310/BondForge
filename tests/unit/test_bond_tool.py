"""Tests for the bond tool's click-to-extend behavior.

In v0.2 the bond tool grew a "click in empty space → pick best free
angle" shortcut. The fix under test here extends that shortcut to also
fire when the user taps an *existing* atom (press and release on the
same atom), so repeatedly tapping the end of a chain grows a new bond
instead of doing nothing.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF  # noqa: E402

from bondforge.canvas.tools.bond_tool import BondTool  # noqa: E402
from bondforge.core.model.molecule import Molecule  # noqa: E402


class _FakeScene:
    def __init__(self, molecule: Molecule) -> None:
        self.molecule = molecule
        self.rebuilds = 0
        self._previews: list = []

    def rebuild(self) -> None:
        self.rebuilds += 1

    def views(self) -> list:
        return []

    def add_preview_item(self, item) -> None:
        self._previews.append(item)

    def clear_previews(self) -> None:
        self._previews.clear()


class _FakeEvent:
    def __init__(self, pos: QPointF) -> None:
        self._pos = pos

    def scenePos(self) -> QPointF:  # noqa: N802 — Qt-style
        return self._pos


class _FakeAtomItem:
    def __init__(self, atom) -> None:
        self.atom = atom


def _make_tool_with_stub(mol: Molecule, hovered) -> tuple[BondTool, _FakeScene]:
    """Build a BondTool whose hit-test always returns ``hovered``."""
    scene = _FakeScene(mol)
    tool = BondTool(scene, undo_stack=None)
    tool._atom_at = lambda pos: hovered  # type: ignore[method-assign]
    return tool, scene


def test_click_on_empty_canvas_creates_single_bond_and_new_atom() -> None:
    mol = Molecule()
    tool, scene = _make_tool_with_stub(mol, hovered=None)

    click = QPointF(100.0, 100.0)
    tool.mouse_press(_FakeEvent(click))
    tool.mouse_release(_FakeEvent(click))

    assert len(mol.atoms) == 2
    assert len(mol.bonds) == 1


def test_click_on_existing_atom_grows_a_new_bond() -> None:
    """This is the bug-4 regression: tapping on an existing atom used to
    do nothing because press and release resolved to the same atom and
    the tool skipped the ``start_id == end_id`` case."""
    mol = Molecule()
    start = mol.add_atom("C", 200.0, 200.0)

    # Hit-test is stubbed to always return the existing atom so press and
    # release both resolve to it.
    hovered = _FakeAtomItem(start)
    tool, scene = _make_tool_with_stub(mol, hovered=hovered)

    click = QPointF(200.0, 200.0)
    tool.mouse_press(_FakeEvent(click))
    tool.mouse_release(_FakeEvent(click))

    assert len(mol.atoms) == 2, "new carbon should have been added"
    assert len(mol.bonds) == 1, "new bond should connect the two atoms"
    bond = next(iter(mol.bonds.values()))
    assert start.id in (bond.begin_atom_id, bond.end_atom_id)
