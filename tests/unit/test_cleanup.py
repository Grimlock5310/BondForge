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
