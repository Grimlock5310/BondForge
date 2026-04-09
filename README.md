# BondForge

> Free and open-source desktop alternative to ChemDraw, for students and educators.

BondForge is an early-stage chemistry drawing application built on **PySide6 (Qt for Python)** and **RDKit**. It targets Windows and macOS, ships under **GPL-3.0-or-later**, and aims for full ChemDraw feature parity over a series of phased releases.

## Status

**Pre-alpha (v0.3).** What works today:

- Click-and-drag drawing of atoms, bonds, and rings (3- through 8-membered)
- Click to extend a chain at a proper zigzag (bonds parallel to the grandparent)
- Click on an existing bond with the double/triple tool to change its order
- 30°-snapped angles and uniform bond lengths on every fresh bond
- Live preview line while dragging the bond tool
- Wedge / hash stereo bond tools
- Nucleus-style hotkeys: hover an atom and tap `n`/`o`/`s`/`f`/`b`/`i`/`k`/`p`,
  shift+`l`/`r`/`i`/`e`/`m`/`z` for `Cl`/`Br`/`Si`/`Se`/`Mg`/`Zn`,
  `+`/`-` to change formal charge, `1`/`2`/`3` to set bond order,
  `Delete` to remove the atom under the cursor, `m` to stamp the next
  sequential reaction-mapping number
- Whole-molecule structure clean-up (Ctrl+Shift+K) using RDKit's
  `Compute2DCoords`, scaled to the canvas's uniform bond length and
  re-centered on the original centroid
- Reaction arrows: forward (→), equilibrium (⇌), retrosynthetic (⇒), and
  curved electron-pushing arrows for lone-pair (full head) and radical
  (fish-hook) mechanisms
- MDL RXN V2000 export (arrow-direction projection splits the drawing into
  reactants and products)
- OPSIN Name→Structure dialog (Tools → Name to Structure…, Ctrl+Shift+N);
  requires the optional `naming` extra: `pip install bondforge[naming]`
- Carbon-implicit vertices, charge labels, reaction map-number labels
- MOL (V2000/V3000), SMILES, and RXN read/write
- PNG and SVG export
- Undo/redo via the Qt undo stack
- Round-trip with RDKit for sanitization, aromaticity, and canonical SMILES

The roadmap below tracks how we get from this skeleton to ChemDraw parity.

## Why?

ChemDraw is the de facto standard chemistry drawing tool but is proprietary, expensive, and a recurring pain point for students who lose access when their institution's license lapses. BondForge exists so that anyone can draw and share publication-quality chemistry without paying a subscription.

## Roadmap

| Version | Theme | Highlights |
|---------|-------|------------|
| v0.1 | Skeleton | Window, canvas, atom/bond/ring tools, MOL+SMILES IO, PNG export, undo |
| v0.2 | Drawing core | Nucleus hotkeys, snapping, uniform bond lengths, structure clean-up, wedge/hash bonds, ring set 3–8 |
| **v0.3** | Reactions & naming | Reaction arrows, atom mapping, electron-pushing curved arrows, RXN export, OPSIN Name→Structure |
| v0.4 | Properties & 3D | MW/formula/logP/pKa/TPSA, embedded 3Dmol.js viewer, ETKDG conformers, MMFF94 minimization, XYZ/PDB |
| v0.5 | Documents | Multi-page, rich text, tables, journal styles, PDF/SVG export, native `.bforge` format |
| v0.6 | BioDraw / HELM | Peptide/DNA/RNA editor, monomer palette, HELM IO, antibody templates |
| v0.7 | Spectra | NMRium embedded viewer, JCAMP-DX, 1H/13C prediction |
| v1.0 | Polish | PubChem search, Office clipboard interop, signed installers, plugin API |

## Known parity gaps

- **Structure-to-Name (IUPAC)** is genuinely unsolved in the open-source world. OPSIN (shipped in v0.3) goes Name→Structure beautifully but not the other direction. We plan to ship STOUT (an ML model, ~95% accurate on common molecules) behind an "experimental" label in a later release.
- **CDX binary format** has no public spec; we will support CDXML (XML) first and treat the legacy CDX as best-effort.
- **Cloud collaboration** (Signals ChemDraw) is out of scope until v1.x.

## Development

Requires Python 3.11+.

```bash
pip install -e ".[dev]"
pytest
python -m bondforge
```

## License

GPL-3.0-or-later. See `LICENSE`.

All bundled or required dependencies (RDKit BSD, OpenBabel GPL-2+, OPSIN MIT, NMRium MIT, 3Dmol.js BSD, STOUT MIT, HELM toolkit MIT) are compatible with GPL-3 redistribution.
