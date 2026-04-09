"""Force-field minimization via RDKit (MMFF94 with UFF fallback).

:func:`minimize` takes an RDKit ``Mol`` that already carries a 3D
conformer (from :func:`bondforge.engine.conformer.generate_conformer`)
and energy-minimizes it in place. MMFF94 is preferred; if MMFF setup
fails (missing parameters for exotic atoms/fragments), UFF is used as
a fallback.

The function returns the final energy and whether it converged within
the iteration limit. The caller can use ``not converged`` to show a
warning, but the structure is still usable either way.
"""

from __future__ import annotations

from dataclasses import dataclass

from rdkit.Chem import AllChem, rdForceFieldHelpers


class MinimizationError(RuntimeError):
    """Force-field setup or minimization failed entirely."""


@dataclass(frozen=True)
class MinimizationResult:
    """Outcome of a force-field minimization run."""

    energy: float
    converged: bool
    force_field: str  # "MMFF94" or "UFF"


def minimize(
    mol,
    *,
    conf_id: int = 0,
    max_iters: int = 500,
) -> MinimizationResult:
    """Minimize the given conformer in place.

    Parameters:
        mol: An RDKit ``Mol`` with at least one 3D conformer.
        conf_id: Which conformer to minimize (default: first).
        max_iters: Maximum optimization iterations.

    Returns:
        A :class:`MinimizationResult` with final energy, convergence flag,
        and the force field that was used.

    Raises:
        MinimizationError: neither MMFF94 nor UFF could be set up.
    """
    # Try MMFF94 first.
    if rdForceFieldHelpers.MMFFHasAllMoleculeParams(mol):
        props = AllChem.MMFFGetMoleculeProperties(mol)
        ff = AllChem.MMFFGetMoleculeForceField(mol, props, confId=conf_id)
        if ff is not None:
            converged = ff.Minimize(maxIts=max_iters)
            return MinimizationResult(
                energy=ff.CalcEnergy(),
                converged=converged == 0,
                force_field="MMFF94",
            )

    # Fallback to UFF.
    ff = AllChem.UFFGetMoleculeForceField(mol, confId=conf_id)
    if ff is None:
        raise MinimizationError(
            "Neither MMFF94 nor UFF force fields could be set up for this molecule."
        )
    converged = ff.Minimize(maxIts=max_iters)
    return MinimizationResult(
        energy=ff.CalcEnergy(),
        converged=converged == 0,
        force_field="UFF",
    )


__all__ = ["MinimizationError", "MinimizationResult", "minimize"]
