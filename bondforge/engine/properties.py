"""Molecular property calculations via RDKit.

Provides a :class:`MolecularProperties` dataclass that bundles the most
commonly needed descriptors (molecular weight, formula, logP, TPSA, HBD,
HBA, rotatable bonds, heavy atom count) and a :func:`compute_properties`
factory that builds one from a BondForge :class:`Molecule`.

All properties are computed from a sanitized RDKit ``Mol``. If
sanitization fails (e.g. on a partial drawing), the function returns
``None`` rather than crashing — the UI should show "—" in that case.
"""

from __future__ import annotations

from dataclasses import dataclass

from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors

from bondforge.core.model.molecule import Molecule
from bondforge.engine.rdkit_adapter import molecule_to_rwmol


@dataclass(frozen=True)
class MolecularProperties:
    """Read-only bag of computed molecular descriptors."""

    molecular_weight: float
    exact_mass: float
    formula: str
    logp: float
    tpsa: float
    hbd: int  # hydrogen-bond donors
    hba: int  # hydrogen-bond acceptors
    rotatable_bonds: int
    heavy_atom_count: int
    ring_count: int


def compute_properties(mol: Molecule) -> MolecularProperties | None:
    """Compute molecular properties for a BondForge :class:`Molecule`.

    Returns ``None`` when the molecule is empty or cannot be sanitized
    (e.g. a partial drawing with valence errors).
    """
    if not mol.atoms:
        return None
    rw = molecule_to_rwmol(mol)
    try:
        Chem.SanitizeMol(rw)
    except Exception:
        return None
    rd_mol = rw.GetMol()
    return MolecularProperties(
        molecular_weight=round(Descriptors.MolWt(rd_mol), 4),
        exact_mass=round(Descriptors.ExactMolWt(rd_mol), 4),
        formula=rdMolDescriptors.CalcMolFormula(rd_mol),
        logp=round(Descriptors.MolLogP(rd_mol), 4),
        tpsa=round(Descriptors.TPSA(rd_mol), 4),
        hbd=Descriptors.NumHDonors(rd_mol),
        hba=Descriptors.NumHAcceptors(rd_mol),
        rotatable_bonds=Descriptors.NumRotatableBonds(rd_mol),
        heavy_atom_count=rd_mol.GetNumHeavyAtoms(),
        ring_count=Descriptors.RingCount(rd_mol),
    )


__all__ = ["MolecularProperties", "compute_properties"]
