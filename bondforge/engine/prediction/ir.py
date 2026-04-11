"""Heuristic IR spectrum prediction.

Scans the molecule for known functional groups via RDKit SMARTS and
sums Gaussian absorbances onto a uniform 4 cm⁻¹ wavenumber grid from
500 to 4000 cm⁻¹. The result is a continuous %T curve (100 = no
absorption, 0 = full absorption) suitable for rendering as a polyline.

The table is intentionally pragmatic — about a dozen and a half
functional groups covering the bands chemists look at first. Each
match contributes one or more Gaussian bands at characteristic
wavenumbers, with width and depth tuned roughly to literature spectra.

Highlights of the v0.7 overhaul
-------------------------------

- C=O is differentiated by neighbour environment: aldehyde, ketone,
  ester, acid, amide each get a distinct centre.
- Nitro, imine, sulfoxide, sulfonyl, and phosphate stretches added.
- sp3, sp2 (vinyl), sp2 (aromatic), and sp (alkyne) C-H stretches
  are now separate matches with separate centres.
- Multiplicative absorbance composition is replaced by an additive
  scheme that's then converted to %T = 100·exp(-A), so transmittance
  is always clamped to (0, 100] and overlapping bands behave like
  real Beer's-law spectra.
- Bands are sorted into "diagnostic" priority for labelling so the
  spectrum viewer's top-N labels actually pick out the chemically
  interesting peaks instead of whichever group happened to be first.

This is still a heuristic. For research use, wire up a real
quantum-chemistry calculation (Psi4 / ORCA / Gaussian) as a worker.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from rdkit import Chem

from bondforge.core.model.molecule import Molecule
from bondforge.core.model.spectrum import Peak, Spectrum, SpectrumType
from bondforge.engine.rdkit_adapter import molecule_to_rwmol


@dataclass(frozen=True)
class _Band:
    """A single IR band definition.

    ``absorbance`` is a unitless Beer-Lambert depth (the higher, the
    deeper the dip). ``width`` is the FWHM in cm⁻¹. ``priority`` is
    used to sort labels — lower number = more diagnostic = more
    likely to get a label printed in the viewer.
    """

    center: float
    absorbance: float
    width: float
    label: str
    priority: int = 5


# (SMARTS, list of bands). Order matters only for the *first* match —
# more specific groups (carboxylic acid, ester, amide) are listed
# before the generic C=O so we can choose to suppress the generic
# match when a specific one already fired.
_IR_PATTERNS: list[tuple[str, list[_Band]]] = [
    # ---- O-H stretches -------------------------------------------------
    # Carboxylic acid O–H (very broad, overlaps C–H region).
    (
        "[CX3](=O)[OX2H1]",
        [
            _Band(2950.0, 0.55, 500.0, "O–H (acid, broad)", priority=2),
            _Band(1710.0, 1.10, 30.0, "C=O (acid)", priority=1),
            _Band(1280.0, 0.40, 30.0, "C–O (acid)", priority=4),
        ],
    ),
    # Alcohol / phenol O–H.
    ("[OX2H1]", [_Band(3350.0, 0.65, 200.0, "O–H stretch", priority=2)]),
    # ---- N-H stretches -------------------------------------------------
    # Primary amine — two bands (sym + asym).
    (
        "[NX3;H2]",
        [
            _Band(3380.0, 0.35, 60.0, "N–H asym", priority=3),
            _Band(3290.0, 0.30, 60.0, "N–H sym", priority=3),
        ],
    ),
    # Secondary amine / amide — single band.
    ("[NX3;H1]", [_Band(3320.0, 0.30, 70.0, "N–H stretch", priority=3)]),
    # ---- Aldehyde / ester / amide / ketone C=O -------------------------
    # Aldehyde — distinctive 2720 + 2820 doublet plus C=O.
    (
        "[CX3H1](=O)[#6]",
        [
            _Band(2820.0, 0.30, 25.0, "aldehyde C–H", priority=2),
            _Band(2720.0, 0.32, 25.0, "aldehyde C–H", priority=2),
            _Band(1725.0, 1.05, 25.0, "C=O (aldehyde)", priority=1),
        ],
    ),
    # Ester — sharp C=O at 1735 + strong C–O at 1200.
    (
        "[CX3](=O)[OX2][#6]",
        [
            _Band(1735.0, 1.05, 25.0, "C=O (ester)", priority=1),
            _Band(1200.0, 0.55, 35.0, "C–O (ester)", priority=4),
        ],
    ),
    # Amide — C=O around 1670 + N–H bend at 1550.
    (
        "[CX3](=[OX1])[NX3]",
        [
            _Band(1670.0, 0.95, 35.0, "C=O (amide I)", priority=1),
            _Band(1540.0, 0.45, 30.0, "N–H bend (amide II)", priority=3),
        ],
    ),
    # Ketone (must not be aldehyde, ester, acid, amide). The "no H,
    # both neighbours C" requirement is encoded in SMARTS.
    (
        "[#6][CX3](=[OX1])[#6]",
        [_Band(1715.0, 1.00, 25.0, "C=O (ketone)", priority=1)],
    ),
    # ---- Nitrile, alkyne, isocyanate -----------------------------------
    ("[CX2]#[NX1]", [_Band(2245.0, 0.55, 20.0, "C≡N stretch", priority=1)]),
    (
        "[CX2H]#[CX2]",
        [
            _Band(3300.0, 0.45, 25.0, "≡C–H stretch", priority=2),
            _Band(2120.0, 0.20, 20.0, "C≡C stretch", priority=2),
        ],
    ),
    ("[NX2]=[CX2]=[OX1]", [_Band(2270.0, 0.70, 30.0, "N=C=O stretch", priority=1)]),
    # ---- Nitro and N=O -------------------------------------------------
    (
        "[NX3](=O)=O",
        [
            _Band(1530.0, 0.75, 25.0, "NO₂ asym", priority=1),
            _Band(1350.0, 0.65, 25.0, "NO₂ sym", priority=1),
        ],
    ),
    (
        "[#6][NX3+](=O)[O-]",
        [
            _Band(1530.0, 0.75, 25.0, "NO₂ asym", priority=1),
            _Band(1350.0, 0.65, 25.0, "NO₂ sym", priority=1),
        ],
    ),
    # Imine C=N.
    ("[CX3]=[NX2]", [_Band(1660.0, 0.45, 25.0, "C=N stretch", priority=2)]),
    # ---- Sulfur and phosphorus oxygen ----------------------------------
    ("[#16X3]=[OX1]", [_Band(1050.0, 0.60, 30.0, "S=O (sulfoxide)", priority=2)]),
    (
        "[#16X4](=[OX1])(=[OX1])",
        [
            _Band(1340.0, 0.65, 25.0, "SO₂ asym", priority=2),
            _Band(1150.0, 0.60, 25.0, "SO₂ sym", priority=2),
        ],
    ),
    ("[PX4]=[OX1]", [_Band(1250.0, 0.55, 30.0, "P=O stretch", priority=2)]),
    # ---- Aromatic ring -------------------------------------------------
    (
        "c1ccccc1",
        [
            _Band(3050.0, 0.20, 25.0, "aromatic C–H", priority=4),
            _Band(1600.0, 0.35, 25.0, "aromatic C=C", priority=3),
            _Band(1500.0, 0.30, 25.0, "aromatic C=C", priority=3),
            _Band(750.0, 0.40, 30.0, "aromatic C–H bend", priority=4),
        ],
    ),
    # ---- Alkene C=C and =C-H -------------------------------------------
    (
        "[CX3]=[CX3]",
        [
            _Band(3080.0, 0.18, 25.0, "=C–H stretch", priority=4),
            _Band(1645.0, 0.35, 25.0, "C=C stretch", priority=3),
        ],
    ),
    # ---- Ether / alcohol C–O -------------------------------------------
    ("[CX4][OX2H0]", [_Band(1100.0, 0.55, 40.0, "C–O–C stretch", priority=4)]),
    ("[CX4][OX2H1]", [_Band(1050.0, 0.55, 40.0, "C–O stretch", priority=4)]),
    # ---- C-H stretches --------------------------------------------------
    # sp3 alkyl C–H (always present if any sp3 C-H).
    ("[CX4;H1,H2,H3]", [_Band(2925.0, 0.45, 50.0, "sp³ C–H stretch", priority=5)]),
    # CH3 doublet around 1380/1460.
    (
        "[CH3]",
        [
            _Band(1455.0, 0.20, 30.0, "CH₂/CH₃ bend", priority=5),
            _Band(1375.0, 0.18, 25.0, "CH₃ bend", priority=5),
        ],
    ),
]

# A few SMARTS we suppress the generic C=O for, because a more specific
# group already produced its own carbonyl band.
_GENERIC_CARBONYL_SUPPRESSORS = [
    "[CX3](=O)[OX2H1]",
    "[CX3H1](=O)[#6]",
    "[CX3](=O)[OX2][#6]",
    "[CX3](=[OX1])[NX3]",
    "[#6][CX3](=[OX1])[#6]",
]


def _matches_any(rd: Chem.Mol, smarts: str) -> bool:
    patt = Chem.MolFromSmarts(smarts)
    if patt is None:
        return False
    return rd.HasSubstructMatch(patt)


def _gaussian_absorbance(wavenumbers: list[float], bands: list[_Band]) -> list[float]:
    """Sum each band's Gaussian contribution to the total absorbance grid."""
    absorbance = [0.0] * len(wavenumbers)
    for band in bands:
        sigma = band.width / 2.355  # FWHM → σ
        two_sigma_sq = 2.0 * sigma * sigma
        for i, wn in enumerate(wavenumbers):
            dx = wn - band.center
            if abs(dx) > 4 * band.width:
                continue  # outside the band's tail; skip for speed
            absorbance[i] += band.absorbance * math.exp(-(dx * dx) / two_sigma_sq)
    return absorbance


