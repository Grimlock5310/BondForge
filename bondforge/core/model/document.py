"""Document — top-level container for a drawing.

A :class:`Document` owns exactly one :class:`Molecule` (which may have
disjoint connected components — a reaction scheme draws A + B → C by
laying out three components in the same molecule) plus a list of
:class:`Arrow` instances for reaction and electron-pushing arrows.

Older v0.2 code talks to ``scene.molecule`` directly; ``Document`` is
designed to slot under that without breaking existing call sites. The
scene exposes both ``molecule`` (the bare connectivity) and ``document``
(the full drawing including arrows).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from bondforge.core.model.arrow import Arrow, ArrowKind
from bondforge.core.model.molecule import Molecule


@dataclass
class Document:
    """A drawing: one molecule + a list of arrows."""

    molecule: Molecule = field(default_factory=Molecule)
    arrows: dict[int, Arrow] = field(default_factory=dict)
    _next_arrow_id: int = 1

    def add_arrow(
        self,
        kind: ArrowKind,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        curvature: float = 0.0,
        label: str = "",
    ) -> Arrow:
        """Create and register a new arrow, returning the live instance."""
        arrow = Arrow(
            id=self._next_arrow_id,
            kind=kind,
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            curvature=curvature,
            label=label,
        )
        self.arrows[arrow.id] = arrow
        self._next_arrow_id += 1
        return arrow

    def remove_arrow(self, arrow_id: int) -> None:
        if arrow_id not in self.arrows:
            raise KeyError(f"Arrow {arrow_id} not found")
        del self.arrows[arrow_id]

    def iter_arrows(self) -> Iterable[Arrow]:
        return self.arrows.values()


__all__ = ["Document"]
