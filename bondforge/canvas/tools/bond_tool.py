"""BondTool — drag from one atom to another to create a bond.

If the drag starts in empty space, an implicit carbon is created at the
press position. If it ends in empty space, another implicit carbon is
created there. The result is the standard ChemDraw "drag a stick" UX.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from bondforge.canvas.items.atom_item import AtomItem
from bondforge.canvas.scene import DEFAULT_BOND_LENGTH
from bondforge.canvas.tools.base_tool import BaseTool
from bondforge.core.commands import AddAtomCommand, AddBondCommand
from bondforge.core.model.bond import BondOrder

if TYPE_CHECKING:
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent


class BondTool(BaseTool):
    """Click-drag to draw bonds. Single bonds by default."""

    def __init__(self, scene, undo_stack=None, order: BondOrder = BondOrder.SINGLE) -> None:
        super().__init__(scene, undo_stack)
        self.order = order
        self._press_atom_id: int | None = None
        self._press_pos: QPointF | None = None

    def _atom_at(self, pos) -> AtomItem | None:
        view = self.scene.views()[0] if self.scene.views() else None
        transform = view.transform() if view is not None else None
        item = self.scene.itemAt(pos, transform) if transform is not None else None
        return item if isinstance(item, AtomItem) else None

    def mouse_press(self, event: QGraphicsSceneMouseEvent) -> None:
        self._press_pos = event.scenePos()
        atom_item = self._atom_at(self._press_pos)
        self._press_atom_id = atom_item.atom.id if atom_item is not None else None

    def mouse_release(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._press_pos is None:
            return
        end_pos = event.scenePos()
        end_item = self._atom_at(end_pos)

        # Resolve start atom: existing or create new C.
        start_id = self._press_atom_id
        if start_id is None:
            cmd = AddAtomCommand(self.scene, "C", self._press_pos.x(), self._press_pos.y())
            self._push(cmd)
            start_id = cmd.created_atom_id

        # If the user just clicked (no real drag) and the click was on an atom,
        # create a new bonded atom in the default direction.
        dx = end_pos.x() - self._press_pos.x()
        dy = end_pos.y() - self._press_pos.y()
        if math.hypot(dx, dy) < 4 and end_item is None:
            angle = math.radians(30)
            ex = self._press_pos.x() + DEFAULT_BOND_LENGTH * math.cos(angle)
            ey = self._press_pos.y() + DEFAULT_BOND_LENGTH * math.sin(angle)
            cmd = AddAtomCommand(self.scene, "C", ex, ey)
            self._push(cmd)
            end_id = cmd.created_atom_id
        elif end_item is not None:
            end_id = end_item.atom.id
        else:
            cmd = AddAtomCommand(self.scene, "C", end_pos.x(), end_pos.y())
            self._push(cmd)
            end_id = cmd.created_atom_id

        if start_id != end_id:
            self._push(AddBondCommand(self.scene, start_id, end_id, self.order))

        self.scene.rebuild()
        self._press_atom_id = None
        self._press_pos = None

    def _push(self, cmd) -> None:
        if self.undo_stack is not None:
            self.undo_stack.push(cmd)
        else:
            cmd.redo()
