"""Heuristic mass spectrum prediction.

Emits a line spectrum with:

- A **molecular ion peak** (M⁺) at the monoisotopic mass.
- **Isotopologue peaks** at M+1, M+2 with heights computed from the
  natural abundance of ¹³C, ²H, ³⁴S, ³⁷Cl and ⁸¹Br.
- A handful of **fragment peaks** chosen from a tiny rule table:
  loss of H, H₂O, CH₃, OH, CO, C₂H₄, ·OH.

The output is suitable for a quick qualitative check — the viewer
renders each peak as a vertical stick normalized to 100% at the base
peak.

Caveats: real EI-MS fragmentation is governed by stability of carbocations
and radical cations, McLafferty rearrangements, ring-opening, etc. A
complete treatment would need a dedicated fragmentor such as MetFrag
or CFM-ID. For v0.7 we just want the molecular ion and common losses
to exercise the spectrum viewer.
"""

from __future__ import annotations

from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors

from bondforge.core.model.molecule import Molecule
from bondforge.core.model.spectrum import Peak, Spectrum, SpectrumType
from bondforge.engine.rdkit_adapter import molecule_to_rwmol

# Common neutral losses in EI-MS.
_FRAGMENTS = [
    (1.008, "M−H", 20.0),
    (15.023, "M−CH3", 30.0),
    (17.003, "M−OH", 15.0),
    (18.011, "M−H2O", 40.0),
    (28.003, "M−CO", 25.0),
    (28.031, "M−C2H4", 25.0),
    (29.026, "M−CHO", 20.0),
    (43.018, "M−C2H3O", 20.0),
]


def predict_ms(mol: Molecule, *, title: str = "") -> Spectrum:
    """Predict an EI-MS line spectrum for ``mol``."""
    peaks: list[Peak] = []
    x_values: list[float] = []
    y_values: list[float] = []

    if mol.atoms:
        rw = molecule_to_rwmol(mol)
        try:
            Chem.SanitizeMol(rw)
        except Exception:
            return _empty_spectrum(title)
        rd = rw.GetMol()

        mplus = round(Descriptors.ExactMolWt(rd), 4)
        peaks.append(Peak(x=mplus, intensity=100.0, label="M⁺"))
        x_values.append(mplus)
        y_values.append(100.0)

        # M+1 from 13C natural abundance (~1.1% per carbon).
        n_c = sum(1 for a in rd.GetAtoms() if a.GetSymbol() == "C")
        if n_c:
            h_m1 = 1.1 * n_c
            peaks.append(Peak(x=mplus + 1.003, intensity=h_m1, label="M+1"))
            x_values.append(mplus + 1.003)
            y_values.append(h_m1)

        # M+2 for S, Cl, Br (34S 4.4%, 37Cl 32%, 81Br 97%).
        formula = rdMolDescriptors.CalcMolFormula(rd)
        m2 = 0.0
        if "Cl" in formula:
            m2 += 32.0
        if "Br" in formula:
            m2 += 97.0
        if "S" in formula:
            m2 += 4.4
        if m2 > 0:
            peaks.append(Peak(x=mplus + 1.997, intensity=m2, label="M+2"))
            x_values.append(mplus + 1.997)
            y_values.append(m2)

        # Fragment losses — only keep peaks with m/z > 0.
        for loss, label, height in _FRAGMENTS:
            frag_mz = round(mplus - loss, 4)
            if frag_mz > 0:
                peaks.append(Peak(x=frag_mz, intensity=height, label=label))
                x_values.append(frag_mz)
                y_values.append(height)

    return Spectrum(
        id=0,
        spectrum_type=SpectrumType.MS,
        x_values=x_values,
        y_values=y_values,
        peaks=peaks,
        title=title or "Predicted EI-MS",
        origin="predicted",
        metadata={"ionization": "EI 70 eV"},
    )


def _empty_spectrum(title: str) -> Spectrum:
    return Spectrum(
        id=0,
        spectrum_type=SpectrumType.MS,
        title=title or "Predicted EI-MS",
        origin="predicted",
    )


__all__ = ["predict_ms"]
