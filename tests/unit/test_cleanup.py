"""Tests for the structure clean-up engine."""

from __future__ import annotations

import math

import pytest

pytest.importorskip("rdkit")

from bondforge.canvas.geometry import DEFAULT_BOND_LENGTH  # noqa: E402
from bondforge.core.io.smiles import read_smiles  # noqa: E402
from bondforge.engine.cleanup import compute_clean_2d_coords  # noqa: E402


def test_cleanup_uniform_bond_lengths_for_benzene() -> None:
    mol = read_smiles("c1ccccc1")
    compute_clean_2d_coords(mol)
    lengths = []
    for bond in mol.iter_bonds():
        a = mol.atoms[bond.begin_atom_id]
        b = mol.atoms[bond.end_atom_id]
        lengths.append(math.hypot(a.x - b.x, a.y - b.y))
    avg = sum(lengths) / len(lengths)
    assert avg == pytest.approx(DEFAULT_BOND_LENGTH, rel=0.05)
    for ll in lengths:
        assert ll == pytest.approx(avg, rel=0.05)


def test_cleanup_preserves_centroid() -> None:
    mol = read_smiles("CCO")
    # Move the molecule somewhere arbitrary first.
    for atom in mol.iter_atoms():
        atom.x += 500
        atom.y -= 200
    cx_before = sum(a.x for a in mol.iter_atoms()) / len(mol.atoms)
    cy_before = sum(a.y for a in mol.iter_atoms()) / len(mol.atoms)
    compute_clean_2d_coords(mol)
    cx_after = sum(a.x for a in mol.iter_atoms()) / len(mol.atoms)
    cy_after = sum(a.y for a in mol.iter_atoms()) / len(mol.atoms)
    assert cx_after == pytest.approx(cx_before, abs=1e-6)
    assert cy_after == pytest.approx(cy_before, abs=1e-6)


def test_cleanup_empty_molecule_is_noop() -> None:
    from bondforge.core.model.molecule import Molecule

    mol = Molecule()
    compute_clean_2d_coords(mol)  # must not raise
    assert len(mol.atoms) == 0


def test_cleanup_survives_hypervalent_atom() -> None:
    """A nitrogen with five neighbors is chemically nonsense but users
    routinely produce it mid-edit. Clean-up must never crash on it."""
    from bondforge.core.model.molecule import Molecule

    mol = Molecule()
    n = mol.add_atom("N", 0.0, 0.0)
    for i in range(5):
        c = mol.add_atom("C", 50.0 * (i + 1), 0.0)
        mol.add_bond(n.id, c.id)
    # Must not raise.
    compute_clean_2d_coords(mol)
    # And every atom still has a finite position.
    for atom in mol.iter_atoms():
        assert math.isfinite(atom.x)
        assert math.isfinite(atom.y)


def test_cleanup_survives_kekulization_failure() -> None:
    """An odd-membered ring with all-aromatic bonds cannot be kekulized;
    the old cleanup path would raise from ``Chem.SanitizeMol``. The new
    path must still produce a layout."""
    from bondforge.core.model.bond import BondOrder
    from bondforge.core.model.molecule import Molecule

    mol = Molecule()
    atom_ids = [mol.add_atom("C", float(i * 50), 0.0).id for i in range(5)]
    for i in range(5):
        mol.add_bond(atom_ids[i], atom_ids[(i + 1) % 5], BondOrder.AROMATIC)
    # Must not raise.
    compute_clean_2d_coords(mol)
    assert len(mol.atoms) == 5
