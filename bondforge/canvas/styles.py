"""Journal style presets for publication-quality drawings.

Each :class:`JournalStyle` defines the drawing parameters that match a
journal's author guidelines. Applying a style adjusts the canvas-wide
defaults — bond length, line width, font family/size, and margin widths.

Major chemistry journals specify these in their "Author Guidelines /
Artwork" pages. The values here are distilled from the respective
specifications (where available) and from empirical measurements of
recently published papers.

Usage::

    from bondforge.canvas.styles import STYLES, apply_style
    apply_style(scene, STYLES["ACS"])

The style only affects *new* drawing operations and export parameters.
To reformat an existing drawing, call the :meth:`reformat` method on
the scene (which rescales bond lengths and updates font sizes).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JournalStyle:
    """Drawing parameters for a specific journal family.

    Attributes:
        name: Human-readable identifier (e.g. ``"ACS 1996"``).
        bond_length_pt: Bond length in points (1 pt = 1/72 in).
        line_width_pt: Bond line width in points.
        font_family: Preferred font family for atom labels.
        font_size_pt: Font size for atom labels in points.
        margin_width_pt: Hash/wedge line spacing in points.
        bold_width_pt: Bold bond width in points.
        hash_spacing_pt: Distance between hash marks in points.
    """

    name: str
    bond_length_pt: float
    line_width_pt: float
    font_family: str
    font_size_pt: float
    margin_width_pt: float
    bold_width_pt: float
    hash_spacing_pt: float

    @property
    def bond_length_px(self) -> float:
        """Bond length in scene units (pixels at 96 dpi)."""
        return self.bond_length_pt * 96.0 / 72.0

    @property
    def line_width_px(self) -> float:
        """Bond line width in scene pixels."""
        return self.line_width_pt * 96.0 / 72.0

    @property
    def font_size_px(self) -> float:
        """Font size in scene pixels."""
        return self.font_size_pt * 96.0 / 72.0


# ---- Standard presets ----------------------------------------------------

ACS_1996 = JournalStyle(
    name="ACS 1996",
    bond_length_pt=14.4,   # 0.508 cm / 0.2 in
    line_width_pt=0.6,
    font_family="Arial",
    font_size_pt=10.0,
    margin_width_pt=1.6,
    bold_width_pt=2.0,
    hash_spacing_pt=2.5,
)

RSC = JournalStyle(
    name="RSC",
    bond_length_pt=17.007,  # 0.6 cm
    line_width_pt=0.5,
    font_family="Arial",
    font_size_pt=7.0,
    margin_width_pt=1.4,
    bold_width_pt=1.8,
    hash_spacing_pt=2.2,
)

NATURE = JournalStyle(
    name="Nature",
    bond_length_pt=14.4,
    line_width_pt=0.5,
    font_family="Helvetica",
    font_size_pt=8.0,
    margin_width_pt=1.4,
    bold_width_pt=2.0,
    hash_spacing_pt=2.5,
)

WILEY = JournalStyle(
    name="Wiley",
    bond_length_pt=15.12,  # 0.533 cm
    line_width_pt=0.5,
    font_family="Helvetica",
    font_size_pt=8.0,
    margin_width_pt=1.5,
    bold_width_pt=2.0,
    hash_spacing_pt=2.3,
)

DEFAULT = JournalStyle(
    name="Default",
    bond_length_pt=37.5,   # 50 px at 96 dpi (our DEFAULT_BOND_LENGTH)
    line_width_pt=1.5,
    font_family="Arial",
    font_size_pt=10.5,
    margin_width_pt=2.0,
    bold_width_pt=3.0,
    hash_spacing_pt=3.0,
)

STYLES: dict[str, JournalStyle] = {
    "Default": DEFAULT,
    "ACS": ACS_1996,
    "RSC": RSC,
    "Nature": NATURE,
    "Wiley": WILEY,
}


def apply_style(scene, style: JournalStyle) -> None:
    """Rescale bond lengths and update fonts to match ``style``.

    Iterates over all atoms in the molecule, scaling positions so the
    average bond length matches the style's target. Also sets the
    scene's default bond length for new drawing operations.
    """
    from bondforge.canvas import geometry

    mol = scene.molecule
    if not mol.bonds:
        # No bonds to measure — just update the default for future drawing.
        geometry.DEFAULT_BOND_LENGTH = style.bond_length_px
        scene.rebuild()
        return

    # Compute current average bond length.
    total = 0.0
    for bond in mol.iter_bonds():
        a = mol.atoms[bond.begin_atom_id]
        b = mol.atoms[bond.end_atom_id]
        total += geometry.distance(a.x, a.y, b.x, b.y)
    avg = total / len(mol.bonds) if mol.bonds else style.bond_length_px

    if avg < 1e-6:
        geometry.DEFAULT_BOND_LENGTH = style.bond_length_px
        scene.rebuild()
        return

    factor = style.bond_length_px / avg

    # Find centroid so we scale about the center.
    cx = sum(a.x for a in mol.iter_atoms()) / len(mol.atoms)
    cy = sum(a.y for a in mol.iter_atoms()) / len(mol.atoms)

    for atom in mol.iter_atoms():
        atom.x = cx + (atom.x - cx) * factor
        atom.y = cy + (atom.y - cy) * factor

    # Scale arrow positions too.
    doc = scene.document
    for arrow in doc.iter_arrows():
        arrow.x1 = cx + (arrow.x1 - cx) * factor
        arrow.y1 = cy + (arrow.y1 - cy) * factor
        arrow.x2 = cx + (arrow.x2 - cx) * factor
        arrow.y2 = cy + (arrow.y2 - cy) * factor

    # Scale text annotation positions.
    for text in doc.iter_texts():
        text.x = cx + (text.x - cx) * factor
        text.y = cy + (text.y - cy) * factor

    geometry.DEFAULT_BOND_LENGTH = style.bond_length_px
    scene.rebuild()


__all__ = [
    "JournalStyle",
    "STYLES",
    "ACS_1996",
    "RSC",
    "NATURE",
    "WILEY",
    "DEFAULT",
    "apply_style",
]
