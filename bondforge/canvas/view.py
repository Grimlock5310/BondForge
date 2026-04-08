"""BondForgeView — QGraphicsView subclass with zoom, pan, and hotkey routing.

The view holds a reference to a :class:`HotkeyDispatcher` (set by the
main window after construction). When a key is pressed, the view feeds
the dispatcher the cursor's *current* scene-space position so that
nucleus-style edits target whatever the user is hovering over, not
whatever happens to be focused.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QKeyEvent, QPainter, QWheelEvent
from PySide6.QtWidgets import QGraphicsView

if TYPE_CHECKING:
    from bondforge.canvas.hotkeys import HotkeyDispatcher


class BondForgeView(QGraphicsView):
    """Drawing view with mouse-wheel zoom and key-driven hotkey edits."""

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
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._scale = 1.0
        self._hotkey_dispatcher: HotkeyDispatcher | None = None

    def set_hotkey_dispatcher(self, dispatcher: HotkeyDispatcher | None) -> None:
        self._hotkey_dispatcher = dispatcher

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

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt)
        if self._hotkey_dispatcher is not None and event.text():
            scene_pos = self.mapToScene(self.mapFromGlobal(QCursor.pos()))
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if self._hotkey_dispatcher.handle_key(event.text(), scene_pos, shift=shift):
                event.accept()
                return
        super().keyPressEvent(event)
