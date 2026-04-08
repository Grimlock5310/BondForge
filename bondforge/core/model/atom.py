"""Atom — display-side representation of a single atom in a molecule.

The display model is authoritative for everything the user can see and
interact with. RDKit ``RWMol`` objects are built lazily by the engine layer
and discarded; they are never the source of truth for cosmetic or layout
information.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Atom:
    """A single atom on the canvas.

    Attributes:
        id: Stable integer identifier, unique within a :class:`Molecule`.
        element: IUPAC element symbol (e.g. ``"C"``, ``"N"``, ``"Fe"``).
        x: Scene-space x coordinate (Qt graphics coordinates).
        y: Scene-space y coordinate (Qt graphics coordinates).
        charge: Formal charge.
        isotope: Mass number; ``0`` means natural abundance.
        radical_electrons: Number of unpaired electrons.
        explicit_hydrogens: User-fixed hydrogen count; ``None`` means infer.
        map_number: Atom-atom mapping number used in reactions; ``0`` if unset.
        label: Optional display label override (e.g. ``"R1"``, ``"OMe"``).
        is_query: True if this atom is a query/wildcard atom.
    """

    id: int
    element: str
    x: float = 0.0
    y: float = 0.0
    charge: int = 0
    isotope: int = 0
    radical_electrons: int = 0
    explicit_hydrogens: int | None = None
    map_number: int = 0
    label: str | None = None
    is_query: bool = False
    properties: dict[str, str] = field(default_factory=dict)

    def display_label(self) -> str:
        """Return the label that should be drawn on the canvas."""
        if self.label is not None:
            return self.label
        return self.element
