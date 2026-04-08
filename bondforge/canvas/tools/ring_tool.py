"""RingTool — click to drop a regular polygon ring at the cursor.

The ring's placement mirrors ChemDraw's idiom:

- Click empty canvas → drop a fresh, centered n-membered ring.
- Click on an existing **atom** → the ring grows *off* that atom (the atom
  becomes one vertex of the new ring). The ring is oriented into the
  largest empty wedge around that atom so it doesn't collide with the
  existing substituents.
- Click on an existing **bond** → the ring is **fused** to that bond (the
  bond becomes one edge of the new ring). The ring expands on the side of
  the bond where the click landed, so the user can choose which face the
  ring appears on by clicking just above or just below the bond.

The whole ring — atoms *and* bonds — is pushed as a single macro on the
undo stack, so one ``Ctrl+Z`` cleanly removes it.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF

from bondforge.canvas.geometry import (
    DEFAULT_BOND_LENGTH,
    best_new_bond_angle,
    neighbor_angles,
)
from bondforge.canvas.items.atom_item import AtomItem
from bondforge.canvas.items.bond_item import BondItem
from bondforge.canvas.tools.base_tool import BaseTool
from bondforge.core.commands import AddAtomCommand, AddBondCommand
from bondforge.core.model.bond import BondOrder

if TYPE_CHECKING:
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent


class RingTool(BaseTool):
    """Drop a regular n-membered ring with snap-to-atom / fuse-to-bond."""

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

    # ----- event entry point -------------------------------------------

    def mouse_press(self, event: QGraphicsSceneMouseEvent) -> None:
        click_pos = event.scenePos()
        atom_item = self._atom_at(click_pos)
        bond_item = None if atom_item is not None else self._bond_at(click_pos)

        label = f"Add {self.size}-ring"
        stack = self.undo_stack
        if stack is not None:
            stack.beginMacro(label)
        try:
            if bond_item is not None:
                self._fuse_to_bond(bond_item, click_pos)
            elif atom_item is not None:
                self._fuse_to_atom(atom_item)
            else:
                self._place_centered(click_pos.x(), click_pos.y())
        finally:
            if stack is not None:
                stack.endMacro()

        self.scene.rebuild()

    # ----- placement strategies -----------------------------------------

    def _place_centered(self, cx: float, cy: float) -> None:
        radius = DEFAULT_BOND_LENGTH / (2 * math.sin(math.pi / self.size))
        atom_ids: list[int] = []
        for i in range(self.size):
            theta = 2 * math.pi * i / self.size - math.pi / 2
            x = cx + radius * math.cos(theta)
            y = cy + radius * math.sin(theta)
            cmd = AddAtomCommand(self.scene, "C", x, y)
            self._push(cmd)
            atom_ids.append(cmd.created_atom_id)
        self._link_ring(atom_ids, skip_first_edge=False)

    def _fuse_to_atom(self, atom_item: AtomItem) -> None:
        """Grow a ring that shares the clicked atom as one vertex."""
        shared = atom_item.atom
        ax, ay = shared.x, shared.y

        # Pick a direction that stays clear of existing bonds at this atom.
        neighbor_coords = [
            (
                self.scene.molecule.atoms[bond.other_atom_id(shared.id)].x,
                self.scene.molecule.atoms[bond.other_atom_id(shared.id)].y,
            )
            for bond in self.scene.molecule.bonds_for_atom(shared.id)
        ]
        angles = neighbor_angles(ax, ay, neighbor_coords)
        bisector_angle = best_new_bond_angle(angles)

        radius = DEFAULT_BOND_LENGTH / (2 * math.sin(math.pi / self.size))
        # The ring's center lies along the bisector, one circumradius away.
        cx = ax + radius * math.cos(bisector_angle)
        cy = ay + radius * math.sin(bisector_angle)

        # Vertex 0 is the shared atom; the remaining n-1 vertices are new.
        angle_0 = math.atan2(ay - cy, ax - cx)
        angle_step = 2 * math.pi / self.size

        atom_ids: list[int] = [shared.id]
        for i in range(1, self.size):
            theta = angle_0 + i * angle_step
            x = cx + radius * math.cos(theta)
            y = cy + radius * math.sin(theta)
            cmd = AddAtomCommand(self.scene, "C", x, y)
            self._push(cmd)
            atom_ids.append(cmd.created_atom_id)
        self._link_ring(atom_ids, skip_first_edge=False)

    def _fuse_to_bond(self, bond_item: BondItem, click_pos: QPointF) -> None:
        """Grow a ring that shares the clicked bond as one edge."""
        mol = self.scene.molecule
        a_atom = mol.atoms[bond_item.bond.begin_atom_id]
        b_atom = mol.atoms[bond_item.bond.end_atom_id]
        ax, ay = a_atom.x, a_atom.y
        bx, by = b_atom.x, b_atom.y

        dx = bx - ax
        dy = by - ay
        edge_length = math.hypot(dx, dy)
        if edge_length == 0:
            # Degenerate bond; fall back to centered placement.
            self._place_centered(click_pos.x(), click_pos.y())
            return

        mx = (ax + bx) / 2
        my = (ay + by) / 2
        # Perpendicular unit vector to AB.
        px = -dy / edge_length
        py = dx / edge_length

        # Push the ring onto the side of AB where the user clicked.
        click_side = (click_pos.x() - mx) * px + (click_pos.y() - my) * py
        sign = 1.0 if click_side >= 0 else -1.0

        # Apothem: distance from edge midpoint to polygon center.
        apothem = edge_length / (2 * math.tan(math.pi / self.size))
        cx = mx + sign * apothem * px
        cy = my + sign * apothem * py

        # Circumradius — should equal edge_length/(2 sin(pi/n)). We reuse it
        # so all generated atoms sit exactly on the circle through A and B.
        radius = edge_length / (2 * math.sin(math.pi / self.size))

        # Walk around the circle starting at A. Determine which direction
        # (CCW vs CW in scene coords) lands us on B after one angular step.
        angle_a = math.atan2(ay - cy, ax - cx)
        angle_step = 2 * math.pi / self.size

        ccw_angle = angle_a + angle_step
        cw_angle = angle_a - angle_step
        ccw_x = cx + radius * math.cos(ccw_angle)
        ccw_y = cy + radius * math.sin(ccw_angle)
        cw_x = cx + radius * math.cos(cw_angle)
        cw_y = cy + radius * math.sin(cw_angle)
        ccw_err = (ccw_x - bx) ** 2 + (ccw_y - by) ** 2
        cw_err = (cw_x - bx) ** 2 + (cw_y - by) ** 2
        step_sign = 1 if ccw_err < cw_err else -1

        atom_ids: list[int] = [a_atom.id, b_atom.id]
        for i in range(2, self.size):
            theta = angle_a + step_sign * i * angle_step
            x = cx + radius * math.cos(theta)
            y = cy + radius * math.sin(theta)
            cmd = AddAtomCommand(self.scene, "C", x, y)
            self._push(cmd)
            atom_ids.append(cmd.created_atom_id)

        # Skip the 0-1 edge — that's the bond we fused to; it already exists.
        self._link_ring(atom_ids, skip_first_edge=True)

    # ----- helpers ------------------------------------------------------

    def _link_ring(self, atom_ids: list[int], *, skip_first_edge: bool) -> None:
        """Add bonds around the ring, honoring the Kekulé pattern for benzene."""
        n = len(atom_ids)
        start = 1 if skip_first_edge else 0
        for i in range(start, n):
            a_id = atom_ids[i]
            b_id = atom_ids[(i + 1) % n]
            order = self._ring_bond_order(i)
            self._push(AddBondCommand(self.scene, a_id, b_id, order))

    def _ring_bond_order(self, index: int) -> BondOrder:
        if self.aromatic and self.size == 6:
            return BondOrder.SINGLE if index % 2 == 0 else BondOrder.DOUBLE
        return BondOrder.AROMATIC if self.aromatic else BondOrder.SINGLE

    def _atom_at(self, pos: QPointF) -> AtomItem | None:
        view = self.scene.views()[0] if self.scene.views() else None
        transform = view.transform() if view is not None else None
        item = self.scene.itemAt(pos, transform) if transform is not None else None
        return item if isinstance(item, AtomItem) else None

    def _bond_at(self, pos: QPointF) -> BondItem | None:
        view = self.scene.views()[0] if self.scene.views() else None
        transform = view.transform() if view is not None else None
        item = self.scene.itemAt(pos, transform) if transform is not None else None
        return item if isinstance(item, BondItem) else None

    def _push(self, cmd) -> None:
        if self.undo_stack is not None:
            self.undo_stack.push(cmd)
        else:
            cmd.redo()
