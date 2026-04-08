"""IO round-trip tests for MOL and SMILES."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("rdkit")

from rdkit import Chem  # noqa: E402

from bondforge.core.io.mol import read_mol_file, write_mol  # noqa: E402
from bondforge.core.io.smiles import read_smiles, write_smiles  # noqa: E402
from bondforge.engine.rdkit_adapter import sanitized  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_read_benzene_mol_file() -> None:
    mol = read_mol_file(FIXTURES / "benzene.mol")
    assert len(mol.atoms) == 6
    assert len(mol.bonds) == 6
    smiles = Chem.MolToSmiles(sanitized(mol))
    assert smiles == "c1ccccc1"


def test_write_then_read_mol_round_trip(tmp_path: Path) -> None:
    mol = read_mol_file(FIXTURES / "benzene.mol")
    block = write_mol(mol)
    out = tmp_path / "out.mol"
    out.write_text(block, encoding="utf-8")
    mol2 = read_mol_file(out)
    assert len(mol.atoms) == len(mol2.atoms)
    assert len(mol.bonds) == len(mol2.bonds)


def test_smiles_round_trip() -> None:
    mol = read_smiles("CC(=O)O")
    assert len(mol.atoms) == 4
    assert write_smiles(mol) == "CC(=O)O"
