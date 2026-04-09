"""3D conformer generation via RDKit's ETKDG embedding.

:func:`generate_conformer` builds a single 3D conformer (or
``num_conformers`` conformers) from a BondForge :class:`Molecule` using
RDKit's ETKDGv3 algorithm. The returned ``Chem.Mol`` carries the 3D
coordinates as a conformer and can be fed to the 3D viewer, written to
XYZ/PDB, or handed to :func:`bondforge.engine.forcefield.minimize`.

Raises :class:`ConformerError` when RDKit cannot embed (e.g. the molecule
has valence errors that prevent sanitization, or the embedding simply
fails — this is rare but can happen for strained systems).
"""

from __future__ import annotations

from rdkit import Chem
from rdkit.Chem import AllChem

from bondforge.core.model.molecule import Molecule
from bondforge.engine.rdkit_adapter import molecule_to_rwmol


class ConformerError(RuntimeError):
    """RDKit could not embed the molecule."""


def generate_conformer(
    mol: Molecule,
    *,
    num_conformers: int = 1,
    random_seed: int = 42,
) -> Chem.Mol:
    """Return an RDKit ``Mol`` with 3D coordinates.

    Parameters:
        mol: The BondForge molecule to embed.
        num_conformers: How many conformers to generate. The returned
            mol carries all of them; caller can enumerate via
            ``mol.GetConformers()``.
        random_seed: Seed for reproducibility; ``-1`` for random.

    Raises:
        ConformerError: sanitization or embedding failed.
    """
    if not mol.atoms:
        raise ConformerError("Cannot embed an empty molecule.")
    rw = molecule_to_rwmol(mol)
    try:
        Chem.SanitizeMol(rw)
    except Exception as exc:
        raise ConformerError(f"Sanitization failed: {exc}") from exc

    rw = Chem.AddHs(rw)
    params = AllChem.ETKDGv3()
    params.randomSeed = random_seed
    conf_ids = AllChem.EmbedMultipleConfs(rw, numConfs=num_conformers, params=params)
    if not conf_ids:
        raise ConformerError(
            "RDKit ETKDG embedding failed. The molecule may be too strained "
            "or missing valence information."
        )
    return rw


__all__ = ["ConformerError", "generate_conformer"]
