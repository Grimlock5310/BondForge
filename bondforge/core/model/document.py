"""Document — top-level container for a drawing.

A :class:`Document` owns exactly one :class:`Molecule` (which may have
disjoint connected components — a reaction scheme draws A + B → C by
laying out three components in the same molecule), a list of
:class:`Arrow` instances, a list of :class:`TextAnnotation` objects,
and a dict of :class:`Biopolymer` instances.

Older v0.2 code talks to ``scene.molecule`` directly; ``Document`` is
designed to slot under that without breaking existing call sites. The
scene exposes both ``molecule`` (the bare connectivity) and ``document``
(the full drawing including arrows and text annotations).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from bondforge.core.model.arrow import Arrow, ArrowKind
from bondforge.core.model.biopolymer import Biopolymer
from bondforge.core.model.molecule import Molecule
from bondforge.core.model.text_annotation import TextAnnotation


@dataclass
class Document:
    """A drawing: one molecule + arrows + text annotations + biopolymers."""

    molecule: Molecule = field(default_factory=Molecule)
    arrows: dict[int, Arrow] = field(default_factory=dict)
    texts: dict[int, TextAnnotation] = field(default_factory=dict)
    biopolymers: dict[int, Biopolymer] = field(default_factory=dict)
    _next_arrow_id: int = 1
    _next_text_id: int = 1
    _next_biopolymer_id: int = 1

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

    def add_text(
        self,
        text: str,
        x: float,
        y: float,
        *,
        font_family: str = "Arial",
        font_size: float = 12.0,
        bold: bool = False,
        italic: bool = False,
    ) -> TextAnnotation:
        """Create and register a new text annotation."""
        ann = TextAnnotation(
            id=self._next_text_id,
            text=text,
            x=x,
            y=y,
            font_family=font_family,
            font_size=font_size,
            bold=bold,
            italic=italic,
        )
        self.texts[ann.id] = ann
        self._next_text_id += 1
        return ann

    def remove_text(self, text_id: int) -> None:
        if text_id not in self.texts:
            raise KeyError(f"TextAnnotation {text_id} not found")
        del self.texts[text_id]

    def iter_texts(self) -> Iterable[TextAnnotation]:
        return self.texts.values()

    # ----- biopolymers ---------------------------------------------------

    def add_biopolymer(self, biopolymer: Biopolymer) -> Biopolymer:
        """Register a biopolymer, assigning it a document-unique ID."""
        biopolymer.id = self._next_biopolymer_id
        self.biopolymers[biopolymer.id] = biopolymer
        self._next_biopolymer_id += 1
        return biopolymer

    def remove_biopolymer(self, bp_id: int) -> None:
        if bp_id not in self.biopolymers:
            raise KeyError(f"Biopolymer {bp_id} not found")
        del self.biopolymers[bp_id]

    def iter_biopolymers(self) -> Iterable[Biopolymer]:
        return self.biopolymers.values()


__all__ = ["Document"]
