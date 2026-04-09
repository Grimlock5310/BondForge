"""Arrow — straight reaction and curved electron-pushing arrows.

v0.3 introduces two categories of arrow on the canvas:

- **Reaction arrows** (``FORWARD``, ``EQUILIBRIUM``, ``RETROSYNTHETIC``)
  are straight arrows drawn between reactants and products. They have a
  head at the tip and an optional text label for reagents/conditions.

- **Curved electron-pushing arrows** (``ELECTRON_PAIR``,
  ``SINGLE_ELECTRON``) depict the movement of electrons in a reaction
  mechanism. ``ELECTRON_PAIR`` is the full double-headed "harpoon"
  used for two-electron motion; ``SINGLE_ELECTRON`` is the half-head
  "fish hook" used for radical mechanisms. Both curve — the control
  offset parameter says how far off the chord midpoint the midpoint
  of the curve sits, and which side it curves toward.

The arrow model is intentionally free of molecule references at v0.3;
the user positions head and tail in free scene coordinates. v0.4 can
add "anchor to atom/bond/lone-pair" once the selection model supports
compound targets.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ArrowKind(Enum):
    """The five arrow flavors supported in v0.3."""

    FORWARD = 1
    EQUILIBRIUM = 2
    RETROSYNTHETIC = 3
    ELECTRON_PAIR = 4  # curved, double-headed (two-electron motion)
    SINGLE_ELECTRON = 5  # curved, fish-hook (radical, one-electron)

    @property
    def is_curved(self) -> bool:
        return self in (ArrowKind.ELECTRON_PAIR, ArrowKind.SINGLE_ELECTRON)

    @property
    def is_reaction(self) -> bool:
        return self in (
            ArrowKind.FORWARD,
            ArrowKind.EQUILIBRIUM,
            ArrowKind.RETROSYNTHETIC,
        )


@dataclass
class Arrow:
    """An arrow on the canvas, reaction or electron-pushing.

    Attributes:
        id: Stable integer identifier, unique within a :class:`Document`.
        kind: Which arrow flavor this is.
        x1, y1: Tail (start) point in scene coordinates.
        x2, y2: Head (end) point in scene coordinates.
        curvature: Signed perpendicular offset of the curve's midpoint
            from the chord midpoint, in scene units. Ignored for straight
            reaction arrows. Positive values curve the arrow toward the
            "left" of the tail→head direction (counter-clockwise in
            math-y-up; in Qt scene-y-down that's clockwise on screen).
        label: Optional reagent/conditions text rendered above reaction
            arrows. Unused for electron-pushing arrows.
    """

    id: int
    kind: ArrowKind
    x1: float
    y1: float
    x2: float
    y2: float
    curvature: float = 0.0
    label: str = ""


__all__ = ["Arrow", "ArrowKind"]
