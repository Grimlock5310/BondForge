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


def test_repeated_click_extension_forms_zigzag_not_hexagon() -> None:
    """Five repeated click-extensions should trace a zigzag. The
    previous heuristic used +120° offsets and closed back into a hexagon,
    which is the bug this fix addresses."""
    import math

    mol = Molecule()
    start = mol.add_atom("C", 0.0, 0.0)

    def hit(pos):
        # Return whatever atom has the closest match to the cursor.
        best = None
        best_d = 1.0
        for atom in mol.iter_atoms():
            d = math.hypot(pos.x() - atom.x, pos.y() - atom.y)
            if d < best_d:
                best = atom
                best_d = d
        return _FakeAtomItem(best) if best is not None else None

    scene = _FakeScene(mol)
    tool = BondTool(scene, undo_stack=None)
    tool._atom_at = hit  # type: ignore[method-assign]

    # Repeatedly "click" on the current tip atom.
    tip_id = start.id
    for _ in range(5):
        tip = mol.atoms[tip_id]
        click = QPointF(tip.x, tip.y)
        tool.mouse_press(_FakeEvent(click))
        tool.mouse_release(_FakeEvent(click))
        # Newest atom is the one with the highest ID.
        tip_id = max(mol.atoms.keys())

    # Six atoms total; five bonds. A hexagon would have closed with only
    # six atoms *and* six bonds, with the final tip returning near (0, 0).
    assert len(mol.atoms) == 6
    assert len(mol.bonds) == 5
    final_tip = mol.atoms[tip_id]
    assert math.hypot(final_tip.x, final_tip.y) > 100.0


def test_click_on_bond_with_double_tool_sets_bond_to_double() -> None:
    from bondforge.core.model.bond import BondOrder

    mol = Molecule()
    a = mol.add_atom("C", 0.0, 0.0)
    b = mol.add_atom("C", 50.0, 0.0)
    existing_bond = mol.add_bond(a.id, b.id, BondOrder.SINGLE)

    class _FakeBondItem:
        def __init__(self, bond) -> None:
            self.bond = bond

    scene = _FakeScene(mol)
    tool = BondTool(scene, undo_stack=None, order=BondOrder.DOUBLE)
    tool._atom_at = lambda pos: None  # type: ignore[method-assign]
    tool._bond_at = lambda pos: _FakeBondItem(existing_bond)  # type: ignore[method-assign]

    # Click the midpoint of the bond. Mouse_press alone should have
    # upgraded the order; the release must not spawn new atoms or bonds.
    click = QPointF(25.0, 0.0)
    tool.mouse_press(_FakeEvent(click))
    tool.mouse_release(_FakeEvent(click))

    assert len(mol.atoms) == 2, "no new atoms should appear"
    assert len(mol.bonds) == 1, "no new bonds should appear"
    assert mol.bonds[existing_bond.id].order == BondOrder.DOUBLE


def test_click_on_bond_with_triple_tool_sets_bond_to_triple() -> None:
    from bondforge.core.model.bond import BondOrder

    mol = Molecule()
    a = mol.add_atom("C", 0.0, 0.0)
    b = mol.add_atom("C", 50.0, 0.0)
    existing_bond = mol.add_bond(a.id, b.id, BondOrder.DOUBLE)

    class _FakeBondItem:
        def __init__(self, bond) -> None:
            self.bond = bond

    scene = _FakeScene(mol)
    tool = BondTool(scene, undo_stack=None, order=BondOrder.TRIPLE)
    tool._atom_at = lambda pos: None  # type: ignore[method-assign]
    tool._bond_at = lambda pos: _FakeBondItem(existing_bond)  # type: ignore[method-assign]

    click = QPointF(25.0, 0.0)
    tool.mouse_press(_FakeEvent(click))
    tool.mouse_release(_FakeEvent(click))

    assert mol.bonds[existing_bond.id].order == BondOrder.TRIPLE
