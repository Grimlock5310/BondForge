"""3D molecular viewer backed by 3Dmol.js inside a QWebEngineView.

The viewer accepts an RDKit ``Mol`` with a 3D conformer and renders it
using 3Dmol.js loaded from a CDN. Communication is one-way for v0.4:
we push a MOL block into the viewer's HTML; later versions can add a
QWebChannel for bidirectional interaction (e.g. picking atoms).

If ``QWebEngineWidgets`` is not installed the module still imports — it
just provides a placeholder widget that tells the user what to install.
"""

from __future__ import annotations

from rdkit import Chem

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView

    _HAS_WEBENGINE = True
except ImportError:
    _HAS_WEBENGINE = False

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {{ margin: 0; padding: 0; width: 100%%; height: 100%%;
               overflow: hidden; background: #f8f8f8; }}
  #viewer {{ width: 100%%; height: 100%%; position: absolute; }}
</style>
<script src="https://3dmol.csb.pitt.edu/build/3Dmol-min.js"></script>
</head>
<body>
<div id="viewer"></div>
<script>
  var viewer = $3Dmol.createViewer("viewer", {{
    backgroundColor: "0xf8f8f8"
  }});
  var molblock = `{mol_block}`;
  viewer.addModel(molblock, "sdf");
  viewer.setStyle({{}}, {{stick: {{radius: 0.15}}, sphere: {{scale: 0.25}}}});
  viewer.zoomTo();
  viewer.render();
</script>
</body>
</html>
"""


class Viewer3D(QWidget):
    """Widget that renders an RDKit 3D Mol via 3Dmol.js.

    Call :meth:`set_molecule` to push a new molecule into the viewer.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if _HAS_WEBENGINE:
            self._web = QWebEngineView()
            layout.addWidget(self._web)
        else:
            self._web = None
            label = QLabel(
                "QWebEngineView not available.\nInstall PySide6-WebEngine to enable the 3D viewer."
            )
            label.setWordWrap(True)
            layout.addWidget(label)

    def set_molecule(self, mol: Chem.Mol, *, conf_id: int = 0) -> None:
        """Render the given RDKit Mol with 3D coordinates."""
        if self._web is None:
            return
        mol_block = Chem.MolToMolBlock(mol, confId=conf_id)
        # Escape backticks in the MOL block for the JS template literal.
        mol_block = mol_block.replace("`", "\\`")
        html = _HTML_TEMPLATE.format(mol_block=mol_block)
        self._web.setHtml(html)

    def clear(self) -> None:
        """Clear the current display."""
        if self._web is not None:
            self._web.setHtml("")
