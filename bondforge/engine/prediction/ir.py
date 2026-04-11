"""Heuristic IR spectrum prediction.

Scans the molecule for known functional groups via RDKit SMARTS and
injects characteristic absorption bands as Gaussian lineshapes onto a
uniform wavenumber grid from 500 to 4000 cm⁻¹. The output is a
continuous ``%T`` curve (100 = no absorption, 0 = complete absorption)
suitable for rendering as a polyline in the viewer.

The table is intentionally coarse — half a dozen groups covering the
bands most chemists look at first. For a production IR predictor, a
quantum-chemistry calculation (e.g. via Psi4, ORCA, or Gaussian) would
be wired in as a worker.
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
    """A single IR band definition."""

    center: float  # cm⁻¹
    intensity: float  # 0..1 absorbance depth
    width: float  # cm⁻¹ half-width at half-maximum
    label: str


# SMARTS → list of bands. We deliberately use simple, unambiguous
# patterns so a sanitized mol is enough.
_IR_PATTERNS: list[tuple[str, list[_Band]]] = [
    # Hydroxyl (alcohol / acid broad).
    ("[OX2H]", [_Band(3350.0, 0.55, 150.0, "O–H stretch")]),
    # Carboxylic acid O–H (very broad).
    (
        "[CX3](=O)[OX2H1]",
        [
            _Band(3000.0, 0.50, 250.0, "acid O–H"),
            _Band(1710.0, 0.85, 30.0, "C=O (acid)"),
        ],
    ),
    # N–H amine/amide.
    ("[NX3;H2,H1]", [_Band(3400.0, 0.40, 80.0, "N–H stretch")]),
    # Aldehyde C–H.
    ("[CX3H1](=O)[#6]", [_Band(2720.0, 0.30, 30.0, "aldehyde C–H")]),
    # Nitrile C≡N.
    ("[CX2]#[NX1]", [_Band(2240.0, 0.60, 25.0, "C≡N stretch")]),
    # Alkyne C≡C.
    ("[CX2]#[CX2]", [_Band(2120.0, 0.25, 20.0, "C≡C stretch")]),
    # Ketone / ester / aldehyde C=O (generic).
    ("[CX3]=[OX1]", [_Band(1715.0, 0.80, 25.0, "C=O stretch")]),
    # Aromatic ring C=C.
    (
        "a1aaaaa1",
        [_Band(1600.0, 0.35, 30.0, "aromatic C=C"), _Band(1500.0, 0.30, 25.0, "aromatic C=C")],
    ),
    # Alkene C=C.
    ("[CX3]=[CX3]", [_Band(1650.0, 0.30, 25.0, "C=C stretch")]),
    # C–O alcohol / ether fingerprint.
    ("[CX4][OX2H0,OX2H1]", [_Band(1075.0, 0.55, 40.0, "C–O stretch")]),
    # Alkyl C–H (always present if any sp3 C).
    ("[CX4H]", [_Band(2950.0, 0.45, 40.0, "sp3 C–H stretch")]),
    # sp2 C–H.
    ("[cH,CX3H1]=[cX3,CX3]", [_Band(3050.0, 0.25, 30.0, "sp2 C–H stretch")]),
]


def _matches_any(rd: Chem.Mol, smarts: str) -> bool:
    patt = Chem.MolFromSmarts(smarts)
    if patt is None:
        return False
    return rd.HasSubstructMatch(patt)


def _transmittance(wavenumbers: list[float], bands: list[_Band]) -> list[float]:
    """Sum Gaussian absorbances into a %T curve on the wavenumber grid."""
    trans = [100.0] * len(wavenumbers)
    for band in bands:
        sigma = band.width / 2.355  # FWHM → σ
        for i, wn in enumerate(wavenumbers):
            dx = wn - band.center
            absorb = band.intensity * math.exp(-0.5 * (dx / sigma) ** 2)
            # Compose absorbances multiplicatively.
            trans[i] *= 1.0 - absorb
    return trans


def predict_ir(mol: Molecule, *, title: str = "") -> Spectrum:
    """Predict a continuous IR transmittance spectrum for ``mol``."""
    # Build a uniform 501-point grid from 500 to 4000 cm⁻¹.
    n = 501
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
        for smarts, bands in _IR_PATTERNS:
            if _matches_any(rd, smarts):
                matched_bands.extend(bands)
                for b in bands:
                    peaks.append(
                        Peak(x=b.center, intensity=100.0 - b.intensity * 100, label=b.label)
                    )

    transmittance = _transmittance(wavenumbers, matched_bands)

    return Spectrum(
        id=0,
        spectrum_type=SpectrumType.IR,
        x_values=wavenumbers,
        y_values=transmittance,
        peaks=peaks,
        title=title or "Predicted IR",
        origin="predicted",
        metadata={"resolution": "8 cm⁻¹", "sample": "neat"},
    )


__all__ = ["predict_ir"]
