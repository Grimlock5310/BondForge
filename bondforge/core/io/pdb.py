"""PDB coordinate file reader and writer.

Uses RDKit's PDB support for both reading and writing. Reading produces
a BondForge :class:`Molecule` with 3D positions. Writing requires an
RDKit ``Mol`` with a 3D conformer.
"""

from __future__ import annotations

from pathlib import Path

from rdkit import Chem

from bondforge.core.model.molecule import Molecule
from bondforge.engine.rdkit_adapter import rwmol_to_molecule


def read_pdb(text: str) -> Molecule:
    """Parse a PDB string into a :class:`Molecule`."""
    rw = Chem.MolFromPDBBlock(text, sanitize=False, removeHs=False)
    if rw is None:
        raise ValueError("Failed to parse PDB block")
    return rwmol_to_molecule(rw)


def read_pdb_file(path: str | Path) -> Molecule:
    """Read a ``.pdb`` file from disk."""
    return read_pdb(Path(path).read_text(encoding="utf-8"))


def write_pdb(mol: Chem.Mol, *, conf_id: int = 0) -> str:
    """Serialize an RDKit ``Mol`` with 3D coordinates to a PDB string."""
    return Chem.MolToPDBBlock(mol, confId=conf_id)


def write_pdb_file(mol: Chem.Mol, path: str | Path, *, conf_id: int = 0) -> None:
    """Write an RDKit ``Mol`` to a ``.pdb`` file."""
    Path(path).write_text(write_pdb(mol, conf_id=conf_id), encoding="utf-8")


__all__ = ["read_pdb", "read_pdb_file", "write_pdb", "write_pdb_file"]
