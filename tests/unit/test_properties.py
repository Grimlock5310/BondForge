"""Tests for the molecular properties engine."""

from __future__ import annotations

import pytest

pytest.importorskip("rdkit")

from bondforge.core.io.smiles import read_smiles  # noqa: E402
from bondforge.core.model.molecule import Molecule  # noqa: E402
from bondforge.engine.properties import compute_properties  # noqa: E402


def test_compute_properties_benzene() -> None:
    mol = read_smiles("c1ccccc1")
    props = compute_properties(mol)
    assert props is not None
    assert props.formula == "C6H6"
    assert 77 < props.molecular_weight < 79
    assert props.heavy_atom_count == 6
    assert props.ring_count == 1


def test_compute_properties_ethanol() -> None:
    mol = read_smiles("CCO")
    props = compute_properties(mol)
    assert props is not None
    assert props.formula == "C2H6O"
    assert 45 < props.molecular_weight < 47
    assert props.hbd >= 1  # OH group is an HBD
    assert props.hba >= 1  # O is an HBA


def test_compute_properties_empty_molecule() -> None:
    props = compute_properties(Molecule())
    assert props is None


def test_compute_properties_tpsa_aspirin() -> None:
    mol = read_smiles("CC(=O)Oc1ccccc1C(=O)O")
    props = compute_properties(mol)
    assert props is not None
    # Aspirin TPSA ~63.6
    assert 60 < props.tpsa < 70
    assert props.rotatable_bonds >= 2
