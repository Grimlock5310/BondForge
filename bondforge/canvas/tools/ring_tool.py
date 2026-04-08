"""RingTool — click to drop a regular polygon ring at the cursor.

The ring's atoms and bonds are added in a single :class:`QUndoCommand`
group so that one undo removes the whole ring.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from bondforge.canvas.geometry import DEFAULT_BOND_LENGTH
from bondforge.canvas.tools.base_tool import BaseTool
from bondforge.core.commands import AddAtomCommand, AddBondCommand
from bondforge.core.model.bond import BondOrder

if TYPE_CHECKING:
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent


class RingTool(BaseTool):
    """Drop a regular n-membered ring centered on the click."""

    def __init__(
        self,
        scene,
        undo_stack=None,
        size: int = 6,
        aromatic: bool = True,
    ) -> None:
        super().__init__(scene, undo_stack)
        self.size = size
        self.aromatic = aromatic

    def mouse_press(self, event: QGraphicsSceneMouseEvent) -> None:
        cx = event.scenePos().x()
        cy = event.scenePos().y()
        radius = DEFAULT_BOND_LENGTH / (2 * math.sin(math.pi / self.size))

        atom_ids: list[int] = []
        for i in range(self.size):
            theta = 2 * math.pi * i / self.size - math.pi / 2
            x = cx + radius * math.cos(theta)
            y = cy + radius * math.sin(theta)
            cmd = AddAtomCommand(self.scene, "C", x, y)
            self._push(cmd)
            atom_ids.append(cmd.created_atom_id)

        for i in range(self.size):
            a = atom_ids[i]
            b = atom_ids[(i + 1) % self.size]
            order = BondOrder.AROMATIC if self.aromatic else BondOrder.SINGLE
            # Plain Kekulé alternative for non-aromatic rendering of benzene-like rings.
            if self.aromatic and self.size == 6:
                order = BondOrder.SINGLE if i % 2 == 0 else BondOrder.DOUBLE
            self._push(AddBondCommand(self.scene, a, b, order))

        self.scene.rebuild()

    def _push(self, cmd) -> None:
        if self.undo_stack is not None:
            self.undo_stack.push(cmd)
        else:
            cmd.redo()
