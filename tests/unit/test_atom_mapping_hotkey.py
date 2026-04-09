"""Tests for the atom-mapping ``m`` hotkey dispatcher logic."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from bondforge.canvas.hotkeys import HotkeyDispatcher  # noqa: E402
from bondforge.core.model.document import Document  # noqa: E402
from bondforge.core.model.molecule import Molecule  # noqa: E402


class _FakeScene:
    """Minimal scene that exposes ``molecule`` and a views() accessor."""

    def __init__(self, molecule: Molecule) -> None:
        self._molecule = molecule
        self._document = Document(molecule=molecule)

    @property
    def molecule(self) -> Molecule:
        return self._molecule

    @property
    def document(self) -> Document:
        return self._document

    def views(self) -> list:  # pragma: no cover - unused in _next_map_number
        return []

    def rebuild(self) -> None:  # pragma: no cover - unused
        pass


def test_next_map_number_starts_at_one() -> None:
    mol = Molecule()
    mol.add_atom("C", 0, 0)
    mol.add_atom("C", 50, 0)
    dispatcher = HotkeyDispatcher(_FakeScene(mol))
    assert dispatcher._next_map_number() == 1


def test_next_map_number_fills_gaps() -> None:
    mol = Molecule()
    a = mol.add_atom("C", 0, 0)
    b = mol.add_atom("C", 50, 0)
    c = mol.add_atom("C", 100, 0)
    a.map_number = 1
    c.map_number = 3
    # b is unmapped; the next number should be 2 because it's the
    # smallest positive integer not yet in use.
    dispatcher = HotkeyDispatcher(_FakeScene(mol))
    assert dispatcher._next_map_number() == 2
    b.map_number = 2
    assert dispatcher._next_map_number() == 4
