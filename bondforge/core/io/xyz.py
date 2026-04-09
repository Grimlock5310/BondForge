"""XYZ coordinate file reader and writer.

The XYZ format is a simple text format for 3D molecular coordinates::

    <atom_count>
    <comment line>
    <element> <x> <y> <z>
    ...

Reading an XYZ file produces a BondForge :class:`Molecule` with 3D
positions stored in the atom's ``x``/``y`` fields (``z`` is stored in
``atom.properties["z"]``). Connectivity is *not* inferred — XYZ files
carry no bond information.

Writing an XYZ file requires an RDKit ``Mol`` with a 3D conformer (as
produced by :func:`bondforge.engine.conformer.generate_conformer`).
"""

from __future__ import annotations

from pathlib import Path

from rdkit import Chem

from bondforge.core.model.molecule import Molecule


def read_xyz(text: str) -> Molecule:
    """Parse an XYZ string into a :class:`Molecule`.

    Only atom positions are imported; bonds are not inferred.
    """
    lines = text.strip().splitlines()
    if len(lines) < 3:
        raise ValueError("XYZ file too short: expected at least 3 lines")
    try:
        atom_count = int(lines[0].strip())
    except ValueError as exc:
        raise ValueError(f"Invalid atom count on line 1: {lines[0]!r}") from exc
    mol = Molecule()
    for i in range(atom_count):
        line_idx = i + 2
        if line_idx >= len(lines):
            raise ValueError(f"XYZ file truncated: expected {atom_count} atoms")
        parts = lines[line_idx].split()
        if len(parts) < 4:
            raise ValueError(f"Invalid XYZ line {line_idx + 1}: {lines[line_idx]!r}")
        element = parts[0]
        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
        atom = mol.add_atom(element, x, y)
        atom.properties["z"] = str(z)
    return mol


def read_xyz_file(path: str | Path) -> Molecule:
    """Read a ``.xyz`` file from disk."""
    return read_xyz(Path(path).read_text(encoding="utf-8"))


def write_xyz(mol: Chem.Mol, *, conf_id: int = 0, comment: str = "") -> str:
    """Serialize an RDKit ``Mol`` with 3D coordinates to an XYZ string.

    Parameters:
        mol: RDKit Mol with at least one conformer.
        conf_id: Which conformer to write.
        comment: Optional comment for the second line.
    """
    conf = mol.GetConformer(conf_id)
    lines: list[str] = [str(mol.GetNumAtoms()), comment]
    for atom in mol.GetAtoms():
        pos = conf.GetAtomPosition(atom.GetIdx())
        lines.append(f"{atom.GetSymbol():>2s}  {pos.x:12.6f}  {pos.y:12.6f}  {pos.z:12.6f}")
    return "\n".join(lines) + "\n"


def write_xyz_file(
    mol: Chem.Mol,
    path: str | Path,
    *,
    conf_id: int = 0,
    comment: str = "",
) -> None:
    """Write an RDKit ``Mol`` to a ``.xyz`` file."""
    Path(path).write_text(write_xyz(mol, conf_id=conf_id, comment=comment), encoding="utf-8")


__all__ = ["read_xyz", "read_xyz_file", "write_xyz", "write_xyz_file"]
