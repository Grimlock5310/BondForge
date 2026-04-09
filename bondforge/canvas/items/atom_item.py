"""AtomItem — QGraphicsItem rendering a single atom on the canvas.

Atoms are drawn as a centered text label only when the element is not
carbon (matching ChemDraw's "carbon-as-vertex" convention). Carbon atoms
render an invisible hit target so they remain selectable.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from bondforge.core.model.atom import Atom

ATOM_FONT_SIZE = 14
ATOM_HIT_RADIUS = 12.0


class AtomItem(QGraphicsItem):
    """Visual representation of an :class:`Atom`."""

    def __init__(self, atom: Atom, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self._atom = atom
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(2.0)
        self.setPos(atom.x, atom.y)

    @property
    def atom(self) -> Atom:
        return self._atom

    def sync_from_model(self) -> None:
        """Refresh position and trigger a repaint after the model changed."""
        self.setPos(self._atom.x, self._atom.y)
        self.update()

    # ----- QGraphicsItem ------------------------------------------------

    def boundingRect(self) -> QRectF:  # noqa: N802 (Qt)
        return QRectF(-ATOM_HIT_RADIUS, -ATOM_HIT_RADIUS, 2 * ATOM_HIT_RADIUS, 2 * ATOM_HIT_RADIUS)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        label = self._atom.display_label()
        if label == "C" and self._atom.charge == 0 and self._atom.label is None:
            # Carbon vertices are implicit. Draw nothing in normal state,
            # unless the atom carries a reaction map number — that needs
            # to be visible even on implicit carbons so users can see the
            # mapping they just stamped.
            if self._atom.map_number:
                self._draw_map_number(painter)
            if self.isSelected():
                painter.setPen(QPen(QColor(80, 140, 255), 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(self.boundingRect().adjusted(2, 2, -2, -2))
            return

        # Background blob to mask the bond ends behind the label.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(QRectF(-10, -10, 20, 20))

        font = QFont()
        font.setPointSize(ATOM_FONT_SIZE)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor(20, 20, 20)))
        rect = QRectF(-20, -20, 40, 40)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

        if self._atom.charge != 0:
            painter.setFont(QFont("", 9, QFont.Weight.Bold))
            sign = "+" if self._atom.charge > 0 else "-"
            mag = "" if abs(self._atom.charge) == 1 else str(abs(self._atom.charge))
            painter.drawText(QRectF(6, -16, 20, 12), Qt.AlignmentFlag.AlignLeft, mag + sign)

        if self._atom.map_number:
            self._draw_map_number(painter)

        if self.isSelected():
            painter.setPen(QPen(QColor(80, 140, 255), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(self.boundingRect().adjusted(2, 2, -2, -2))

    def _draw_map_number(self, painter: QPainter) -> None:
        """Render the atom-map number as a small blue subscript."""
        painter.setFont(QFont("", 8, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(40, 100, 200)))
        painter.drawText(
            QRectF(-18, 2, 14, 12),
            Qt.AlignmentFlag.AlignRight,
            f":{self._atom.map_number}",
        )
