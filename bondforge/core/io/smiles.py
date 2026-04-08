"""SMILES reader and writer."""

from __future__ import annotations

from rdkit import Chem

from bondforge.core.model.molecule import Molecule
from bondforge.engine.rdkit_adapter import molecule_to_rwmol, rwmol_to_molecule


def read_smiles(smiles: str) -> Molecule:
    """Parse a SMILES string into a :class:`Molecule`.

    Always emits 2D coordinates so the result is immediately renderable.
    """
    rw = Chem.MolFromSmiles(smiles)
    if rw is None:
        raise ValueError(f"Failed to parse SMILES: {smiles!r}")
    return rwmol_to_molecule(rw)


def write_smiles(mol: Molecule, *, canonical: bool = True) -> str:
    """Serialize a :class:`Molecule` to a SMILES string."""
    rw = molecule_to_rwmol(mol)
    Chem.SanitizeMol(rw)
    return Chem.MolToSmiles(rw, canonical=canonical)
