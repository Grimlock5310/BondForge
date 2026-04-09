"""Tests for journal style presets."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from bondforge.canvas.styles import (  # noqa: E402
    ACS_1996,
    NATURE,
    RSC,
    STYLES,
    apply_style,
)
from bondforge.core.model.document import Document  # noqa: E402
from bondforge.core.model.molecule import Molecule  # noqa: E402


class _FakeScene:
    def __init__(self, doc: Document | None = None) -> None:
        self._document = doc or Document(molecule=Molecule())
        self.rebuilds = 0

    @property
    def molecule(self) -> Molecule:
        return self._document.molecule

    @property
    def document(self) -> Document:
        return self._document

    def rebuild(self) -> None:
        self.rebuilds += 1


def test_all_styles_present() -> None:
    assert "ACS" in STYLES
    assert "RSC" in STYLES
    assert "Nature" in STYLES
    assert "Wiley" in STYLES
    assert "Default" in STYLES


def test_style_bond_length_conversion() -> None:
    # ACS bond length is 14.4 pt, at 96 dpi: 14.4 * 96/72 = 19.2 px
    assert abs(ACS_1996.bond_length_px - 19.2) < 0.01


def test_apply_style_scales_molecule() -> None:
    mol = Molecule()
    a1 = mol.add_atom("C", 0, 0)
    a2 = mol.add_atom("C", 50, 0)
    mol.add_bond(a1.id, a2.id)
    scene = _FakeScene(Document(molecule=mol))

    apply_style(scene, ACS_1996)

    # After applying ACS style, bond length should be ~19.2 px
    ra1 = scene.molecule.atoms[a1.id]
    ra2 = scene.molecule.atoms[a2.id]
    actual_length = abs(ra2.x - ra1.x)
    assert abs(actual_length - ACS_1996.bond_length_px) < 0.1


def test_apply_style_empty_molecule() -> None:
    scene = _FakeScene()
    # Should not raise on empty molecule.
    apply_style(scene, RSC)
    assert scene.rebuilds == 1


def test_apply_style_triggers_rebuild() -> None:
    mol = Molecule()
    mol.add_atom("C", 0, 0)
    mol.add_atom("C", 50, 0)
    scene = _FakeScene(Document(molecule=mol))
    apply_style(scene, NATURE)
    assert scene.rebuilds >= 1


def test_style_names_unique() -> None:
    names = [s.name for s in STYLES.values()]
    assert len(names) == len(set(names))
