"""BiopolymerItem — QGraphicsItem that renders a biopolymer on the canvas.

Displays each polymer chain as a horizontal row of monomer blocks, with
inter-chain connections drawn as dashed lines. The overall biopolymer
is a single selectable, movable item group.

Layout:
- Each monomer residue is a small rectangle with its symbol inside.
- Chains are stacked vertically.
- Connections are drawn as lines between residue centers.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from bondforge.core.model.biopolymer import Biopolymer
from bondforge.core.model.monomer import PolymerType

# Layout constants.
BLOCK_W = 28.0
BLOCK_H = 24.0
BLOCK_SPACING = 2.0
CHAIN_SPACING = 40.0
LABEL_FONT_SIZE = 9

# Color scheme by polymer type.
_TYPE_COLORS: dict[PolymerType, QColor] = {
    PolymerType.PEPTIDE: QColor(100, 149, 237),   # cornflower blue
    PolymerType.RNA: QColor(144, 190, 109),        # olive green
    PolymerType.DNA: QColor(255, 165, 79),         # sandy orange
    PolymerType.CHEM: QColor(200, 200, 200),       # light gray
}


class BiopolymerItem(QGraphicsItem):
    """Visual representation of a :class:`Biopolymer`."""

    def __init__(
        self,
        biopolymer: Biopolymer,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._bp = biopolymer
        self.setPos(biopolymer.x, biopolymer.y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setZValue(5.0)

        # Pre-compute chain layout.
        self._chain_rects: dict[str, list[QRectF]] = {}
        self._chain_origins: dict[str, QPointF] = {}
        self._compute_layout()

    @property
    def biopolymer(self) -> Biopolymer:
        return self._bp

    def _compute_layout(self) -> None:
        """Compute the bounding rect of each residue for painting."""
        y_offset = 0.0
        for chain in self._bp.iter_chains():
            self._chain_origins[chain.id] = QPointF(0, y_offset)
            rects: list[QRectF] = []
            for i, _residue in enumerate(chain.residues):
                x = i * (BLOCK_W + BLOCK_SPACING)
                rects.append(QRectF(x, y_offset, BLOCK_W, BLOCK_H))
            self._chain_rects[chain.id] = rects
            y_offset += BLOCK_H + CHAIN_SPACING

    def _residue_center(self, chain_id: str, position: int) -> QPointF | None:
        """Return the scene-local center of a residue block."""
        rects = self._chain_rects.get(chain_id, [])
        idx = position - 1  # 1-based to 0-based
        if 0 <= idx < len(rects):
            return rects[idx].center()
        return None

    def boundingRect(self) -> QRectF:  # noqa: N802
        if not self._chain_rects:
            return QRectF(0, 0, 50, 30)
        all_rects = [r for rects in self._chain_rects.values() for r in rects]
        if not all_rects:
            return QRectF(0, 0, 50, 30)
        left = min(r.left() for r in all_rects)
        top = min(r.top() for r in all_rects)
        right = max(r.right() for r in all_rects)
        bottom = max(r.bottom() for r in all_rects)
        # Add room for chain labels and connections.
        return QRectF(left - 80, top - 10, right - left + 90, bottom - top + 20)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont("Arial", LABEL_FONT_SIZE)
        painter.setFont(font)

        # Draw chain labels and residue blocks.
        for chain in self._bp.iter_chains():
            rects = self._chain_rects.get(chain.id, [])
            color = _TYPE_COLORS.get(chain.polymer_type, QColor(200, 200, 200))
            brush = QBrush(color)
            pen = QPen(color.darker(140), 1.0)

            # Chain label to the left.
            if rects:
                label_y = rects[0].center().y()
                painter.setPen(QPen(Qt.GlobalColor.black))
                painter.drawText(QPointF(rects[0].left() - 75, label_y + 4), chain.id)

            # Residue blocks.
            for i, rect in enumerate(rects):
                painter.setPen(pen)
                painter.setBrush(brush)
                painter.drawRoundedRect(rect, 3, 3)

                # Residue symbol.
                if i < len(chain.residues):
                    painter.setPen(QPen(Qt.GlobalColor.white))
                    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, chain.residues[i].symbol)

            # Draw backbone line connecting residues.
            if len(rects) > 1:
                painter.setPen(QPen(color.darker(120), 1.5))
                for i in range(len(rects) - 1):
                    p1 = QPointF(rects[i].right(), rects[i].center().y())
                    p2 = QPointF(rects[i + 1].left(), rects[i + 1].center().y())
                    painter.drawLine(p1, p2)

        # Draw connections (disulfide bonds, etc.).
        conn_pen = QPen(QColor(180, 50, 50), 1.5, Qt.PenStyle.DashLine)
        for conn in self._bp.iter_connections():
            p1 = self._residue_center(conn.source_chain_id, conn.source_position)
            p2 = self._residue_center(conn.target_chain_id, conn.target_position)
            if p1 is not None and p2 is not None:
                painter.setPen(conn_pen)
                painter.drawLine(p1, p2)

        # Selection highlight.
        if self.isSelected():
            painter.setPen(QPen(QColor(0, 120, 215), 2.0, Qt.PenStyle.DashDotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.boundingRect().adjusted(2, 2, -2, -2))


__all__ = ["BiopolymerItem"]
