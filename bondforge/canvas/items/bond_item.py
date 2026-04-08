"""BondItem — QGraphicsItem rendering a bond between two AtomItems."""

from __future__ import annotations

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from bondforge.canvas.items.atom_item import AtomItem
from bondforge.core.model.bond import Bond, BondOrder, BondStereo

BOND_PEN_WIDTH = 2.0
DOUBLE_OFFSET = 4.0
TRIPLE_OFFSET = 5.0
WEDGE_HALF_WIDTH = 4.5
ATOM_GAP = 9.0  # leave room around labeled atoms


class BondItem(QGraphicsItem):
    """Visual representation of a :class:`Bond`."""

    def __init__(
        self,
        bond: Bond,
        begin: AtomItem,
        end: AtomItem,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._bond = bond
        self._begin = begin
        self._end = end
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(1.0)

    @property
    def bond(self) -> Bond:
        return self._bond

    # ----- geometry -----------------------------------------------------

    def _line(self) -> QLineF:
        return QLineF(self._begin.pos(), self._end.pos())

    def _trimmed_line(self) -> QLineF:
        line = self._line()
        if line.length() == 0:
            return line
        unit = line.unitVector()
        ux = unit.dx()
        uy = unit.dy()
        begin_label = self._begin.atom.display_label()
        end_label = self._end.atom.display_label()
        p1 = line.p1()
        p2 = line.p2()
        if begin_label != "C":
            p1 = QPointF(p1.x() + ux * ATOM_GAP, p1.y() + uy * ATOM_GAP)
        if end_label != "C":
            p2 = QPointF(p2.x() - ux * ATOM_GAP, p2.y() - uy * ATOM_GAP)
        return QLineF(p1, p2)

    def boundingRect(self) -> QRectF:  # noqa: N802 (Qt)
        line = self._line()
        x_min = min(line.x1(), line.x2()) - 8
        y_min = min(line.y1(), line.y2()) - 8
        x_max = max(line.x1(), line.x2()) + 8
        y_max = max(line.y1(), line.y2()) + 8
        return QRectF(x_min, y_min, x_max - x_min, y_max - y_min)

    # ----- painting -----------------------------------------------------

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        line = self._trimmed_line()
        if line.length() == 0:
            return

        color = QColor(80, 140, 255) if self.isSelected() else QColor(20, 20, 20)
        pen = QPen(color, BOND_PEN_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(color)

        if self._bond.stereo == BondStereo.WEDGE_UP:
            self._paint_wedge(painter, line)
            return
        if self._bond.stereo == BondStereo.WEDGE_DOWN:
            self._paint_hash(painter, line)
            return

        order = self._bond.order
        if order == BondOrder.SINGLE:
            painter.drawLine(line)
        elif order == BondOrder.DOUBLE:
            self._paint_parallel(painter, line, count=2, spacing=DOUBLE_OFFSET)
        elif order == BondOrder.TRIPLE:
            self._paint_parallel(painter, line, count=3, spacing=TRIPLE_OFFSET)
        elif order == BondOrder.AROMATIC:
            painter.drawLine(line)
            dashed = QPen(color, BOND_PEN_WIDTH, Qt.PenStyle.DashLine)
            painter.setPen(dashed)
            self._paint_parallel(painter, line, count=1, spacing=DOUBLE_OFFSET, skip_main=True)
        else:
            painter.drawLine(line)

    def _paint_parallel(
        self,
        painter: QPainter,
        line: QLineF,
        count: int,
        spacing: float,
        *,
        skip_main: bool = False,
    ) -> None:
        if line.length() == 0:
            return
        nx = -line.dy() / line.length()
        ny = line.dx() / line.length()
        if count == 1:
            offset = spacing
            painter.drawLine(
                QLineF(
                    line.x1() + nx * offset,
                    line.y1() + ny * offset,
                    line.x2() + nx * offset,
                    line.y2() + ny * offset,
                )
            )
            return
        offsets = [(-spacing / 2, spacing / 2)] if count == 2 else [(-spacing, 0.0, spacing)]
        if count == 2 or count == 3:
            for o in offsets[0]:
                painter.drawLine(
                    QLineF(
                        line.x1() + nx * o,
                        line.y1() + ny * o,
                        line.x2() + nx * o,
                        line.y2() + ny * o,
                    )
                )
        if skip_main:
            return

    def _paint_wedge(self, painter: QPainter, line: QLineF) -> None:
        if line.length() == 0:
            return
        nx = -line.dy() / line.length()
        ny = line.dx() / line.length()
        p1 = line.p1()
        p2a = QPointF(line.x2() + nx * WEDGE_HALF_WIDTH, line.y2() + ny * WEDGE_HALF_WIDTH)
        p2b = QPointF(line.x2() - nx * WEDGE_HALF_WIDTH, line.y2() - ny * WEDGE_HALF_WIDTH)
        poly = QPolygonF([p1, p2a, p2b])
        painter.drawPolygon(poly)

    def _paint_hash(self, painter: QPainter, line: QLineF) -> None:
        if line.length() == 0:
            return
        nx = -line.dy() / line.length()
        ny = line.dx() / line.length()
        length = line.length()
        steps = max(4, int(length / 4))
        for i in range(1, steps + 1):
            t = i / steps
            half = WEDGE_HALF_WIDTH * t
            cx = line.x1() + (line.x2() - line.x1()) * t
            cy = line.y1() + (line.y2() - line.y1()) * t
            painter.drawLine(QLineF(cx + nx * half, cy + ny * half, cx - nx * half, cy - ny * half))
