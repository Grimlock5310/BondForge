"""Whole-molecule 2D coordinate clean-up via RDKit.

ChemDraw's "Clean Up Structure" command rebuilds the 2D drawing so bond
lengths are uniform, angles are sensible, and rings are regular. We
implement the same idea by handing the molecule to RDKit's
``Compute2DCoords``, then scaling the result so bond lengths match the
canvas's :data:`DEFAULT_BOND_LENGTH`, then re-centering the layout on the
old centroid so the user doesn't see the structure jump across the page.

Clean-up must never crash on a partially-drawn molecule — users routinely
trigger it mid-edit with dangling bonds, radicals, or hypervalent atoms
that a strict ``Chem.SanitizeMol`` would reject. We sanitize with
property/valence checks disabled and ignore any residual exception so
``Compute2DCoords`` always gets to run.
"""

from __future__ import annotations

import contextlib

from rdkit import Chem
from rdkit.Chem import AllChem

from bondforge.canvas.geometry import DEFAULT_BOND_LENGTH
from bondforge.core.model.molecule import Molecule
from bondforge.engine.rdkit_adapter import molecule_to_rwmol

# RDKit's Compute2DCoords places bonds at length 1.5 in its native units;
# scale that to our canvas default. Computed lazily because the constant
# may change in future RDKit versions.
_RDKIT_BOND_LENGTH = 1.5

# Sanitize flags that skip valence / property checks. Those are the ones
# that blow up on drawings in progress (e.g. a nitrogen with five bonds
# while the user is still deciding what they want).
_CLEANUP_SANITIZE_OPS = (
    Chem.SANITIZE_ALL ^ Chem.SANITIZE_PROPERTIES ^ Chem.SANITIZE_CLEANUPCHIRALITY
)


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
    # Even the loosened sanitization can raise (e.g. on kekulization
    # failures for an in-progress aromatic ring). Swallow it — the 2D
    # layout engine doesn't need a sanitized mol to run.
    with contextlib.suppress(Exception):
        Chem.SanitizeMol(rw, sanitizeOps=_CLEANUP_SANITIZE_OPS)
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
