# BondForge

> Free and open-source desktop alternative to ChemDraw, for students and educators.

BondForge is an early-stage chemistry drawing application built on **PySide6 (Qt for Python)** and **RDKit**. It targets Windows and macOS, ships under **GPL-3.0-or-later**, and aims for full ChemDraw feature parity over a series of phased releases.

## Status

**Pre-alpha (v0.1).** What works today:

- Click-and-drag drawing of atoms, bonds, and rings
- Carbon-implicit vertices, charges, and basic stereo wedges
- MOL (V2000/V3000) and SMILES read/write
- PNG and SVG export
- Undo/redo via the Qt undo stack
- Round-trip with RDKit for sanitization, aromaticity, and canonical SMILES

The roadmap below tracks how we get from this skeleton to ChemDraw parity.

## Why?

ChemDraw is the de facto standard chemistry drawing tool but is proprietary, expensive, and a recurring pain point for students who lose access when their institution's license lapses. BondForge exists so that anyone can draw and share publication-quality chemistry without paying a subscription.

## Roadmap

| Version | Theme | Highlights |
|---------|-------|------------|
| **v0.1** | Skeleton | Window, canvas, atom/bond/ring tools, MOL+SMILES IO, PNG export, undo |
| v0.2 | Drawing core | Nucleus hotkeys, full template palette, stereo wedges, brackets, charges, isotopes, structure clean-up |
| v0.3 | Reactions & naming | Reaction arrows, atom mapping, electron-pushing curved arrows, RXN export, OPSIN Name→Structure, STOUT Structure→Name (experimental) |
| v0.4 | Properties & 3D | MW/formula/logP/pKa/TPSA, embedded 3Dmol.js viewer, ETKDG conformers, MMFF94 minimization, XYZ/PDB |
| v0.5 | Documents | Multi-page, rich text, tables, journal styles, PDF/SVG export, native `.bforge` format |
| v0.6 | BioDraw / HELM | Peptide/DNA/RNA editor, monomer palette, HELM IO, antibody templates |
| v0.7 | Spectra | NMRium embedded viewer, JCAMP-DX, 1H/13C prediction |
| v1.0 | Polish | PubChem search, Office clipboard interop, signed installers, plugin API |

## Known parity gaps

- **Structure-to-Name (IUPAC)** is genuinely unsolved in the open-source world. OPSIN goes Name→Structure beautifully but not the other direction. We plan to ship STOUT (an ML model, ~95% accurate on common molecules) behind an "experimental" label.
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
