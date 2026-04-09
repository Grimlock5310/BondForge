"""BondTool — drag from one atom to another to create a bond.

The user experience matches ChemDraw's "drag a stick" idiom:

- Click on empty canvas to drop a single bond off an implicit carbon, with
  the new atom auto-placed using a 30°-snapped angle and a uniform bond
  length (see :mod:`bondforge.canvas.geometry`).
- Click on an existing atom to grow a new bond off that atom; the angle
  snaps to a multiple of 30°, and the new atom lands at exactly the
  default bond length away.
- Drag from atom A to atom B to bond them together (no length snapping
  in this case — A and B already have positions).

A live preview line shadows the cursor while dragging so the user can see
where the bond will land before releasing the button.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtCore import QLineF, QPointF, Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsLineItem

from bondforge.canvas.geometry import (
    DEFAULT_BOND_LENGTH,
    free_endpoint_at_default_length,
    snap_endpoint,
    zigzag_extension_angle,
)
from bondforge.canvas.items.atom_item import AtomItem
from bondforge.canvas.items.bond_item import BondItem
from bondforge.canvas.tools.base_tool import BaseTool
from bondforge.core.commands import AddAtomCommand, AddBondCommand, SetBondOrderCommand
from bondforge.core.model.bond import BondOrder, BondStereo

if TYPE_CHECKING:
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent

# Drag distance below which we treat the gesture as a "click" rather than a
# stretch. Below this we always create a new atom at the default length and
# snapped angle.
CLICK_THRESHOLD = 4.0


class BondTool(BaseTool):
    """Click-drag to draw bonds with angle snapping and uniform length."""

    def __init__(
        self,
        scene,
        undo_stack=None,
        order: BondOrder = BondOrder.SINGLE,
        stereo: BondStereo = BondStereo.NONE,
    ) -> None:
        super().__init__(scene, undo_stack)
        self.order = order
        self.stereo = stereo
        self._press_atom_id: int | None = None
        self._press_pos: QPointF | None = None
        self._preview: QGraphicsLineItem | None = None

    # ----- helpers ------------------------------------------------------

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

    def _resolve_endpoint(
        self, start_x: float, start_y: float, end_pos: QPointF, end_item: AtomItem | None
    ) -> tuple[float, float, AtomItem | None]:
        """Return (x, y, snap_target_item) for the bond endpoint.

        If the cursor is hovering an existing atom we snap to it. Otherwise
        we apply 30° angle snapping and force the bond to the default length.
        """
        if end_item is not None:
            return end_item.atom.x, end_item.atom.y, end_item
        sx, sy = snap_endpoint(start_x, start_y, end_pos.x(), end_pos.y())
        return sx, sy, None

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

    def deactivate(self) -> None:
        self._hide_preview()
        self._press_atom_id = None
        self._press_pos = None

    # ----- mouse handlers -----------------------------------------------

    def mouse_press(self, event: QGraphicsSceneMouseEvent) -> None:
        pos = event.scenePos()
        atom_item = self._atom_at(pos)

        # Clicking on an existing bond with a typed bond tool should
        # **set** that bond's order rather than dragging out a new bond
        # from the click point. (Atoms take priority — hitting an atom
        # at a bond endpoint behaves like a normal grab-and-drag.)
        if atom_item is None:
            bond_item = self._bond_at(pos)
            if bond_item is not None:
                self._push(SetBondOrderCommand(self.scene, bond_item.bond.id, self.order))
                self.scene.rebuild()
                # Swallow the gesture: the next release must not create
                # a dangling stub at the click point.
                self._press_pos = None
                self._press_atom_id = None
                return

        self._press_pos = pos
        self._press_atom_id = atom_item.atom.id if atom_item is not None else None

    def mouse_move(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._press_pos is None:
            return
        # Compute the *would-be* start point so the preview tracks even
        # before we have a real atom committed (we don't create one until
        # release, to avoid polluting undo history with abandoned drags).
        start_x = self._press_pos.x()
        start_y = self._press_pos.y()
        if self._press_atom_id is not None:
            atom = self.scene.molecule.atoms[self._press_atom_id]
            start_x, start_y = atom.x, atom.y

        end_pos = event.scenePos()
        end_item = self._atom_at(end_pos)
        ex, ey, _ = self._resolve_endpoint(start_x, start_y, end_pos, end_item)
        self._show_preview(start_x, start_y, ex, ey)

    def mouse_release(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._press_pos is None:
            return
        end_pos = event.scenePos()
        end_item = self._atom_at(end_pos)

        # Materialize the start atom if we started on empty canvas.
        start_id = self._press_atom_id
        if start_id is None:
            cmd = AddAtomCommand(self.scene, "C", self._press_pos.x(), self._press_pos.y())
            self._push(cmd)
            start_id = cmd.created_atom_id

        start_atom = self.scene.molecule.atoms[start_id]
        sx, sy = start_atom.x, start_atom.y

        # Decide whether the user dragged at all. A near-zero-distance
        # release should grow a new bond off the start atom in a sensible
        # default direction (not snap to the original click position, which
        # could leave the new atom on top of the old one). A click that
        # lands back on the *same* atom as the press (i.e. no drag off the
        # atom) is also treated as a click, so tapping the end of an
        # existing bond grows a fresh bond off it.
        dx = end_pos.x() - self._press_pos.x()
        dy = end_pos.y() - self._press_pos.y()
        is_click = math.hypot(dx, dy) < CLICK_THRESHOLD
        click_on_start_atom = is_click and end_item is not None and end_item.atom.id == start_id

        if is_click and (end_item is None or click_on_start_atom):
            angle = self._click_extend_angle(start_id)
            ex, ey = free_endpoint_at_default_length(sx, sy, angle, length=DEFAULT_BOND_LENGTH)
            cmd = AddAtomCommand(self.scene, "C", ex, ey)
            self._push(cmd)
            end_id = cmd.created_atom_id
        elif end_item is not None:
            end_id = end_item.atom.id
        else:
            ex, ey, _ = self._resolve_endpoint(sx, sy, end_pos, None)
            cmd = AddAtomCommand(self.scene, "C", ex, ey)
            self._push(cmd)
            end_id = cmd.created_atom_id

        if start_id != end_id:
            # Avoid duplicate bonds — if a bond already exists between the
            # two atoms we leave it alone (the user can use the bond-order
            # hotkey to upgrade it).
            existing = next(
                (
                    b
                    for b in self.scene.molecule.bonds_for_atom(start_id)
                    if b.other_atom_id(start_id) == end_id
                ),
                None,
            )
            if existing is None:
                self._push(AddBondCommand(self.scene, start_id, end_id, self.order, self.stereo))

        self._hide_preview()
        self.scene.rebuild()
        self._press_atom_id = None
        self._press_pos = None

    # ----- internal -----------------------------------------------------

    def _click_extend_angle(self, tip_atom_id: int) -> float:
        """Pick the direction for a new bond when the user "taps to extend".

        - With no existing bonds on the tip, go up-right (textbook default).
        - With one neighbor, extend as a parallel-grandparent zigzag so
          repeated clicks trace ↗↘↗↘ instead of closing a hexagon.
        - With two-or-more neighbors, fall back to the generic largest-gap
          heuristic so tapping at a branching atom still picks a sensible
          empty wedge.
        """
        mol = self.scene.molecule
        tip = mol.atoms[tip_atom_id]
        incident = list(mol.bonds_for_atom(tip_atom_id))

        if len(incident) == 1:
            neighbor_id = incident[0].other_atom_id(tip_atom_id)
            neighbor = mol.atoms[neighbor_id]
            # Look up the neighbor's *other* neighbor (the tip's grandparent).
            grandparent = None
            for nb_bond in mol.bonds_for_atom(neighbor_id):
                candidate_id = nb_bond.other_atom_id(neighbor_id)
                if candidate_id != tip_atom_id:
                    grandparent = mol.atoms[candidate_id]
                    break
            if grandparent is not None:
                return zigzag_extension_angle(
                    tip.x, tip.y, neighbor.x, neighbor.y, grandparent.x, grandparent.y
                )
            return zigzag_extension_angle(tip.x, tip.y, neighbor.x, neighbor.y)

        # Zero or 2+ neighbors: the generic largest-gap heuristic.
        from bondforge.canvas.geometry import best_new_bond_angle, neighbor_angles

        neighbor_coords = [
            (mol.atoms[b.other_atom_id(tip_atom_id)].x, mol.atoms[b.other_atom_id(tip_atom_id)].y)
            for b in incident
        ]
        return best_new_bond_angle(neighbor_angles(tip.x, tip.y, neighbor_coords))

    def _push(self, cmd) -> None:
        if self.undo_stack is not None:
            self.undo_stack.push(cmd)
        else:
            cmd.redo()
