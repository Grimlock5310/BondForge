"""Heuristic EI mass spectrum prediction.

Generates a stick spectrum that includes:

- A **molecular ion** M⁺ at the monoisotopic mass.
- **Isotopologue peaks** at M+1 (¹³C natural abundance, ~1.1% per
  carbon) and M+2 (³⁴S, ³⁷Cl, ⁸¹Br abundances).
- **Context-aware fragment peaks** chosen by detecting functional
  groups via SMARTS. The fragment table is no longer fixed: a
  molecule with no methyl groups never shows an M−CH₃ peak, an
  alcohol gets M−H₂O / M−OH, a ketone gets α-cleavage acylium
  fragments, an aromatic gets a tropylium peak at m/z 91, and so on.
- Everything is **normalized to a base peak of 100**, so the spectrum
  always fills the y-axis the way users expect.

This is still a heuristic for visualization. For research-grade EI
fragmentation a quantum-chemistry-driven fragmentor (CFM-ID, MetFrag,
QCxMS) is the right tool.
"""

from __future__ import annotations

from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors

from bondforge.core.model.molecule import Molecule
from bondforge.core.model.spectrum import Peak, Spectrum, SpectrumType
from bondforge.engine.rdkit_adapter import molecule_to_rwmol


def _matches(rd: Chem.Mol, smarts: str) -> bool:
    patt = Chem.MolFromSmarts(smarts)
    if patt is None:
        return False
    return rd.HasSubstructMatch(patt)


def _add_peak(
    peaks: list[Peak],
    mz: float,
    intensity: float,
    label: str,
    *,
    seen: dict[float, int],
) -> None:
    """Add a peak to ``peaks``, merging duplicates within 0.05 m/z."""
    rounded = round(mz, 3)
    # Find the nearest existing peak within 0.05.
    for existing_mz, idx in list(seen.items()):
        if abs(existing_mz - rounded) <= 0.05:
            old = peaks[idx]
            if intensity > old.intensity:
                peaks[idx] = Peak(x=old.x, intensity=intensity, label=label)
            return
    seen[rounded] = len(peaks)
    peaks.append(Peak(x=rounded, intensity=intensity, label=label))


