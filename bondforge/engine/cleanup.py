"""Whole-molecule 2D coordinate clean-up via RDKit.

ChemDraw's "Clean Up Structure" command rebuilds the 2D drawing so bond
lengths are uniform, angles are sensible, and rings are regular. We
implement the same idea by handing the molecule to RDKit's
``Compute2DCoords``, then scaling the result so bond lengths match the
canvas's :data:`DEFAULT_BOND_LENGTH`, then re-centering the layout on the
old centroid so the user doesn't see the structure jump across the page.
"""

from __future__ import annotations

from rdkit import Chem
from rdkit.Chem import AllChem

from bondforge.canvas.geometry import DEFAULT_BOND_LENGTH
from bondforge.core.model.molecule import Molecule
from bondforge.engine.rdkit_adapter import molecule_to_rwmol

# RDKit's Compute2DCoords places bonds at length 1.5 in its native units;
# scale that to our canvas default. Computed lazily because the constant
# may change in future RDKit versions.
_RDKIT_BOND_LENGTH = 1.5


def compute_clean_2d_coords(mol: Molecule) -> None:
    """Mutate ``mol`` in place, replacing atom positions with cleaned ones.

    Bond lengths after this call are exactly :data:`DEFAULT_BOND_LENGTH`,
    angles match RDKit's preferred drawing for the connectivity, and the
    centroid of the new layout is the centroid of the old layout (so the
    user perceives clean-up as "tidying up around where I was working").
    """
    if not mol.atoms:
        return

    rw = molecule_to_rwmol(mol)
    Chem.SanitizeMol(rw)
    AllChem.Compute2DCoords(rw)
    conf = rw.GetConformer(0)

    scale = DEFAULT_BOND_LENGTH / _RDKIT_BOND_LENGTH

    old_cx = sum(a.x for a in mol.iter_atoms()) / len(mol.atoms)
    old_cy = sum(a.y for a in mol.iter_atoms()) / len(mol.atoms)

    new_positions: list[tuple[float, float]] = []
    for i in range(rw.GetNumAtoms()):
        pos = conf.GetAtomPosition(i)
        new_positions.append((pos.x * scale, -pos.y * scale))  # flip Y to scene
    new_cx = sum(p[0] for p in new_positions) / len(new_positions)
    new_cy = sum(p[1] for p in new_positions) / len(new_positions)

    # iter_atoms() preserves insertion order, which matches the order in
    # which molecule_to_rwmol added the corresponding RDKit atoms.
    for atom, (nx, ny) in zip(mol.iter_atoms(), new_positions, strict=True):
        atom.x = nx - new_cx + old_cx
        atom.y = ny - new_cy + old_cy


__all__ = ["compute_clean_2d_coords"]
