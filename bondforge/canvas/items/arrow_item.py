"""ArrowItem — QGraphicsItem rendering reaction and electron-pushing arrows.

Reaction arrows (``FORWARD``, ``EQUILIBRIUM``, ``RETROSYNTHETIC``) are
drawn as straight shafts with one or two filled triangle heads. Curved
arrows (``ELECTRON_PAIR``, ``SINGLE_ELECTRON``) are drawn as a
single-segment quadratic Bézier whose control point is offset
perpendicular to the chord by ``curvature``; ``ELECTRON_PAIR`` finishes
with a full triangle head, ``SINGLE_ELECTRON`` with a half-head
"fish hook" stroke.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from bondforge.core.model.arrow import Arrow, ArrowKind

ARROW_PEN_WIDTH = 2.0
HEAD_LENGTH = 12.0
HEAD_HALF_WIDTH = 5.0
EQUILIBRIUM_OFFSET = 4.0


class ArrowItem(QGraphicsItem):
    """Visual representation of an :class:`Arrow`."""

    def __init__(self, arrow: Arrow, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self._arrow = arrow
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(3.0)

    @property
    def arrow(self) -> Arrow:
        return self._arrow

    # ----- bounds -------------------------------------------------------

    def boundingRect(self) -> QRectF:  # noqa: N802 (Qt)
        a = self._arrow
        x_min = min(a.x1, a.x2) - HEAD_LENGTH - abs(a.curvature)
        y_min = min(a.y1, a.y2) - HEAD_LENGTH - abs(a.curvature)
        x_max = max(a.x1, a.x2) + HEAD_LENGTH + abs(a.curvature)
        y_max = max(a.y1, a.y2) + HEAD_LENGTH + abs(a.curvature)
        return QRectF(x_min, y_min, x_max - x_min, y_max - y_min)

    # ----- paint --------------------------------------------------------

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        color = QColor(80, 140, 255) if self.isSelected() else QColor(20, 20, 20)
        pen = QPen(color, ARROW_PEN_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(QBrush(color))

        kind = self._arrow.kind
        if kind == ArrowKind.FORWARD:
            self._paint_forward(painter)
        elif kind == ArrowKind.EQUILIBRIUM:
            self._paint_equilibrium(painter)
        elif kind == ArrowKind.RETROSYNTHETIC:
            self._paint_retro(painter)
        elif kind == ArrowKind.ELECTRON_PAIR:
            self._paint_curved(painter, half_head=False)
        elif kind == ArrowKind.SINGLE_ELECTRON:
            self._paint_curved(painter, half_head=True)

    # ----- reaction arrows ----------------------------------------------

    def _paint_forward(self, painter: QPainter) -> None:
        a = self._arrow
        line = QLineF(a.x1, a.y1, a.x2, a.y2)
        painter.drawLine(line)
        self._draw_head(painter, line, half=False)
        self._draw_label(painter, line)

    def _paint_equilibrium(self, painter: QPainter) -> None:
        """Two parallel half-arrows pointing in opposite directions."""
        a = self._arrow
        line = QLineF(a.x1, a.y1, a.x2, a.y2)
        length = line.length()
        if length == 0:
            return
        nx = -line.dy() / length
        ny = line.dx() / length

        # Top arrow: tail->head, offset toward "above".
        top = QLineF(
            a.x1 + nx * EQUILIBRIUM_OFFSET,
            a.y1 + ny * EQUILIBRIUM_OFFSET,
            a.x2 + nx * EQUILIBRIUM_OFFSET,
            a.y2 + ny * EQUILIBRIUM_OFFSET,
        )
        # Bottom arrow: head->tail, offset toward "below".
        bot = QLineF(
            a.x2 - nx * EQUILIBRIUM_OFFSET,
            a.y2 - ny * EQUILIBRIUM_OFFSET,
            a.x1 - nx * EQUILIBRIUM_OFFSET,
            a.y1 - ny * EQUILIBRIUM_OFFSET,
        )
        painter.drawLine(top)
        painter.drawLine(bot)
        self._draw_head(painter, top, half=True, side=+1)
        self._draw_head(painter, bot, half=True, side=+1)
        self._draw_label(painter, line)

    def _paint_retro(self, painter: QPainter) -> None:
        """Two parallel lines with a single head at the product end."""
        a = self._arrow
        line = QLineF(a.x1, a.y1, a.x2, a.y2)
        length = line.length()
        if length == 0:
            return
        nx = -line.dy() / length
        ny = line.dx() / length
        gap = 2.5
        top = QLineF(a.x1 + nx * gap, a.y1 + ny * gap, a.x2 + nx * gap, a.y2 + ny * gap)
        bot = QLineF(a.x1 - nx * gap, a.y1 - ny * gap, a.x2 - nx * gap, a.y2 - ny * gap)
        painter.drawLine(top)
        painter.drawLine(bot)
        self._draw_head(painter, line, half=False)
        self._draw_label(painter, line)

    # ----- curved electron arrows ---------------------------------------

    def _paint_curved(self, painter: QPainter, *, half_head: bool) -> None:
        """Quadratic Bézier with a full or half head at the tip."""
        a = self._arrow
        dx = a.x2 - a.x1
        dy = a.y2 - a.y1
        chord = math.hypot(dx, dy)
        if chord == 0:
            return
        mx = (a.x1 + a.x2) / 2
        my = (a.y1 + a.y2) / 2
        # Perpendicular unit vector.
        px = -dy / chord
        py = dx / chord
        curvature = a.curvature if a.curvature != 0 else chord * 0.35
        cx = mx + px * curvature
        cy = my + py * curvature

        path = QPainterPath()
        path.moveTo(a.x1, a.y1)
        path.quadTo(cx, cy, a.x2, a.y2)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        # Tangent at the end for head orientation:
        # derivative of Bézier at t=1 is 2*((p2 - c)).
        tx = 2 * (a.x2 - cx)
        ty = 2 * (a.y2 - cy)
        tlen = math.hypot(tx, ty)
        if tlen == 0:
            return
        tx /= tlen
        ty /= tlen
        self._draw_curved_head(painter, a.x2, a.y2, tx, ty, half=half_head)

    def _draw_curved_head(
        self,
        painter: QPainter,
        tip_x: float,
        tip_y: float,
        tangent_x: float,
        tangent_y: float,
        *,
        half: bool,
    ) -> None:
        # Perpendicular to tangent.
        nx = -tangent_y
        ny = tangent_x
        base_x = tip_x - tangent_x * HEAD_LENGTH
        base_y = tip_y - tangent_y * HEAD_LENGTH
        if half:
            # Single-line "fish hook" on the +perp side only.
            wing = QPointF(base_x + nx * HEAD_HALF_WIDTH, base_y + ny * HEAD_HALF_WIDTH)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(QLineF(tip_x, tip_y, wing.x(), wing.y()))
            return
        left = QPointF(base_x + nx * HEAD_HALF_WIDTH, base_y + ny * HEAD_HALF_WIDTH)
        right = QPointF(base_x - nx * HEAD_HALF_WIDTH, base_y - ny * HEAD_HALF_WIDTH)
        painter.setBrush(QBrush(painter.pen().color()))
        painter.drawPolygon(QPolygonF([QPointF(tip_x, tip_y), left, right]))

    # ----- shared helpers -----------------------------------------------

    def _draw_head(self, painter: QPainter, line: QLineF, *, half: bool, side: int = +1) -> None:
        length = line.length()
        if length == 0:
            return
        ux = line.dx() / length
        uy = line.dy() / length
        nx = -uy
        ny = ux
        tip = line.p2()
        base = QPointF(tip.x() - ux * HEAD_LENGTH, tip.y() - uy * HEAD_LENGTH)
        if half:
            wing = QPointF(
                base.x() + side * nx * HEAD_HALF_WIDTH,
                base.y() + side * ny * HEAD_HALF_WIDTH,
            )
            painter.drawLine(QLineF(tip, wing))
            return
        left = QPointF(base.x() + nx * HEAD_HALF_WIDTH, base.y() + ny * HEAD_HALF_WIDTH)
        right = QPointF(base.x() - nx * HEAD_HALF_WIDTH, base.y() - ny * HEAD_HALF_WIDTH)
        painter.drawPolygon(QPolygonF([tip, left, right]))

    def _draw_label(self, painter: QPainter, line: QLineF) -> None:
        label = self._arrow.label
        if not label:
            return
        # Place the label above the arrow midpoint.
        mid_x = (line.x1() + line.x2()) / 2
        mid_y = (line.y1() + line.y2()) / 2
        length = line.length()
        if length == 0:
            return
        nx = -line.dy() / length
        ny = line.dx() / length
        offset = 14.0
        text_x = mid_x + nx * offset - 40
        text_y = mid_y + ny * offset - 10
        font = QFont()
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(QRectF(text_x, text_y, 80, 20), Qt.AlignmentFlag.AlignCenter, label)
