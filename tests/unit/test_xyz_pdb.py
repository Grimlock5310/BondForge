"""Tests for XYZ and PDB file IO."""

from __future__ import annotations

import pytest

pytest.importorskip("rdkit")

from bondforge.core.io.pdb import read_pdb, write_pdb  # noqa: E402
from bondforge.core.io.smiles import read_smiles  # noqa: E402
from bondforge.core.io.xyz import read_xyz, write_xyz  # noqa: E402
from bondforge.engine.conformer import generate_conformer  # noqa: E402


def test_xyz_write_and_read_round_trip() -> None:
    mol = read_smiles("O")  # water
    rd_mol = generate_conformer(mol)
    text = write_xyz(rd_mol, comment="water")
    lines = text.strip().splitlines()
    atom_count = int(lines[0])
    assert atom_count == rd_mol.GetNumAtoms()
    assert lines[1] == "water"

    # Read it back.
    parsed = read_xyz(text)
    assert len(parsed.atoms) == atom_count


def test_xyz_read_invalid_raises() -> None:
    with pytest.raises(ValueError):
        read_xyz("not a valid xyz")


def test_pdb_write_produces_atom_lines() -> None:
    mol = read_smiles("CCO")
    rd_mol = generate_conformer(mol)
    text = write_pdb(rd_mol)
    # PDB should contain HETATM or ATOM lines.
    assert "ATOM" in text or "HETATM" in text


def test_pdb_read_round_trip() -> None:
    mol = read_smiles("CCO")
    rd_mol = generate_conformer(mol)
    text = write_pdb(rd_mol)
    parsed = read_pdb(text)
    assert len(parsed.atoms) > 0