def _to_transmittance(absorbance: list[float]) -> list[float]:
    """Convert summed absorbance into a Beer-Lambert %T trace."""
    # %T = 100 · 10^(-A). exp(-A·ln10) is equivalent and a tad faster.
    out: list[float] = []
    ln10 = math.log(10)
    for a in absorbance:
        t = 100.0 * math.exp(-a * 0.65 * ln10)  # 0.65 keeps depths reasonable
        if t < 0.5:
            t = 0.5  # never let the trace touch the floor
        if t > 100.0:
            t = 100.0
        out.append(t)
    return out


def predict_ir(mol: Molecule, *, title: str = "") -> Spectrum:
    """Predict a continuous IR transmittance spectrum for ``mol``.

    Returns a :class:`Spectrum` with 876 points (4 cm⁻¹ resolution from
    500 to 4000 cm⁻¹), an annotated peak list of every diagnostic
    band, and metadata describing the assumed sample form.
    """
    # 4 cm⁻¹ resolution → 876 points across 500–4000 cm⁻¹.
    n = 876
    wavenumbers = [500.0 + i * (4000.0 - 500.0) / (n - 1) for i in range(n)]

    rd = None
    if mol.atoms:
        rw = molecule_to_rwmol(mol)
        try:
            Chem.SanitizeMol(rw)
            rd = rw.GetMol()
        except Exception:
            rd = None

    matched_bands: list[_Band] = []
    peaks: list[Peak] = []

    if rd is not None:
        # Determine whether to suppress the generic C=O entry.
        suppress_generic_carbonyl = any(_matches_any(rd, s) for s in _GENERIC_CARBONYL_SUPPRESSORS)
        seen_labels: set[tuple[float, str]] = set()
        for smarts, bands in _IR_PATTERNS:
            if not _matches_any(rd, smarts):
                continue
            # Skip plain C=O if a specific carbonyl group already matched.
            if smarts == "[CX3]=[OX1]" and suppress_generic_carbonyl:
                continue
            for band in bands:
                # Avoid double-listing the same labelled peak (same
                # centre + label) in the peak table.
                key = (round(band.center, 1), band.label)
                if key in seen_labels:
                    continue
                seen_labels.add(key)
                matched_bands.append(band)
                # %T at the band centre — for the label.
                depth = 100.0 * math.exp(-band.absorbance * 0.65 * math.log(10))
                peaks.append(
                    Peak(
                        x=band.center,
                        intensity=max(depth, 1.0),
                        label=band.label,
                        # Stash priority in multiplicity slot for the
                        # viewer's label sorter (low = more important).
                        multiplicity=str(band.priority),
                    )
                )

    absorbance = _gaussian_absorbance(wavenumbers, matched_bands)
    transmittance = _to_transmittance(absorbance)

    return Spectrum(
        id=0,
        spectrum_type=SpectrumType.IR,
        x_values=wavenumbers,
        y_values=transmittance,
        peaks=peaks,
        title=title or "Predicted IR",
        origin="predicted",
        metadata={
            "resolution": "4 cm⁻¹",
            "sample": "neat (predicted)",
            "range": "500–4000 cm⁻¹",
        },
    )


__all__ = ["predict_ir"]
