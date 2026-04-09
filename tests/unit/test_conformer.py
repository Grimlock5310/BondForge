"""Tests for 3D conformer generation and force-field minimization."""

from __future__ import annotations

import pytest

pytest.importorskip("rdkit")

from bondforge.core.io.smiles import read_smiles  # noqa: E402
from bondforge.core.model.molecule import Molecule  # noqa: E402
from bondforge.engine.conformer import ConformerError, generate_conformer  # noqa: E402
from bondforge.engine.forcefield import minimize  # noqa: E402


def test_generate_conformer_ethanol() -> None:
    mol = read_smiles("CCO")
    rd_mol = generate_conformer(mol)
    assert rd_mol.GetNumConformers() >= 1
    conf = rd_mol.GetConformer(0)
    # Should have 3D coordinates (z != 0 for at least one atom).
    has_3d = any(abs(conf.GetAtomPosition(i).z) > 0.01 for i in range(rd_mol.GetNumAtoms()))
    assert has_3d


def test_generate_conformer_empty_raises() -> None:
    with pytest.raises(ConformerError):
        generate_conformer(Molecule())


def test_minimize_ethanol() -> None:
    mol = read_smiles("CCO")
    rd_mol = generate_conformer(mol)
    result = minimize(rd_mol)
    assert result.energy < 1e6  # reasonable energy
    assert result.force_field in ("MMFF94", "UFF")


def test_generate_multiple_conformers() -> None:
    mol = read_smiles("CCCC")
    rd_mol = generate_conformer(mol, num_conformers=3)
    assert rd_mol.GetNumConformers() >= 1
