"""Tests for the MDL RXN reaction-file writer."""

from __future__ import annotations

import pytest

pytest.importorskip("rdkit")

from bondforge.core.io import RxnExportError, document_to_rxn  # noqa: E402
from bondforge.core.model.arrow import ArrowKind  # noqa: E402
from bondforge.core.model.document import Document  # noqa: E402
from bondforge.core.model.molecule import Molecule  # noqa: E402


def _two_component_reaction() -> Document:
    """Build a trivial A + B → C layout with one forward arrow.

    Reactant 1: methane (at x ~ -200)
    Reactant 2: water (at x ~ -100)
    Product:    a single carbon on the product side (at x ~ 200)
    Arrow:      horizontal, midpoint between them.
    """
    mol = Molecule()
    # Reactant side: isolated C at (-200, 0)
    mol.add_atom("C", -200, 0)
    # Another reactant: isolated O at (-100, 0)
    mol.add_atom("O", -100, 0)
    # Product side: a C-C bond at (+200, 0)
    p1 = mol.add_atom("C", 200, 0)
    p2 = mol.add_atom("C", 250, 0)
    mol.add_bond(p1.id, p2.id)

    doc = Document(molecule=mol)
    doc.add_arrow(ArrowKind.FORWARD, -20, 0, 20, 0)
    return doc


def test_rxn_export_emits_rxn_block() -> None:
    doc = _two_component_reaction()
    block = document_to_rxn(doc)
    assert block.startswith("$RXN")
    # Should mention at least two reactants and one product.
    lines = block.splitlines()
    # In V2000 RXN the 5th line is "  2  1" for 2 reactants + 1 product.
    counts_line = lines[4]
    reactant_count = int(counts_line[0:3])
    product_count = int(counts_line[3:6])
    assert reactant_count == 2
    assert product_count == 1


def test_rxn_export_requires_forward_arrow() -> None:
    mol = Molecule()
    mol.add_atom("C", 0, 0)
    doc = Document(molecule=mol)
    with pytest.raises(RxnExportError):
        document_to_rxn(doc)


def test_rxn_export_requires_atoms() -> None:
    doc = Document(molecule=Molecule())
    doc.add_arrow(ArrowKind.FORWARD, 0, 0, 100, 0)
    with pytest.raises(RxnExportError):
        document_to_rxn(doc)


def test_rxn_export_requires_both_sides_populated() -> None:
    """All atoms on one side of the arrow → should raise."""
    mol = Molecule()
    mol.add_atom("C", -100, 0)
    mol.add_atom("O", -50, 0)
    doc = Document(molecule=mol)
    # Arrow lives far to the right of everything, so all components are
    # on the tail side → no products.
    doc.add_arrow(ArrowKind.FORWARD, 200, 0, 300, 0)
    with pytest.raises(RxnExportError):
        document_to_rxn(doc)
