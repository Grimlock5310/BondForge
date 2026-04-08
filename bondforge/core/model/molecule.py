"""Molecule — collection of atoms and bonds with stable identifiers.

This is the authoritative display-side representation. The chemistry engine
(``bondforge.engine.rdkit_adapter``) converts to and from RDKit ``RWMol``
on demand for sanitization, stereo perception, property calculation, and
file IO that benefits from RDKit's parsers.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from bondforge.core.model.atom import Atom
from bondforge.core.model.bond import Bond, BondOrder, BondStereo


@dataclass
class Molecule:
    """A collection of atoms and bonds with stable IDs.

    The molecule owns the ID counters; callers should always use
    :meth:`add_atom` and :meth:`add_bond` rather than constructing
    atoms and bonds directly, so that IDs remain unique.
    """

    atoms: dict[int, Atom] = field(default_factory=dict)
    bonds: dict[int, Bond] = field(default_factory=dict)
    _next_atom_id: int = 1
    _next_bond_id: int = 1

    # ----- atoms ---------------------------------------------------------

    def add_atom(
        self,
        element: str,
        x: float = 0.0,
        y: float = 0.0,
        *,
        charge: int = 0,
        isotope: int = 0,
    ) -> Atom:
        """Create and register a new atom, returning the live instance."""
        atom = Atom(
            id=self._next_atom_id,
            element=element,
            x=x,
            y=y,
            charge=charge,
            isotope=isotope,
        )
        self.atoms[atom.id] = atom
        self._next_atom_id += 1
        return atom

    def remove_atom(self, atom_id: int) -> None:
        """Remove an atom and any bonds incident to it."""
        if atom_id not in self.atoms:
            raise KeyError(f"Atom {atom_id} not found")
        incident = [
            b.id for b in self.bonds.values() if atom_id in (b.begin_atom_id, b.end_atom_id)
        ]
        for bid in incident:
            del self.bonds[bid]
        del self.atoms[atom_id]

    # ----- bonds ---------------------------------------------------------

    def add_bond(
        self,
        begin_atom_id: int,
        end_atom_id: int,
        order: BondOrder = BondOrder.SINGLE,
        stereo: BondStereo = BondStereo.NONE,
    ) -> Bond:
        """Create and register a new bond between two existing atoms."""
        if begin_atom_id not in self.atoms:
            raise KeyError(f"Begin atom {begin_atom_id} not found")
        if end_atom_id not in self.atoms:
            raise KeyError(f"End atom {end_atom_id} not found")
        if begin_atom_id == end_atom_id:
            raise ValueError("Self-bonds are not allowed")
        bond = Bond(
            id=self._next_bond_id,
            begin_atom_id=begin_atom_id,
            end_atom_id=end_atom_id,
            order=order,
            stereo=stereo,
        )
        self.bonds[bond.id] = bond
        self._next_bond_id += 1
        return bond

    def remove_bond(self, bond_id: int) -> None:
        if bond_id not in self.bonds:
            raise KeyError(f"Bond {bond_id} not found")
        del self.bonds[bond_id]

    def bonds_for_atom(self, atom_id: int) -> Iterator[Bond]:
        for bond in self.bonds.values():
            if atom_id in (bond.begin_atom_id, bond.end_atom_id):
                yield bond

    # ----- iteration helpers --------------------------------------------

    def iter_atoms(self) -> Iterable[Atom]:
        return self.atoms.values()

    def iter_bonds(self) -> Iterable[Bond]:
        return self.bonds.values()

    def __len__(self) -> int:
        return len(self.atoms)
