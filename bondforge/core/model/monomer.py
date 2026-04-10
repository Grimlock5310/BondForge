"""Monomer — building block for biopolymers (peptides, DNA, RNA).

Each :class:`Monomer` represents a single residue in a polymer chain.
The monomer library provides a catalog of standard amino acids and
nucleotides with their SMILES, abbreviations, and natural analog codes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PolymerType(Enum):
    """The type of biopolymer a monomer belongs to."""

    PEPTIDE = "PEPTIDE"
    RNA = "RNA"
    DNA = "DNA"
    CHEM = "CHEM"  # non-natural chemical modifier


@dataclass(frozen=True)
class MonomerDef:
    """Definition of a monomer in the library.

    This is a *type-level* object (one per distinct monomer kind).
    Instances on a chain use :class:`MonomerResidue`.

    Attributes:
        symbol: Short abbreviation (e.g. ``"A"`` for alanine, ``"dA"`` for
            deoxyadenosine).
        name: Full IUPAC or common name.
        polymer_type: Which biopolymer family this belongs to.
        smiles: Canonical SMILES for the monomer with attachment points
            marked by ``[*:1]`` (backbone left) and ``[*:2]`` (backbone right).
        natural_analog: Single-letter code of the natural analog, or the
            symbol itself for natural monomers.
    """

    symbol: str
    name: str
    polymer_type: PolymerType
    smiles: str
    natural_analog: str


@dataclass
class MonomerResidue:
    """A single residue placed in a :class:`PolymerChain`.

    Attributes:
        position: 1-based index in the chain.
        symbol: Monomer abbreviation (key into the monomer library).
        polymer_type: Inherited from the chain.
        x: Scene-space x coordinate for rendering.
        y: Scene-space y coordinate.
    """

    position: int
    symbol: str
    polymer_type: PolymerType
    x: float = 0.0
    y: float = 0.0


__all__ = ["PolymerType", "MonomerDef", "MonomerResidue"]
