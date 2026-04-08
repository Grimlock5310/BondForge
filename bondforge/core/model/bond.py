"""Bond — display-side representation of a chemical bond between two atoms."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BondOrder(Enum):
    """Bond order, including the chemistry-specific ``AROMATIC`` and ``ANY``."""

    SINGLE = 1
    DOUBLE = 2
    TRIPLE = 3
    AROMATIC = 4
    DATIVE = 5
    ANY = 6


class BondStereo(Enum):
    """Stereochemical depiction of a bond.

    Wedge directions follow the IUPAC convention as drawn from
    ``begin_atom_id`` toward ``end_atom_id``.
    """

    NONE = 0
    WEDGE_UP = 1
    WEDGE_DOWN = 2
    EITHER = 3
    CIS = 4
    TRANS = 5


@dataclass
class Bond:
    """A chemical bond between two atoms in a molecule.

    Attributes:
        id: Stable integer identifier, unique within a :class:`Molecule`.
        begin_atom_id: ID of the start atom (wedge "narrow" end).
        end_atom_id: ID of the end atom.
        order: Multiplicity / aromaticity.
        stereo: Stereochemical depiction (wedge / hash / cis-trans / none).
    """

    id: int
    begin_atom_id: int
    end_atom_id: int
    order: BondOrder = BondOrder.SINGLE
    stereo: BondStereo = BondStereo.NONE

    def other_atom_id(self, atom_id: int) -> int:
        """Return the atom on the opposite end of this bond from ``atom_id``."""
        if atom_id == self.begin_atom_id:
            return self.end_atom_id
        if atom_id == self.end_atom_id:
            return self.begin_atom_id
        raise ValueError(f"Atom {atom_id} is not part of bond {self.id}")
