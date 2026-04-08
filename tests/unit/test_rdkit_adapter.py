"""Round-trip tests between the display Molecule and RDKit ROMol."""

from __future__ import annotations

import pytest

rdkit = pytest.importorskip("rdkit")
from rdkit import Chem  # noqa: E402

from bondforge.core.model.bond import BondOrder, BondStereo  # noqa: E402
from bondforge.core.model.molecule import Molecule  # noqa: E402
from bondforge.engine.rdkit_adapter import (  # noqa: E402
    molecule_to_rwmol,
    rwmol_to_molecule,
    sanitized,
)


def _build_ethanol() -> Molecule:
    mol = Molecule()
    c1 = mol.add_atom("C", 0, 0)
    c2 = mol.add_atom("C", 50, 0)
    o = mol.add_atom("O", 100, 0)
    mol.add_bond(c1.id, c2.id, BondOrder.SINGLE)
    mol.add_bond(c2.id, o.id, BondOrder.SINGLE)
    return mol


def test_molecule_to_rwmol_preserves_atom_count() -> None:
    mol = _build_ethanol()
    rw = molecule_to_rwmol(mol)
    assert rw.GetNumAtoms() == 3
    assert rw.GetNumBonds() == 2


def test_sanitized_smiles_for_ethanol() -> None:
    mol = _build_ethanol()
    rw = sanitized(mol)
    smiles = Chem.MolToSmiles(rw)
    assert smiles == "CCO"


def test_round_trip_from_smiles() -> None:
    rw = Chem.MolFromSmiles("c1ccccc1")
    bf_mol = rwmol_to_molecule(rw)
    assert len(bf_mol.atoms) == 6
    assert len(bf_mol.bonds) == 6
    rw2 = sanitized(bf_mol)
    assert Chem.MolToSmiles(rw2) == "c1ccccc1"


def test_charge_round_trip() -> None:
    mol = Molecule()
    n = mol.add_atom("N", 0, 0, charge=1)
    h1 = mol.add_atom("H", 10, 0)
    h2 = mol.add_atom("H", -10, 0)
    h3 = mol.add_atom("H", 0, 10)
    h4 = mol.add_atom("H", 0, -10)
    for h in (h1, h2, h3, h4):
        mol.add_bond(n.id, h.id, BondOrder.SINGLE)
    rw = sanitized(mol)
    collapsed = Chem.RemoveHs(rw)
    assert Chem.MolToSmiles(collapsed) == "[NH4+]"


def test_wedge_bond_preserved() -> None:
    mol = Molecule()
    a = mol.add_atom("C", 0, 0)
    b = mol.add_atom("F", 50, 0)
    mol.add_bond(a.id, b.id, BondOrder.SINGLE, BondStereo.WEDGE_UP)
    rw = molecule_to_rwmol(mol)
    bond = rw.GetBondWithIdx(0)
    assert bond.GetBondDir() == Chem.BondDir.BEGINWEDGE
