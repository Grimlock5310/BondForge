"""Tests for the native .bforge JSON serialization format."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from bondforge.core.io.bforge import (
    FORMAT_VERSION,
    document_to_json,
    json_to_document,
    load_bforge,
    save_bforge,
)
from bondforge.core.model.arrow import ArrowKind
from bondforge.core.model.bond import BondOrder, BondStereo
from bondforge.core.model.document import Document
from bondforge.core.model.molecule import Molecule


def _make_doc() -> Document:
    """Build a small test document with atoms, bonds, arrows, and text."""
    mol = Molecule()
    a1 = mol.add_atom("C", 0, 0, charge=1)
    a2 = mol.add_atom("O", 50, 0)
    mol.add_bond(a1.id, a2.id, BondOrder.DOUBLE, BondStereo.NONE)
    doc = Document(molecule=mol)
    doc.add_arrow(ArrowKind.FORWARD, 100, 0, 200, 0, label="heat")
    doc.add_text("reagent", 150, -20, bold=True, font_size=14.0)
    return doc


def test_round_trip_json() -> None:
    doc = _make_doc()
    text = document_to_json(doc)
    restored = json_to_document(text)

    # Molecule
    assert len(restored.molecule.atoms) == 2
    assert len(restored.molecule.bonds) == 1
    atom1 = restored.molecule.atoms[1]
    assert atom1.element == "C"
    assert atom1.charge == 1
    bond = list(restored.molecule.iter_bonds())[0]
    assert bond.order == BondOrder.DOUBLE

    # Arrows
    assert len(restored.arrows) == 1
    arrow = list(restored.iter_arrows())[0]
    assert arrow.kind == ArrowKind.FORWARD
    assert arrow.label == "heat"

    # Texts
    assert len(restored.texts) == 1
    ann = list(restored.iter_texts())[0]
    assert ann.text == "reagent"
    assert ann.bold is True
    assert ann.font_size == 14.0


def test_round_trip_file() -> None:
    doc = _make_doc()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.bforge"
        save_bforge(doc, path)
        restored = load_bforge(path)

    assert len(restored.molecule.atoms) == 2
    assert len(restored.arrows) == 1
    assert len(restored.texts) == 1


def test_format_version_in_json() -> None:
    doc = Document()
    text = document_to_json(doc)
    data = json.loads(text)
    assert data["format"] == "bforge"
    assert data["version"] == FORMAT_VERSION


def test_rejects_unknown_format() -> None:
    import pytest

    with pytest.raises(ValueError, match="Not a .bforge file"):
        json_to_document('{"format": "other"}')


def test_rejects_future_version() -> None:
    import pytest

    payload = json.dumps({"format": "bforge", "version": 999, "document": {}})
    with pytest.raises(ValueError, match="newer than this BondForge"):
        json_to_document(payload)


def test_id_counters_preserved() -> None:
    """After loading, new atoms/bonds should get IDs beyond the max existing."""
    doc = _make_doc()
    text = document_to_json(doc)
    restored = json_to_document(text)

    new_atom = restored.molecule.add_atom("N", 100, 100)
    assert new_atom.id > max(restored.molecule.atoms.keys() - {new_atom.id})

    new_arrow = restored.add_arrow(ArrowKind.EQUILIBRIUM, 0, 0, 50, 50)
    assert new_arrow.id > 1

    new_text = restored.add_text("new", 0, 0)
    assert new_text.id > 1


def test_empty_document_round_trip() -> None:
    doc = Document()
    text = document_to_json(doc)
    restored = json_to_document(text)
    assert len(restored.molecule.atoms) == 0
    assert len(restored.arrows) == 0
    assert len(restored.texts) == 0


def test_atom_optional_fields_round_trip() -> None:
    mol = Molecule()
    atom = mol.add_atom("C", 10, 20, isotope=13)
    atom.map_number = 3
    atom.radical_electrons = 1
    atom.explicit_hydrogens = 2
    atom.label = "R1"
    atom.is_query = True
    doc = Document(molecule=mol)

    restored = json_to_document(document_to_json(doc))
    ra = restored.molecule.atoms[atom.id]
    assert ra.isotope == 13
    assert ra.map_number == 3
    assert ra.radical_electrons == 1
    assert ra.explicit_hydrogens == 2
    assert ra.label == "R1"
    assert ra.is_query is True
