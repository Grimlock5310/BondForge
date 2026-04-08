"""Base interface for canvas drawing tools.

A tool receives forwarded mouse events from :class:`BondForgeScene` and
mutates the underlying :class:`Molecule` via :class:`QUndoCommand`
subclasses pushed onto the document's undo stack.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

if TYPE_CHECKING:
    from PySide6.QtGui import QUndoStack
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent

    from bondforge.canvas.scene import BondForgeScene


class BaseTool(QObject):
    """Abstract base class for interactive canvas tools."""

    def __init__(self, scene: BondForgeScene, undo_stack: QUndoStack | None = None) -> None:
        super().__init__()
        self._scene = scene
        self._undo_stack = undo_stack

    @property
    def scene(self) -> BondForgeScene:
        return self._scene

    @property
    def undo_stack(self) -> QUndoStack | None:
        return self._undo_stack

    def activate(self) -> None:
        """Called when this tool becomes active."""

    def deactivate(self) -> None:
        """Called when this tool stops being active."""

    def mouse_press(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle a mouse press in scene coordinates."""

    def mouse_move(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle a mouse move in scene coordinates."""

    def mouse_release(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle a mouse release in scene coordinates."""
