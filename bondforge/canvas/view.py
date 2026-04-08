"""BondForgeView — QGraphicsView subclass with zoom and pan."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QWheelEvent
from PySide6.QtWidgets import QGraphicsView


class BondForgeView(QGraphicsView):
    """Drawing view with mouse-wheel zoom and middle-button pan."""

    MIN_SCALE = 0.1
    MAX_SCALE = 10.0
    ZOOM_FACTOR = 1.15

    def __init__(self, scene=None, parent=None) -> None:
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scale = 1.0

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 (Qt)
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = self.ZOOM_FACTOR if delta > 0 else 1.0 / self.ZOOM_FACTOR
        new_scale = self._scale * factor
        if new_scale < self.MIN_SCALE or new_scale > self.MAX_SCALE:
            return
        self._scale = new_scale
        self.scale(factor, factor)
