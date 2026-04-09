"""Nucleus-style hotkey dispatcher.

ChemDraw popularized a keyboard interaction where you hover the cursor
over an atom and tap a single key to mutate that atom in place — ``n``
turns it into nitrogen, ``o`` into oxygen, ``+``/``-`` adjusts the formal
charge, ``1``/``2``/``3`` cycles the bond order under the cursor, and so
on. This module wires up that pattern on top of the BondForge command
infrastructure so all hotkey edits go through the undo stack.

The dispatcher is intentionally framework-light: it just takes a key
string, modifier flags, and a scene-space cursor position, and translates
those into a ``QUndoCommand``. The ``BondForgeView`` is the only thing
that knows how to feed it real Qt events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bondforge.canvas.items.atom_item import AtomItem
from bondforge.canvas.items.bond_item import BondItem
from bondforge.core.commands import (
    AddAtomCommand,
    ChangeElementCommand,
    CycleBondOrderCommand,
    DeleteSelectionCommand,
    SetAtomMapNumberCommand,
    SetChargeCommand,
)

if TYPE_CHECKING:
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QUndoStack

    from bondforge.canvas.scene import BondForgeScene


# Lowercase letter -> element symbol. Matches the most common ChemDraw
# nucleus keys. ``h`` is intentionally included so users can promote a
# carbon to an explicit hydrogen for diagram clarity.
ELEMENT_HOTKEYS: dict[str, str] = {
    "c": "C",
    "n": "N",
    "o": "O",
    "s": "S",
    "p": "P",
    "f": "F",
    "h": "H",
    "b": "B",
    "i": "I",
    "k": "K",
}

# Multi-character symbols accessed via Shift+letter. We keep the table here
# (rather than in templates.py) because the dispatcher needs to know which
# keys are reserved for elements vs. functional groups.
SHIFT_ELEMENT_HOTKEYS: dict[str, str] = {
    "L": "Cl",  # shift+l -> Cl
    "R": "Br",  # shift+r -> Br
    "I": "Si",  # shift+i -> Si
    "E": "Se",  # shift+e -> Se
    "M": "Mg",  # shift+m -> Mg
    "Z": "Zn",  # shift+z -> Zn
}


class HotkeyDispatcher:
    """Translate keystrokes into undoable model edits."""

    def __init__(self, scene: BondForgeScene, undo_stack: QUndoStack | None = None) -> None:
        self._scene = scene
        self._undo_stack = undo_stack

    def set_undo_stack(self, undo_stack: QUndoStack | None) -> None:
        self._undo_stack = undo_stack

    # ----- entry point --------------------------------------------------

    def handle_key(self, key_text: str, scene_pos: QPointF, *, shift: bool = False) -> bool:
        """Handle one keystroke. Returns True if anything happened."""
        if not key_text:
            return False

        atom_item = self._atom_at(scene_pos)
        bond_item = None if atom_item is not None else self._bond_at(scene_pos)

        # Bond-order cycle: 1, 2, 3 over a bond.
        if bond_item is not None and key_text in ("1", "2", "3"):
            order_index = int(key_text)
            return self._push(CycleBondOrderCommand(self._scene, bond_item.bond.id, order_index))

        # Charge: +/- adjusts the atom under the cursor.
        if key_text in ("+", "=") and atom_item is not None:
            return self._push(SetChargeCommand(self._scene, atom_item.atom.id, +1))
        if key_text in ("-", "_") and atom_item is not None:
            return self._push(SetChargeCommand(self._scene, atom_item.atom.id, -1))

        # Delete / Backspace removes the atom under the cursor.
        if key_text in ("\x7f", "\b") and atom_item is not None:
            return self._push(DeleteSelectionCommand(self._scene, [atom_item.atom.id]))

        # Atom-atom reaction mapping: lowercase m stamps the next sequential
        # map number on the atom under the cursor. Uppercase M (shift+m) is
        # reserved for Mg and is handled below.
        if key_text == "m" and not shift and atom_item is not None:
            return self._push(
                SetAtomMapNumberCommand(
                    self._scene,
                    atom_item.atom.id,
                    self._next_map_number(),
                )
            )

        # Element keys.
        element = self._element_for(key_text, shift=shift)
        if element is not None:
            return self._handle_element(element, atom_item, scene_pos)

        return False

    def _next_map_number(self) -> int:
        """Return the next unused reaction atom-map number in the scene."""
        used = {atom.map_number for atom in self._scene.molecule.iter_atoms() if atom.map_number}
        n = 1
        while n in used:
            n += 1
        return n

    # ----- helpers ------------------------------------------------------

    def _element_for(self, key: str, *, shift: bool) -> str | None:
        if shift:
            up = key.upper()
            if up in SHIFT_ELEMENT_HOTKEYS:
                return SHIFT_ELEMENT_HOTKEYS[up]
        return ELEMENT_HOTKEYS.get(key.lower())

    def _handle_element(self, element: str, atom_item: AtomItem | None, scene_pos: QPointF) -> bool:
        if atom_item is not None:
            return self._push(ChangeElementCommand(self._scene, atom_item.atom.id, element))
        return self._push(AddAtomCommand(self._scene, element, scene_pos.x(), scene_pos.y()))

    def _atom_at(self, pos: QPointF) -> AtomItem | None:
        view = self._scene.views()[0] if self._scene.views() else None
        transform = view.transform() if view is not None else None
        item = self._scene.itemAt(pos, transform) if transform is not None else None
        return item if isinstance(item, AtomItem) else None

    def _bond_at(self, pos: QPointF) -> BondItem | None:
        view = self._scene.views()[0] if self._scene.views() else None
        transform = view.transform() if view is not None else None
        item = self._scene.itemAt(pos, transform) if transform is not None else None
        return item if isinstance(item, BondItem) else None

    def _push(self, cmd) -> bool:
        if self._undo_stack is not None:
            self._undo_stack.push(cmd)
        else:
            cmd.redo()
        return True


__all__ = ["HotkeyDispatcher", "ELEMENT_HOTKEYS", "SHIFT_ELEMENT_HOTKEYS"]
