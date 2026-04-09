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
from bondforge.canvas.export import export_pdf, export_png, export_svg
from bondforge.canvas.hotkeys import HotkeyDispatcher
from bondforge.canvas.scene import BondForgeScene
from bondforge.canvas.styles import STYLES, apply_style
from bondforge.canvas.tools import ArrowTool, AtomTool, BondTool, RingTool, TextTool
from bondforge.canvas.view import BondForgeView
from bondforge.core.commands import (
    AddAtomCommand,
    AddBondCommand,
    CleanupStructureCommand,
)
from bondforge.core.io import (
    RxnExportError,
    load_bforge,
    read_mol_file,
    read_smiles,
    save_bforge,
    write_mol_file,
    write_rxn_file,
    write_smiles,
)
from bondforge.core.io.pdb import write_pdb_file
from bondforge.core.io.xyz import write_xyz_file
from bondforge.core.model.arrow import ArrowKind
from bondforge.core.model.bond import BondOrder, BondStereo
from bondforge.core.model.molecule import Molecule
from bondforge.ui.dialogs.name_to_structure import NameToStructureDialog
from bondforge.ui.inspectors.properties_panel import PropertiesPanel

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
            "text": TextTool(self._scene, self._undo_stack),
        }

        # Cached 3D conformer (generated on demand, cleared on model change).
        self._conformer_mol = None
        self._viewer_3d = None

        self._props_panel = PropertiesPanel(self._scene, self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._props_panel)

        self._build_menus()
        self._build_toolbar()
        self._scene.set_tool(self._tools["bond"])
        self._scene.model_changed.connect(self._on_model_changed)

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
        save_bforge_action = QAction(
            "Save &BondForge…", self, shortcut="Ctrl+Shift+S", triggered=self._save_bforge
        )
        open_bforge_action = QAction(
            "Open Bond&Forge…", self, shortcut="Ctrl+Shift+O", triggered=self._open_bforge
        )
        export_png_action = QAction("Export &PNG…", self, triggered=self._export_png)
        export_svg_action = QAction("Export &SVG…", self, triggered=self._export_svg)
        export_pdf_action = QAction("Export P&DF…", self, triggered=self._export_pdf)
        export_rxn_action = QAction("Export &RXN…", self, triggered=self._export_rxn)
        quit_action = QAction(
            "&Quit", self, shortcut=QKeySequence.StandardKey.Quit, triggered=self.close
        )
        for a in (new_action, open_action, save_action):
            file_menu.addAction(a)
        file_menu.addSeparator()
        file_menu.addAction(save_bforge_action)
        file_menu.addAction(open_bforge_action)
        file_menu.addSeparator()
        file_menu.addAction(export_png_action)
        file_menu.addAction(export_svg_action)
        file_menu.addAction(export_pdf_action)
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

        view_menu = menu.addMenu("&View")
        toggle_props = self._props_panel.toggleViewAction()
        toggle_props.setText("&Properties Panel")
        view_menu.addAction(toggle_props)
        view_menu.addSeparator()
        style_menu = view_menu.addMenu("&Journal Style")
        style_group = QActionGroup(self)
        style_group.setExclusive(True)
        for style_name, style in STYLES.items():
            action = QAction(style_name, self, checkable=True)
            action.triggered.connect(
                lambda _checked=False, s=style: apply_style(self._scene, s)
            )
            style_group.addAction(action)
            style_menu.addAction(action)
            if style_name == "Default":
                action.setChecked(True)

        insert_menu = menu.addMenu("&Insert")
        insert_text_action = QAction(
            "&Text Annotation",
            self,
            shortcut="Ctrl+T",
            triggered=lambda: self._activate_tool("text"),
        )
        insert_menu.addAction(insert_text_action)

        structure_menu = menu.addMenu("&Structure")
        cleanup_action = QAction(
            "&Clean Up Structure",
            self,
            shortcut="Ctrl+Shift+K",
            triggered=self._cleanup_structure,
        )
        structure_menu.addAction(cleanup_action)
        structure_menu.addSeparator()
        view_3d_action = QAction(
            "&3D Viewer…",
            self,
            shortcut="Ctrl+Shift+3",
            triggered=self._show_3d_viewer,
        )
        minimize_action = QAction(
            "&Minimize (MMFF94)…",
            self,
            triggered=self._minimize_3d,
        )
        export_xyz_action = QAction("Export &XYZ…", self, triggered=self._export_xyz)
        export_pdb_action = QAction("Export P&DB…", self, triggered=self._export_pdb)
        structure_menu.addAction(view_3d_action)
        structure_menu.addAction(minimize_action)
        structure_menu.addSeparator()
        structure_menu.addAction(export_xyz_action)
        structure_menu.addAction(export_pdb_action)

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
            ("text", "Text"),
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
            "All supported (*.mol *.smi *.smiles *.bforge);;Molecules (*.mol *.smi *.smiles);;BondForge (*.bforge);;All files (*)",
        )
        if not path:
            return
        try:
            if path.endswith(".bforge"):
                doc = load_bforge(path)
                self._scene.set_document(doc)
                self._undo_stack.clear()
                return
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

    def _save_bforge(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save BondForge file", "", "BondForge file (*.bforge)"
        )
        if not path:
            return
        if not path.endswith(".bforge"):
            path += ".bforge"
        try:
            save_bforge(self._scene.document, path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save failed", str(exc))

    def _open_bforge(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open BondForge file", "", "BondForge file (*.bforge);;All files (*)"
        )
        if not path:
            return
        try:
            doc = load_bforge(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Open failed", str(exc))
            return
        self._scene.set_document(doc)
        self._undo_stack.clear()

    def _export_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", "", "PDF document (*.pdf)")
        if not path:
            return
        if not path.endswith(".pdf"):
            path += ".pdf"
        export_pdf(self._scene, path)

    def _on_model_changed(self) -> None:
        # Invalidate cached conformer whenever the 2D model changes.
        self._conformer_mol = None

    def _generate_conformer(self):
        """Generate or return cached 3D conformer. Returns None on failure."""
        if self._conformer_mol is not None:
            return self._conformer_mol
        from bondforge.engine.conformer import ConformerError, generate_conformer

        try:
            self._conformer_mol = generate_conformer(self._scene.molecule)
        except ConformerError as exc:
            QMessageBox.warning(self, "Conformer generation failed", str(exc))
            return None
        return self._conformer_mol

    def _show_3d_viewer(self) -> None:
        mol3d = self._generate_conformer()
        if mol3d is None:
            return
        from bondforge.ui.viewers.viewer_3d import Viewer3D

        if self._viewer_3d is None or not self._viewer_3d.isVisible():
            self._viewer_3d = Viewer3D()
            self._viewer_3d.setWindowTitle("BondForge — 3D Viewer")
            self._viewer_3d.resize(600, 500)
        self._viewer_3d.set_molecule(mol3d)
        self._viewer_3d.show()
        self._viewer_3d.raise_()

    def _minimize_3d(self) -> None:
        mol3d = self._generate_conformer()
        if mol3d is None:
            return
        from bondforge.engine.forcefield import MinimizationError, minimize

        try:
            result = minimize(mol3d)
        except MinimizationError as exc:
            QMessageBox.warning(self, "Minimization failed", str(exc))
            return
        status = "converged" if result.converged else "did NOT converge"
        QMessageBox.information(
            self,
            "Minimization complete",
            f"Force field: {result.force_field}\n"
            f"Energy: {result.energy:.2f} kcal/mol\n"
            f"Status: {status}",
        )
        # Refresh the 3D viewer if open.
        if self._viewer_3d is not None and self._viewer_3d.isVisible():
            self._viewer_3d.set_molecule(mol3d)

    def _export_xyz(self) -> None:
        mol3d = self._generate_conformer()
        if mol3d is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export XYZ", "", "XYZ file (*.xyz)")
        if not path:
            return
        if not path.endswith(".xyz"):
            path += ".xyz"
        write_xyz_file(mol3d, path, comment="Generated by BondForge")

    def _export_pdb(self) -> None:
        mol3d = self._generate_conformer()
        if mol3d is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export PDB", "", "PDB file (*.pdb)")
        if not path:
            return
        if not path.endswith(".pdb"):
            path += ".pdb"
        write_pdb_file(mol3d, path)

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
