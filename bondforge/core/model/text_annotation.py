"""TextAnnotation — free-form rich text placed on the canvas.

Used for reagent labels above arrows, figure captions, compound
identifiers, and any other text the user wants to annotate their
drawing with. Each annotation carries its own font family, size,
bold/italic flags, and an (x, y) scene-space position.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TextAnnotation:
    """A positioned text label on the canvas.

    Attributes:
        id: Stable integer identifier, unique within a :class:`Document`.
        text: The annotation content (plain text or basic HTML subset).
        x: Scene-space x coordinate (top-left of the text box).
        y: Scene-space y coordinate.
        font_family: Font family name (e.g. ``"Arial"``).
        font_size: Font point size.
        bold: Whether the text is bold.
        italic: Whether the text is italic.
    """

    id: int
    text: str
    x: float
    y: float
    font_family: str = "Arial"
    font_size: float = 12.0
    bold: bool = False
    italic: bool = False


__all__ = ["TextAnnotation"]