def predict_ms(mol: Molecule, *, title: str = "") -> Spectrum:
    """Predict an EI mass spectrum (line spectrum) for ``mol``."""
    if not mol.atoms:
        return _empty_spectrum(title)

    rw = molecule_to_rwmol(mol)
    try:
        Chem.SanitizeMol(rw)
    except Exception:
        return _empty_spectrum(title)
    rd = rw.GetMol()

    peaks: list[Peak] = []
    seen: dict[float, int] = {}

    # ---- Molecular ion ---------------------------------------------------
    mplus = round(Descriptors.ExactMolWt(rd), 4)
    _add_peak(peaks, mplus, 100.0, "M⁺", seen=seen)

    # ---- Isotopologues ---------------------------------------------------
    n_c = sum(1 for a in rd.GetAtoms() if a.GetSymbol() == "C")
    if n_c > 0:
        m1_height = min(1.1 * n_c, 80.0)
        _add_peak(peaks, mplus + 1.003, m1_height, "M+1", seen=seen)

    formula = rdMolDescriptors.CalcMolFormula(rd)
    n_cl = formula.count("Cl")
    n_br = formula.count("Br")
    n_s = formula.count("S")
    m2_height = 0.0
    m2_label_parts: list[str] = []
    if n_cl:
        m2_height += 32.5 * n_cl
        m2_label_parts.append("³⁷Cl")
    if n_br:
        # 81Br ≈ 97% of 79Br — for n_br=1 the M+2 is the actual base
        # peak. We cap so the molecular ion stays the headline label.
        m2_height += min(97.0 * n_br, 95.0)
        m2_label_parts.append("⁸¹Br")
    if n_s:
        m2_height += 4.4 * n_s
        m2_label_parts.append("³⁴S")
    if m2_height > 0:
        label = "M+2" + (f" ({'+'.join(m2_label_parts)})" if m2_label_parts else "")
        _add_peak(peaks, mplus + 1.997, m2_height, label, seen=seen)

    # ---- Functional-group-driven neutral losses --------------------------
    # Detect functional groups once so each fragment rule is a cheap
    # boolean test.
    has_carbonyl = _matches(rd, "[CX3]=[OX1]")
    has_acid = _matches(rd, "[CX3](=O)[OX2H]")
    has_aldehyde = _matches(rd, "[CX3H1]=[OX1]")
    has_alcohol = _matches(rd, "[CX4][OX2H1]")
    has_methyl = _matches(rd, "[CX4H3]")
    has_ethyl = _matches(rd, "[CX4H3][CX4H2]")
    has_methyl_ester = _matches(rd, "[CX3](=O)[OX2][CH3]")
    has_ethyl_ester = _matches(rd, "[CX3](=O)[OX2][CH2][CH3]")
    has_methyl_ketone = _matches(rd, "[CH3][CX3]=[OX1]")
    has_amine_h2 = _matches(rd, "[NX3;H2]")
    has_nitrile = _matches(rd, "[CX2]#[NX1]")
    has_nitro = _matches(rd, "[NX3](=O)=O") or _matches(rd, "[NX3+](=O)[O-]")
    has_aromatic = _matches(rd, "c1ccccc1")
    has_benzyl = _matches(rd, "c1ccccc1[CX4]")
    has_methyl_ether = _matches(rd, "[CH3][OX2][CX4]")
    has_mclafferty = _matches(rd, "[CX3](=[OX1])[CX4][CX4][CX4][#1]")
    has_F = "F" in formula and "Fe" not in formula
    has_Cl = n_cl > 0
    has_Br = n_br > 0
    has_I = "I" in formula and "In" not in formula and "Ir" not in formula

    # M-1 (loss of H) is almost universal for organic molecules with
    # any aliphatic H present.
    if any(a.GetTotalNumHs() > 0 for a in rd.GetAtoms()):
        _add_peak(peaks, mplus - 1.008, 25.0, "M−H", seen=seen)

    # Methyl loss.
    if has_methyl:
        _add_peak(peaks, mplus - 15.023, 45.0, "M−CH₃", seen=seen)

    # Ethyl loss.
    if has_ethyl:
        _add_peak(peaks, mplus - 29.039, 30.0, "M−C₂H₅", seen=seen)

    # Water loss.
    if has_alcohol or has_acid:
        _add_peak(peaks, mplus - 18.011, 60.0, "M−H₂O", seen=seen)

    # OH loss.
    if has_acid:
        _add_peak(peaks, mplus - 17.003, 30.0, "M−OH", seen=seen)
        _add_peak(peaks, mplus - 45.000, 50.0, "M−COOH", seen=seen)

    # CO loss for any carbonyl.
    if has_carbonyl:
        _add_peak(peaks, mplus - 27.995, 35.0, "M−CO", seen=seen)

    # CHO loss for aldehydes.
    if has_aldehyde:
        _add_peak(peaks, mplus - 29.003, 50.0, "M−CHO", seen=seen)

    # OMe / OEt loss for esters.
    if has_methyl_ester:
        _add_peak(peaks, mplus - 31.018, 55.0, "M−OCH₃", seen=seen)
    if has_ethyl_ester:
        _add_peak(peaks, mplus - 45.034, 50.0, "M−OC₂H₅", seen=seen)

    # Acetyl loss for methyl ketones (also α-cleavage).
    if has_methyl_ketone:
        _add_peak(peaks, mplus - 43.018, 60.0, "M−CH₃CO", seen=seen)

    # NH3 / HCN.
    if has_amine_h2:
        _add_peak(peaks, mplus - 17.027, 30.0, "M−NH₃", seen=seen)
    if has_nitrile:
        _add_peak(peaks, mplus - 27.011, 35.0, "M−HCN", seen=seen)

    # NO2 / NO from nitro.
    if has_nitro:
        _add_peak(peaks, mplus - 46.005, 60.0, "M−NO₂", seen=seen)
        _add_peak(peaks, mplus - 30.011, 35.0, "M−NO", seen=seen)

    # Halogen losses.
    if has_F:
        _add_peak(peaks, mplus - 18.998, 25.0, "M−F", seen=seen)
    if has_Cl:
        _add_peak(peaks, mplus - 34.969, 35.0, "M−Cl", seen=seen)
    if has_Br:
        _add_peak(peaks, mplus - 78.918, 40.0, "M−Br", seen=seen)
    if has_I:
        _add_peak(peaks, mplus - 126.904, 45.0, "M−I", seen=seen)

    # McLafferty rearrangement.
    if has_mclafferty:
        _add_peak(peaks, mplus - 28.031, 50.0, "M−C₂H₄ (McLafferty)", seen=seen)

    # ---- Daughter ions ---------------------------------------------------
    if has_benzyl:
        _add_peak(peaks, 91.054, 80.0, "tropylium C₇H₇⁺", seen=seen)
    if has_aromatic:
        _add_peak(peaks, 77.039, 40.0, "phenyl C₆H₅⁺", seen=seen)
    if has_methyl_ketone or _matches(rd, "[CH3][CX3](=O)O"):
        _add_peak(peaks, 43.018, 65.0, "acylium CH₃CO⁺", seen=seen)
    if has_amine_h2:
        _add_peak(peaks, 30.034, 55.0, "iminium CH₂=NH₂⁺", seen=seen)
    if has_methyl_ether:
        _add_peak(peaks, 45.034, 40.0, "CH₂=OCH₃⁺", seen=seen)

    # Drop fragments at m/z ≤ 1 (un-physical).
    peaks = [p for p in peaks if p.x > 1.0]

    # ---- Normalize to base peak = 100 -----------------------------------
    if peaks:
        max_int = max(p.intensity for p in peaks)
        if max_int > 0:
            peaks = [
                Peak(
                    x=p.x,
                    intensity=round(100.0 * p.intensity / max_int, 1),
                    label=p.label,
                    multiplicity=p.multiplicity,
                )
                for p in peaks
            ]
        # Sort by m/z so the spectrum is in ascending order.
        peaks.sort(key=lambda p: p.x)

    x_values = [p.x for p in peaks]
    y_values = [p.intensity for p in peaks]

    return Spectrum(
        id=0,
        spectrum_type=SpectrumType.MS,
        x_values=x_values,
        y_values=y_values,
        peaks=peaks,
        title=title or "Predicted EI-MS",
        origin="predicted",
        metadata={
            "ionization": "EI 70 eV",
            "monoisotopic": f"{mplus:.4f}",
            "formula": formula,
        },
    )


def _empty_spectrum(title: str) -> Spectrum:
    return Spectrum(
        id=0,
        spectrum_type=SpectrumType.MS,
        title=title or "Predicted EI-MS",
        origin="predicted",
    )


__all__ = ["predict_ms"]
