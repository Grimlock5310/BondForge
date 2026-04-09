"""3D molecular viewer backed by 3Dmol.js inside a QWebEngineView.

The viewer accepts an RDKit ``Mol`` with a 3D conformer and renders it
using 3Dmol.js loaded from a CDN. Communication is one-way for v0.4:
we push a MOL block into the viewer's HTML; later versions can add a
QWebChannel for bidirectional interaction (e.g. picking atoms).

If ``QWebEngineWidgets`` is not installed the module still imports — it
just provides a placeholder widget that tells the user what to install.

**Implementation note**: The HTML is written to a temporary file and
loaded via ``file://`` URL rather than ``setHtml()`` because Qt's web
engine blocks network requests from data-origin pages. Loading from
a ``file://`` origin allows the ``<script src="https://...">`` tag to
fetch 3Dmol.js from the CDN.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from rdkit import Chem

try:
    from PySide6.QtCore import QUrl
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
  html, body {{ margin: 0; padding: 0; width: 100%; height: 100%;
               overflow: hidden; background: #f8f8f8; font-family: sans-serif; }}
  #viewer {{ width: 100%; height: 100%; position: absolute; }}
  #loading {{ position: absolute; top: 50%; left: 50%;
              transform: translate(-50%, -50%); color: #888; font-size: 14px; }}
  #error {{ display: none; position: absolute; top: 50%; left: 50%;
            transform: translate(-50%, -50%); color: #c00; font-size: 13px;
            text-align: center; max-width: 80%; }}
</style>
</head>
<body>
<div id="viewer"></div>
<div id="loading">Loading 3Dmol.js…</div>
<div id="error">
  <p><b>Could not load 3Dmol.js</b></p>
  <p>The 3D viewer requires an internet connection to load the rendering
  library from the CDN. Check your network and try again.</p>
</div>
<script>
  // Timeout: if 3Dmol hasn't loaded in 8 seconds, show the error.
  var _loadTimer = setTimeout(function() {{
    document.getElementById("loading").style.display = "none";
    document.getElementById("error").style.display = "block";
  }}, 8000);
</script>
<script src="https://3dmol.csb.pitt.edu/build/3Dmol-min.js"
        onload="clearTimeout(_loadTimer); _initViewer();"
        onerror="clearTimeout(_loadTimer);
                 document.getElementById('loading').style.display='none';
                 document.getElementById('error').style.display='block';"></script>
<script>
function _initViewer() {{
  document.getElementById("loading").style.display = "none";
  var viewer = $3Dmol.createViewer("viewer", {{
    backgroundColor: "0xf8f8f8"
  }});
  var molblock = `{mol_block}`;
  viewer.addModel(molblock, "sdf");
  viewer.setStyle({{}}, {{stick: {{radius: 0.15}}, sphere: {{scale: 0.25}}}});
  viewer.zoomTo();
  viewer.render();
}}
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

        self._tmp_dir = tempfile.mkdtemp(prefix="bondforge_3d_")

        if _HAS_WEBENGINE:
            self._web = QWebEngineView()
            # Enable JavaScript and remote content access.
            settings = self._web.settings()
            from PySide6.QtWebEngineCore import QWebEngineSettings

            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            settings.setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
            )
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
        # Escape backticks and backslashes for the JS template literal.
        mol_block = mol_block.replace("\\", "\\\\").replace("`", "\\`")
        html = _HTML_TEMPLATE.format(mol_block=mol_block)
        # Write to a temp file so the page has a file:// origin and can
        # fetch the 3Dmol.js CDN script (data: origins block network).
        html_path = Path(self._tmp_dir) / "viewer.html"
        html_path.write_text(html, encoding="utf-8")
        self._web.load(QUrl.fromLocalFile(str(html_path)))

    def clear(self) -> None:
        """Clear the current display."""
        if self._web is not None:
            self._web.setHtml("")
