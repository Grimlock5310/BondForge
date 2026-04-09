"""ArrowTool — drag to place a reaction or electron-pushing arrow.

One tool instance per arrow flavor; the main window constructs a
``FORWARD`` tool, an ``EQUILIBRIUM`` tool, and so on, and the toolbar
buttons pick which is active. Dragging on the canvas draws a preview
line and drops an arrow command on release.

Curved arrows use a default curvature equal to 35% of the chord length,
chosen so a typical "hop off a lone pair" arrow has a natural arc
without looking limp. The user can later tweak the control point by
selecting the arrow (v0.4 will expose a drag handle).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtCore import QLineF, QPointF, Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsLineItem

from bondforge.canvas.tools.base_tool import BaseTool
from bondforge.core.commands import AddArrowCommand
from bondforge.core.model.arrow import ArrowKind

if TYPE_CHECKING:
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent

CLICK_MIN_LENGTH = 20.0  # A pure click drops a default-length arrow.
DEFAULT_ARROW_LENGTH = 80.0


class ArrowTool(BaseTool):
    """Click-drag to create a :class:`bondforge.core.model.arrow.Arrow`."""

    def __init__(
        self,
        scene,
        undo_stack=None,
        kind: ArrowKind = ArrowKind.FORWARD,
    ) -> None:
        super().__init__(scene, undo_stack)
        self.kind = kind
        self._press_pos: QPointF | None = None
        self._preview: QGraphicsLineItem | None = None

    # ----- handlers -----------------------------------------------------

    def mouse_press(self, event: QGraphicsSceneMouseEvent) -> None:
        self._press_pos = event.scenePos()

    def mouse_move(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._press_pos is None:
            return
        end = event.scenePos()
        self._show_preview(self._press_pos.x(), self._press_pos.y(), end.x(), end.y())

    def mouse_release(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._press_pos is None:
            return
        end = event.scenePos()
        x1, y1 = self._press_pos.x(), self._press_pos.y()
        x2, y2 = end.x(), end.y()
        length = math.hypot(x2 - x1, y2 - y1)
        if length < CLICK_MIN_LENGTH:
            # Convert a bare click into a default-length horizontal arrow.
            x2 = x1 + DEFAULT_ARROW_LENGTH
            y2 = y1

        self._push(AddArrowCommand(self.scene, self.kind, x1, y1, x2, y2))
        self._hide_preview()
        self._press_pos = None
        self.scene.rebuild()

    def deactivate(self) -> None:
        self._hide_preview()
        self._press_pos = None

    # ----- helpers ------------------------------------------------------

    def _show_preview(self, x1: float, y1: float, x2: float, y2: float) -> None:
        if self._preview is None:
            self._preview = QGraphicsLineItem()
            pen = QPen(QColor(80, 140, 255, 180), 2.0, Qt.PenStyle.DashLine)
            self._preview.setPen(pen)
            self.scene.add_preview_item(self._preview)
        self._preview.setLine(QLineF(x1, y1, x2, y2))

    def _hide_preview(self) -> None:
        if self._preview is not None:
            self.scene.clear_previews()
            self._preview = None

    def _push(self, cmd) -> None:
        if self.undo_stack is not None:
            self.undo_stack.push(cmd)
        else:
            cmd.redo()
