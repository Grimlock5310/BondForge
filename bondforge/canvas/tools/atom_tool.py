"""AtomTool — click anywhere on the canvas to place a single atom.

If the click lands on top of an existing :class:`AtomItem`, this tool
replaces that atom's element instead of inserting a new one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bondforge.canvas.items.atom_item import AtomItem
from bondforge.canvas.tools.base_tool import BaseTool
from bondforge.core.commands import AddAtomCommand, ChangeElementCommand

if TYPE_CHECKING:
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent

    from bondforge.canvas.scene import BondForgeScene


class AtomTool(BaseTool):
    """Place atoms of a configurable element."""

    def __init__(self, scene: BondForgeScene, undo_stack=None, element: str = "C") -> None:
        super().__init__(scene, undo_stack)
        self.element = element

    def set_element(self, element: str) -> None:
        self.element = element

    def mouse_press(self, event: QGraphicsSceneMouseEvent) -> None:
        pos = event.scenePos()
        item = (
            self.scene.itemAt(pos, self.scene.views()[0].transform())
            if self.scene.views()
            else None
        )
        if isinstance(item, AtomItem):
            cmd = ChangeElementCommand(self.scene, item.atom.id, self.element)
        else:
            cmd = AddAtomCommand(self.scene, self.element, pos.x(), pos.y())
        if self.undo_stack is not None:
            self.undo_stack.push(cmd)
        else:
            cmd.redo()
        self.scene.rebuild()
