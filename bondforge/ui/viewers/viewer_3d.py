"""3D molecular viewer — native QPainter ball-and-stick renderer.

Renders an RDKit ``Mol`` with 3D coordinates using perspective projection
and QPainter. No WebEngine, no JavaScript, no internet — works fully
offline.

Features:
- Left-drag to rotate (trackball)
- Scroll wheel to zoom
- Atoms drawn as filled circles with CPK coloring
- Bonds drawn as grey sticks
- Depth-sorted (painter's algorithm) so closer atoms occlude farther ones
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget
from rdkit import Chem

# CPK-ish element colours.
_ELEMENT_COLORS: dict[str, QColor] = {
    "H": QColor(255, 255, 255),
    "C": QColor(80, 80, 80),
    "N": QColor(48, 80, 248),
    "O": QColor(255, 13, 13),
    "F": QColor(144, 224, 80),
    "Cl": QColor(31, 240, 31),
    "Br": QColor(166, 41, 41),
    "I": QColor(148, 0, 148),
    "S": QColor(255, 200, 50),
    "P": QColor(255, 128, 0),
    "B": QColor(255, 181, 181),
    "Si": QColor(240, 200, 160),
    "Fe": QColor(224, 102, 51),
}
_DEFAULT_COLOR = QColor(200, 200, 200)

# Relative van-der-Waals radii for sphere sizing.
_ELEMENT_RADII: dict[str, float] = {
    "H": 0.31,
    "C": 0.77,
    "N": 0.75,
    "O": 0.73,
    "F": 0.72,
    "Cl": 0.99,
    "Br": 1.14,
    "I": 1.33,
    "S": 1.02,
    "P": 1.06,
}
_DEFAULT_RADIUS = 0.77


@dataclass
class _Atom3D:
    x: float
    y: float
    z: float
    symbol: str


@dataclass
class _Bond3D:
    idx1: int
    idx2: int


def _rotate_y(x: float, y: float, z: float, angle: float) -> tuple[float, float, float]:
    c, s = math.cos(angle), math.sin(angle)
    return c * x + s * z, y, -s * x + c * z


def _rotate_x(x: float, y: float, z: float, angle: float) -> tuple[float, float, float]:
    c, s = math.cos(angle), math.sin(angle)
    return x, c * y - s * z, s * y + c * z


class Viewer3D(QWidget):
    """Native QPainter 3D ball-and-stick molecular viewer."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(400, 350)
        self._atoms: list[_Atom3D] = []
        self._bonds: list[_Bond3D] = []
        self._rot_x: float = 0.3  # radians
        self._rot_y: float = 0.5
        self._zoom: float = 1.0
        self._last_mouse: QPointF | None = None
        self.setMouseTracking(False)

    # ----- public API ---------------------------------------------------

    def set_molecule(self, mol: Chem.Mol, *, conf_id: int = 0) -> None:
        """Load an RDKit Mol with 3D coordinates into the viewer."""
        self._atoms.clear()
        self._bonds.clear()
        if mol.GetNumConformers() == 0:
            self.update()
            return
        conf = mol.GetConformer(conf_id)
        for atom in mol.GetAtoms():
            pos = conf.GetAtomPosition(atom.GetIdx())
            self._atoms.append(_Atom3D(x=pos.x, y=pos.y, z=pos.z, symbol=atom.GetSymbol()))
        for bond in mol.GetBonds():
            self._bonds.append(_Bond3D(idx1=bond.GetBeginAtomIdx(), idx2=bond.GetEndAtomIdx()))
        # Auto-fit zoom.
        if self._atoms:
            max_r = max(math.sqrt(a.x**2 + a.y**2 + a.z**2) for a in self._atoms)
            self._zoom = 1.0 / max(max_r * 0.15, 0.01)
        self.update()

    def clear(self) -> None:
        self._atoms.clear()
        self._bonds.clear()
        self.update()

    # ----- events -------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._last_mouse = event.position()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._last_mouse is not None:
            pos = event.position()
            dx = pos.x() - self._last_mouse.x()
            dy = pos.y() - self._last_mouse.y()
            self._rot_y += dx * 0.01
            self._rot_x += dy * 0.01
            self._last_mouse = pos
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._last_mouse = None

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1.0 / 1.15
        self._zoom *= factor
        self.update()

    # ----- painting -----------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        scale = min(w, h) * 0.35 * self._zoom

        painter.fillRect(0, 0, w, h, QColor(248, 248, 248))

        if not self._atoms:
            painter.setPen(QColor(160, 160, 160))
            painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "No molecule loaded")
            painter.end()
            return

        # Transform all atoms to screen space.
        projected: list[tuple[float, float, float, int]] = []  # sx, sy, depth, idx
        for i, a in enumerate(self._atoms):
            rx, ry, rz = _rotate_x(a.x, a.y, a.z, self._rot_x)
            rx, ry, rz = _rotate_y(rx, ry, rz, self._rot_y)
            sx = cx + rx * scale
            sy = cy - ry * scale  # Qt Y is down
            projected.append((sx, sy, rz, i))

        # Draw bonds first (behind atoms).
        bond_pen = QPen(QColor(140, 140, 140), 2.0)
        painter.setPen(bond_pen)
        for bond in self._bonds:
            sx1, sy1 = projected[bond.idx1][0], projected[bond.idx1][1]
            sx2, sy2 = projected[bond.idx2][0], projected[bond.idx2][1]
            painter.drawLine(QPointF(sx1, sy1), QPointF(sx2, sy2))

        # Sort atoms back-to-front for painter's algorithm.
        projected.sort(key=lambda t: t[2])

        for sx, sy, _depth, idx in projected:
            atom = self._atoms[idx]
            color = _ELEMENT_COLORS.get(atom.symbol, _DEFAULT_COLOR)
            radius = _ELEMENT_RADII.get(atom.symbol, _DEFAULT_RADIUS)
            # Scale radius by zoom and add a depth cue.
            r = radius * scale * 0.18
            r = max(r, 3.0)

            # Simple shading: lighter highlight in top-left.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color.darker(120)))
            painter.drawEllipse(QPointF(sx, sy), r, r)
            # Highlight.
            highlight = color.lighter(160)
            highlight.setAlpha(140)
            painter.setBrush(QBrush(highlight))
            painter.drawEllipse(QPointF(sx - r * 0.25, sy - r * 0.25), r * 0.5, r * 0.5)

            # Label non-carbon, non-hydrogen atoms.
            if atom.symbol not in ("C", "H"):
                painter.setPen(QPen(QColor(255, 255, 255)))
                font = QFont()
                font.setPointSize(max(int(r * 0.7), 7))
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(
                    QRectF(sx - r, sy - r, 2 * r, 2 * r),
                    Qt.AlignmentFlag.AlignCenter,
                    atom.symbol,
                )

        painter.end()
