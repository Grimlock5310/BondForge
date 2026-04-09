"""Properties panel — a dock widget showing computed molecular descriptors.

The panel listens to the scene's ``model_changed`` signal and refreshes
automatically whenever atoms or bonds are added, removed, or mutated.
Properties that cannot be computed (e.g. on a partial drawing) are shown
as "—".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QFormLayout,
    QLabel,
    QWidget,
)

from bondforge.engine.properties import compute_properties

if TYPE_CHECKING:
    from bondforge.canvas.scene import BondForgeScene

_DASH = "—"


class PropertiesPanel(QDockWidget):
    """Side panel that auto-updates molecular properties."""

    def __init__(self, scene: BondForgeScene, parent: QWidget | None = None) -> None:
        super().__init__("Properties", parent)
        self._scene = scene
        self.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        container = QWidget()
        form = QFormLayout(container)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._formula = QLabel(_DASH)
        self._mw = QLabel(_DASH)
        self._exact_mass = QLabel(_DASH)
        self._logp = QLabel(_DASH)
        self._tpsa = QLabel(_DASH)
        self._hbd = QLabel(_DASH)
        self._hba = QLabel(_DASH)
        self._rot_bonds = QLabel(_DASH)
        self._heavy_atoms = QLabel(_DASH)
        self._rings = QLabel(_DASH)

        form.addRow("Formula:", self._formula)
        form.addRow("MW:", self._mw)
        form.addRow("Exact mass:", self._exact_mass)
        form.addRow("logP:", self._logp)
        form.addRow("TPSA:", self._tpsa)
        form.addRow("HBD:", self._hbd)
        form.addRow("HBA:", self._hba)
        form.addRow("Rot. bonds:", self._rot_bonds)
        form.addRow("Heavy atoms:", self._heavy_atoms)
        form.addRow("Rings:", self._rings)

        self.setWidget(container)

        scene.model_changed.connect(self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        props = compute_properties(self._scene.molecule)
        if props is None:
            for label in (
                self._formula,
                self._mw,
                self._exact_mass,
                self._logp,
                self._tpsa,
                self._hbd,
                self._hba,
                self._rot_bonds,
                self._heavy_atoms,
                self._rings,
            ):
                label.setText(_DASH)
            return
        self._formula.setText(props.formula)
        self._mw.setText(f"{props.molecular_weight:.2f}")
        self._exact_mass.setText(f"{props.exact_mass:.4f}")
        self._logp.setText(f"{props.logp:.2f}")
        self._tpsa.setText(f"{props.tpsa:.2f}")
        self._hbd.setText(str(props.hbd))
        self._hba.setText(str(props.hba))
        self._rot_bonds.setText(str(props.rotatable_bonds))
        self._heavy_atoms.setText(str(props.heavy_atom_count))
        self._rings.setText(str(props.ring_count))
