"""Unit tests for the display-side Molecule data model."""

from __future__ import annotations

import pytest

from bondforge.core.model.bond import BondOrder
from bondforge.core.model.molecule import Molecule


def test_add_atoms_assigns_unique_ids() -> None:
    mol = Molecule()
    a = mol.add_atom("C", 0, 0)
    b = mol.add_atom("O", 1, 0)
    assert a.id != b.id
    assert mol.atoms[a.id] is a
    assert mol.atoms[b.id] is b


def test_add_bond_links_existing_atoms() -> None:
    mol = Molecule()
    a = mol.add_atom("C", 0, 0)
    b = mol.add_atom("O", 1, 0)
    bond = mol.add_bond(a.id, b.id, BondOrder.DOUBLE)
    assert bond.order == BondOrder.DOUBLE
    assert bond.other_atom_id(a.id) == b.id
    assert bond.other_atom_id(b.id) == a.id


def test_remove_atom_drops_incident_bonds() -> None:
    mol = Molecule()
    a = mol.add_atom("C")
    b = mol.add_atom("C")
    c = mol.add_atom("C")
    mol.add_bond(a.id, b.id)
    mol.add_bond(b.id, c.id)
    assert len(mol.bonds) == 2
    mol.remove_atom(b.id)
    assert len(mol.bonds) == 0
    assert b.id not in mol.atoms


def test_self_bond_rejected() -> None:
    mol = Molecule()
    a = mol.add_atom("C")
    with pytest.raises(ValueError):
        mol.add_bond(a.id, a.id)


def test_bonds_for_atom() -> None:
    mol = Molecule()
    a = mol.add_atom("C")
    b = mol.add_atom("C")
    c = mol.add_atom("C")
    mol.add_bond(a.id, b.id)
    mol.add_bond(b.id, c.id)
    assert {bond.id for bond in mol.bonds_for_atom(b.id)} == set(mol.bonds)
    assert len(list(mol.bonds_for_atom(a.id))) == 1
