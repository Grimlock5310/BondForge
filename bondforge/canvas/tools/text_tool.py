"""TextTool — click on the canvas to place a text annotation.

A single click places a new :class:`TextAnnotation` at the click
position with default placeholder text. The user can then double-click
the resulting :class:`TextItem` to enter inline editing mode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bondforge.canvas.tools.base_tool import BaseTool
from bondforge.core.commands import AddTextCommand

if TYPE_CHECKING:
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent


class TextTool(BaseTool):
    """Click to place a text annotation on the canvas."""

    def __init__(self, scene, undo_stack=None) -> None:
        super().__init__(scene, undo_stack)

    def mouse_press(self, event: QGraphicsSceneMouseEvent) -> None:
        pos = event.scenePos()
        cmd = AddTextCommand(self._scene, "Text", pos.x(), pos.y())
        if self._undo_stack is not None:
            self._undo_stack.push(cmd)
        else:
            cmd.redo()

    def mouse_move(self, event: QGraphicsSceneMouseEvent) -> None:
        pass

    def mouse_release(self, event: QGraphicsSceneMouseEvent) -> None:
        pass
