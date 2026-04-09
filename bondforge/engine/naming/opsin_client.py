"""OPSIN client: IUPAC / trivial chemical name → structure.

OPSIN is a Java library maintained at the University of Cambridge that
parses chemical names and produces SMILES or MOL output. In v0.3 we
talk to it through `py2opsin`_, a PyPI wrapper that ships a bundled JAR
and a ``subprocess`` caller. ``py2opsin`` is listed as an *optional*
dependency in ``pyproject.toml`` so BondForge still installs and runs
without Java / without the name → structure feature.

The functions below degrade gracefully:

- :func:`is_opsin_available` returns ``False`` when ``py2opsin`` is not
  importable (or fails to find ``java`` at runtime).
- :func:`name_to_smiles` and :func:`name_to_molecule` raise
  :class:`OpsinUnavailable` when the backend is missing, or
  :class:`OpsinError` when the backend ran but couldn't parse the name.

A later release will swap ``py2opsin``'s per-call subprocess for a
persistent JSON-RPC sidecar owned by :mod:`bondforge.sidecars.java_host`.
For v0.3, ``py2opsin`` is simpler and it's what the plan calls for.

.. _py2opsin: https://pypi.org/project/py2opsin/
"""

from __future__ import annotations

from bondforge.core.io.smiles import read_smiles
from bondforge.core.model.molecule import Molecule


class OpsinError(RuntimeError):
    """OPSIN ran but could not translate the input name to a structure."""


class OpsinUnavailable(RuntimeError):
    """OPSIN is not installed / not reachable in this environment."""


def is_opsin_available() -> bool:
    """Return ``True`` when the ``py2opsin`` backend can be imported."""
    try:
        import py2opsin  # noqa: F401
    except Exception:
        return False
    return True


def name_to_smiles(name: str) -> str:
    """Translate a chemical name to a SMILES string via OPSIN.

    Raises:
        OpsinUnavailable: ``py2opsin`` is not installed or not callable.
        OpsinError: OPSIN ran but could not parse the name.
    """
    if not name or not name.strip():
        raise OpsinError("Empty name")
    try:
        from py2opsin import py2opsin
    except Exception as exc:
        raise OpsinUnavailable(
            "OPSIN backend not available — install the 'opsin' extra "
            "(pip install bondforge[opsin]) to enable Name → Structure."
        ) from exc

    smiles = py2opsin(name.strip(), output_format="SMILES")
    if not smiles:
        raise OpsinError(f"OPSIN could not parse the name: {name!r}")
    # py2opsin returns a bare string on success; some versions return
    # a list when given a multi-line input. Normalize to the first hit.
    if isinstance(smiles, list):
        smiles = smiles[0] if smiles else ""
        if not smiles:
            raise OpsinError(f"OPSIN could not parse the name: {name!r}")
    return smiles


def name_to_molecule(name: str) -> Molecule:
    """Translate a chemical name to a BondForge :class:`Molecule`.

    The result carries RDKit-generated 2D coordinates, ready to be
    dropped on the canvas.
    """
    smiles = name_to_smiles(name)
    return read_smiles(smiles)


__all__ = [
    "OpsinError",
    "OpsinUnavailable",
    "is_opsin_available",
    "name_to_smiles",
    "name_to_molecule",
]
