"""MDL Molfile (V2000/V3000) reader and writer.

Wraps RDKit's MOL parsers and converts to and from the BondForge display
model. We deliberately do *not* expose RDKit ``Mol`` objects across this
boundary — callers should only ever see :class:`Molecule`.
"""

from __future__ import annotations

from pathlib import Path

from rdkit import Chem

from bondforge.core.model.molecule import Molecule
from bondforge.engine.rdkit_adapter import molecule_to_rwmol, rwmol_to_molecule


def read_mol(text: str) -> Molecule:
    """Parse a MOL block (V2000 or V3000) into a :class:`Molecule`."""
    rw = Chem.MolFromMolBlock(text, sanitize=True, removeHs=False)
    if rw is None:
        raise ValueError("Failed to parse MOL block")
    return rwmol_to_molecule(rw)


def read_mol_file(path: str | Path) -> Molecule:
    """Read a ``.mol`` file from disk."""
    return read_mol(Path(path).read_text(encoding="utf-8"))


def write_mol(mol: Molecule, *, v3000: bool = False) -> str:
    """Serialize a :class:`Molecule` to a MOL block."""
    rw = molecule_to_rwmol(mol)
    Chem.SanitizeMol(rw)
    return Chem.MolToMolBlock(rw, forceV3000=v3000)


def write_mol_file(mol: Molecule, path: str | Path, *, v3000: bool = False) -> None:
    """Write a :class:`Molecule` to a ``.mol`` file."""
    Path(path).write_text(write_mol(mol, v3000=v3000), encoding="utf-8")
