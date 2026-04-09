"""BondForge main window.

Hosts the canvas as the central widget, exposes File/Edit/View menus,
and wires up the active drawing tool. v0.1 ships with the bond tool
selected by default and the ring tool, atom tool, and selection tool
toggleable from the toolbar.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QUndoStack
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QToolBar,
)

from bondforge import __version__
from bondforge.canvas.export import export_png, export_svg
from bondforge.canvas.hotkeys import HotkeyDispatcher
from bondforge.canvas.scene import BondForgeScene
from bondforge.canvas.tools import ArrowTool, AtomTool, BondTool, RingTool
from bondforge.canvas.view import BondForgeView
from bondforge.core.commands import (
    AddAtomCommand,
    AddBondCommand,
    CleanupStructureCommand,
)
from bondforge.core.io import (
    RxnExportError,
    read_mol_file,
    read_smiles,
    write_mol_file,
    write_rxn_file,
    write_smiles,
)
from bondforge.core.model.arrow import ArrowKind
from bondforge.core.model.bond import BondOrder, BondStereo
from bondforge.core.model.molecule import Molecule
from bondforge.ui.dialogs.name_to_structure import NameToStructureDialog

if TYPE_CHECKING:
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent

    from bondforge.canvas.tools.base_tool import BaseTool


class _ToolDispatchScene(BondForgeScene):
    """Scene that forwards mouse events to the currently active tool."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._active_tool: BaseTool | None = None

    def set_tool(self, tool: BaseTool | None) -> None:
        if self._active_tool is not None:
            self._active_tool.deactivate()
        self._active_tool = tool
        if tool is not None:
            tool.activate()

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802 (Qt)
        if self._active_tool is not None and event.button() == Qt.MouseButton.LeftButton:
            self._active_tool.mouse_press(event)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802 (Qt)
        if self._active_tool is not None:
            self._active_tool.mouse_move(event)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802 (Qt)
        if self._active_tool is not None and event.button() == Qt.MouseButton.LeftButton:
            self._active_tool.mouse_release(event)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    """Top-level window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BondForge")
        self.resize(1100, 750)

        self._scene = _ToolDispatchScene(Molecule())
        self._view = BondForgeView(self._scene)
        self.setCentralWidget(self._view)

        self._undo_stack = QUndoStack(self)
        self._hotkeys = HotkeyDispatcher(self._scene, self._undo_stack)
        self._view.set_hotkey_dispatcher(self._hotkeys)

        self._tools: dict[str, BaseTool] = {
            "select": _NullTool(self._scene, self._undo_stack),
            "atom_c": AtomTool(self._scene, self._undo_stack, element="C"),
            "atom_n": AtomTool(self._scene, self._undo_stack, element="N"),
            "atom_o": AtomTool(self._scene, self._undo_stack, element="O"),
            "bond": BondTool(self._scene, self._undo_stack),
            "bond_double": BondTool(self._scene, self._undo_stack, order=BondOrder.DOUBLE),
            "bond_triple": BondTool(self._scene, self._undo_stack, order=BondOrder.TRIPLE),
            "wedge_up": BondTool(self._scene, self._undo_stack, stereo=BondStereo.WEDGE_UP),
            "wedge_down": BondTool(self._scene, self._undo_stack, stereo=BondStereo.WEDGE_DOWN),
            "ring3": RingTool(self._scene, self._undo_stack, size=3, aromatic=False),
            "ring4": RingTool(self._scene, self._undo_stack, size=4, aromatic=False),
            "ring5": RingTool(self._scene, self._undo_stack, size=5, aromatic=False),
            "ring6": RingTool(self._scene, self._undo_stack, size=6, aromatic=True),
            "ring7": RingTool(self._scene, self._undo_stack, size=7, aromatic=False),
            "ring8": RingTool(self._scene, self._undo_stack, size=8, aromatic=False),
            "arrow_fwd": ArrowTool(self._scene, self._undo_stack, kind=ArrowKind.FORWARD),
            "arrow_eq": ArrowTool(self._scene, self._undo_stack, kind=ArrowKind.EQUILIBRIUM),
            "arrow_retro": ArrowTool(self._scene, self._undo_stack, kind=ArrowKind.RETROSYNTHETIC),
            "arrow_pair": ArrowTool(self._scene, self._undo_stack, kind=ArrowKind.ELECTRON_PAIR),
            "arrow_radical": ArrowTool(
                self._scene, self._undo_stack, kind=ArrowKind.SINGLE_ELECTRON
            ),
        }

        self._build_menus()
        self._build_toolbar()
        self._scene.set_tool(self._tools["bond"])

    # ----- menus / toolbar ---------------------------------------------

    def _build_menus(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("&File")
        new_action = QAction(
            "&New", self, shortcut=QKeySequence.StandardKey.New, triggered=self._new_document
        )
        open_action = QAction(
            "&Open…", self, shortcut=QKeySequence.StandardKey.Open, triggered=self._open_file
        )
        save_action = QAction(
            "&Save As…", self, shortcut=QKeySequence.StandardKey.SaveAs, triggered=self._save_as
        )
        export_png_action = QAction("Export &PNG…", self, triggered=self._export_png)
        export_svg_action = QAction("Export &SVG…", self, triggered=self._export_svg)
        export_rxn_action = QAction("Export &RXN…", self, triggered=self._export_rxn)
        quit_action = QAction(
            "&Quit", self, shortcut=QKeySequence.StandardKey.Quit, triggered=self.close
        )
        for a in (new_action, open_action, save_action):
            file_menu.addAction(a)
        file_menu.addSeparator()
        file_menu.addAction(export_png_action)
        file_menu.addAction(export_svg_action)
        file_menu.addAction(export_rxn_action)
        file_menu.addSeparator()
        file_menu.addAction(quit_action)

        edit_menu = menu.addMenu("&Edit")
        undo_action = self._undo_stack.createUndoAction(self, "&Undo")
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        redo_action = self._undo_stack.createRedoAction(self, "&Redo")
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(undo_action)
        edit_menu.addAction(redo_action)

        menu.addMenu("&View")
        menu.addMenu("&Insert")

        structure_menu = menu.addMenu("&Structure")
        cleanup_action = QAction(
            "&Clean Up Structure",
            self,
            shortcut="Ctrl+Shift+K",
            triggered=self._cleanup_structure,
        )
        structure_menu.addAction(cleanup_action)

        tools_menu = menu.addMenu("&Tools")
        name_to_structure_action = QAction(
            "&Name to Structure…",
            self,
            shortcut="Ctrl+Shift+N",
            triggered=self._name_to_structure,
        )
        tools_menu.addAction(name_to_structure_action)

        help_menu = menu.addMenu("&Help")
        about_action = QAction("&About BondForge", self, triggered=self._about)
        help_menu.addAction(about_action)

    def _build_toolbar(self) -> None:
        bar = QToolBar("Tools", self)
        bar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, bar)
        group = QActionGroup(self)
        group.setExclusive(True)
        for key, label in (
            ("select", "Select"),
            ("bond", "Single"),
            ("bond_double", "Double"),
            ("bond_triple", "Triple"),
            ("wedge_up", "Wedge ▲"),
            ("wedge_down", "Hash ▽"),
            ("atom_c", "C"),
            ("atom_n", "N"),
            ("atom_o", "O"),
            ("ring3", "3-Ring"),
            ("ring4", "4-Ring"),
            ("ring5", "5-Ring"),
            ("ring6", "6-Ring"),
            ("ring7", "7-Ring"),
            ("ring8", "8-Ring"),
            ("arrow_fwd", "→"),
            ("arrow_eq", "⇌"),
            ("arrow_retro", "⇒"),
            ("arrow_pair", "↷ pair"),
            ("arrow_radical", "↷ rad"),
        ):
            action = QAction(label, self, checkable=True)
            action.triggered.connect(lambda _checked=False, k=key: self._activate_tool(k))
            group.addAction(action)
            bar.addAction(action)
            if key == "bond":
                action.setChecked(True)

    def _activate_tool(self, key: str) -> None:
        tool = self._tools.get(key)
        if tool is not None:
            self._scene.set_tool(tool)

    # ----- file actions -------------------------------------------------

    def _new_document(self) -> None:
        self._scene.set_molecule(Molecule())
        self._undo_stack.clear()

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open molecule",
            "",
            "Molecules (*.mol *.smi *.smiles);;All files (*)",
        )
        if not path:
            return
        try:
            if path.endswith((".smi", ".smiles")):
                text = Path(path).read_text(encoding="utf-8").strip().split()[0]
                mol = read_smiles(text)
            else:
                mol = read_mol_file(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Open failed", str(exc))
            return
        self._scene.set_molecule(mol)
        self._undo_stack.clear()

    def _save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save molecule",
            "",
            "MOL file (*.mol);;SMILES (*.smi)",
        )
        if not path:
            return
        try:
            if path.endswith(".smi"):
                Path(path).write_text(write_smiles(self._scene.molecule) + "\n", encoding="utf-8")
            else:
                if not path.endswith(".mol"):
                    path += ".mol"
                write_mol_file(self._scene.molecule, path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save failed", str(exc))

    def _export_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export PNG", "", "PNG image (*.png)")
        if not path:
            return
        if not path.endswith(".png"):
            path += ".png"
        export_png(self._scene, path)

    def _export_svg(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export SVG", "", "SVG image (*.svg)")
        if not path:
            return
        if not path.endswith(".svg"):
            path += ".svg"
        export_svg(self._scene, path)

    def _export_rxn(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export RXN", "", "MDL reaction file (*.rxn)")
        if not path:
            return
        if not path.endswith(".rxn"):
            path += ".rxn"
        try:
            write_rxn_file(self._scene.document, path)
        except RxnExportError as exc:
            QMessageBox.warning(self, "RXN export failed", str(exc))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "RXN export failed", str(exc))

    def _name_to_structure(self) -> None:
        from bondforge.engine.cleanup import compute_clean_2d_coords

        dialog = NameToStructureDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        mol = dialog.result_molecule()
        if mol is None or not mol.atoms:
            return

        # RDKit's raw 2D coordinates are ~1.5 units between bonds; the
        # clean-up pass rescales to DEFAULT_BOND_LENGTH and re-centers on
        # the old centroid (which for a fresh OPSIN molecule is near the
        # origin). That's exactly what we want for a "paste at origin"
        # import.
        compute_clean_2d_coords(mol)

        # Paste the returned molecule into the current document by issuing
        # one AddAtomCommand per atom and one AddBondCommand per bond,
        # all wrapped in a single undo macro so the user can undo the whole
        # import with one Ctrl+Z.
        self._undo_stack.beginMacro("Name to structure")
        id_map: dict[int, int] = {}
        try:
            for atom in mol.iter_atoms():
                cmd = AddAtomCommand(self._scene, atom.element, atom.x, atom.y)
                self._undo_stack.push(cmd)
                id_map[atom.id] = cmd.created_atom_id
                new_atom = self._scene.molecule.atoms[cmd.created_atom_id]
                new_atom.charge = atom.charge
                new_atom.isotope = atom.isotope
                new_atom.explicit_hydrogens = atom.explicit_hydrogens
                new_atom.radical_electrons = atom.radical_electrons
            for bond in mol.iter_bonds():
                self._undo_stack.push(
                    AddBondCommand(
                        self._scene,
                        id_map[bond.begin_atom_id],
                        id_map[bond.end_atom_id],
                        bond.order,
                        bond.stereo,
                    )
                )
        finally:
            self._undo_stack.endMacro()
        self._scene.rebuild()

    def _cleanup_structure(self) -> None:
        if not self._scene.molecule.atoms:
            return
        self._undo_stack.push(CleanupStructureCommand(self._scene))

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "About BondForge",
            f"<h3>BondForge {__version__}</h3>"
            "<p>Free and open-source ChemDraw alternative.</p>"
            "<p>Licensed under GPL-3.0-or-later.</p>",
        )


class _NullTool:
    """Placeholder selection tool: forwards events back to the scene."""

    def __init__(self, scene, undo_stack=None) -> None:
        self.scene = scene
        self.undo_stack = undo_stack

    def activate(self) -> None: ...
    def deactivate(self) -> None: ...
    def mouse_press(self, event) -> None: ...
    def mouse_move(self, event) -> None: ...
    def mouse_release(self, event) -> None: ...
