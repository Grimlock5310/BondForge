"""Heuristic 1H and 13C NMR prediction.

This is a simple substituent-additivity estimator, not a research-grade
predictor. The goal is to give a chemically plausible spectrum for
teaching and to populate the viewer; for production work users should
import experimental data via JCAMP-DX or rely on a dedicated tool
(MestreNova, Mnova, ACD/Labs, NMRium for processing).

Algorithm
=========

For 1H, the shift of a proton attached to a heavy atom is computed
from a base value that depends on the carbon's substitution count
(CH₃, CH₂, CH) and hybridization, with additive increments for each
α-substituent (nearest neighbour) and a smaller bump for each
β-carbonyl. Aromatic protons get a single base value perturbed by
ring electron donors/acceptors. Heteroatom-attached protons (O–H,
N–H) use broad solvent-dependent averages.

For 13C, every carbon emits one peak. Sp³ carbons start from a
base depending on substitution count (CH₃ ≈ 14, CH₂ ≈ 23, CH ≈ 28,
C ≈ 35) and gain heavy α-substituent increments. Carbonyl carbons
are differentiated into acid / ester / amide / aldehyde / ketone.

Both predictors:

- Aggregate equivalent peaks within ±0.02 ppm (¹H) or ±0.5 ppm (¹³C)
  by summing intensities, so e.g. the three CH₃ protons of methanol
  show up as one peak with integral 3, and the six equivalent ring
  carbons of benzene give a single 6× line at 128.
- Add a TMS reference peak at 0 ppm and a residual CDCl₃ peak at
  7.26 (¹H) or 77.16 (¹³C) at low intensity, so the spectrum looks
  the way users expect on screen.
"""

from __future__ import annotations

from rdkit import Chem

from bondforge.core.model.molecule import Molecule
from bondforge.core.model.spectrum import Peak, Spectrum, SpectrumType
from bondforge.engine.rdkit_adapter import molecule_to_rwmol

# ---- helpers ---------------------------------------------------------------


def _sanitized_mol(mol: Molecule) -> Chem.Mol | None:
    """Sanitize and return the mol with implicit hydrogens preserved."""
    if not mol.atoms:
        return None
    rw = molecule_to_rwmol(mol)
    try:
        Chem.SanitizeMol(rw)
    except Exception:
        return None
    return rw.GetMol()


def _has_carbonyl(atom: Chem.Atom) -> bool:
    """True if ``atom`` has a double bond to oxygen."""
    for bond in atom.GetBonds():
        nbr = bond.GetOtherAtom(atom)
        if nbr.GetSymbol() == "O" and bond.GetBondType() == Chem.BondType.DOUBLE:
            return True
    return False


def _carbonyl_neighbour(atom: Chem.Atom) -> Chem.Atom | None:
    """Return a carbonyl C neighbour of ``atom``, if any."""
    for nbr in atom.GetNeighbors():
        if nbr.GetSymbol() == "C" and _has_carbonyl(nbr):
            return nbr
    return None


def _is_aromatic_neighbour(atom: Chem.Atom) -> bool:
    """True if ``atom`` is bonded to any aromatic atom."""
    return any(nbr.GetIsAromatic() for nbr in atom.GetNeighbors())


def _aggregate_peaks(peaks: list[Peak], window: float) -> list[Peak]:
    """Sum peaks whose x-values fall within ``window`` of each other.

    Two protons sharing a chemical environment (e.g. the three Hs of a
    methyl) end up at exactly the same predicted shift in our model;
    aggregating them produces one peak with the correct integral
    instead of three overlapping sticks.

    When peaks with different splitting patterns merge — e.g. two
    aromatic doublets and a triplet — the result is reported as a
    multiplet (``m``) rather than picking whichever happened to land
    in the bucket first.
    """
    if not peaks:
        return []
    peaks = sorted(peaks, key=lambda p: p.x)
    out: list[Peak] = []
    for p in peaks:
        if out and abs(out[-1].x - p.x) <= window:
            last = out[-1]
            new_int = last.intensity + p.intensity
            # Pick the merged multiplicity: if both source peaks agree
            # use that label, otherwise fall back to "m" for multiplet.
            if last.multiplicity == p.multiplicity or not p.multiplicity:
                merged_mult = last.multiplicity
            elif not last.multiplicity:
                merged_mult = p.multiplicity
            else:
                merged_mult = "m"
            # Build the merged label. For proton peaks we use the
            # nH-multiplicity convention; everything else just keeps
            # the original (non-empty) label.
            if last.label and "H " in last.label:
                merged_label = f"{int(round(new_int))}H {merged_mult}".strip()
            else:
                merged_label = last.label or p.label
            out[-1] = Peak(
                x=last.x,
                intensity=new_int,
                label=merged_label,
                multiplicity=merged_mult,
            )
        else:
            out.append(p)
    return out


# ---- 1H NMR ----------------------------------------------------------------

# Per-substituent α-increments for sp3 C–H shifts (additive on top of
# the CH3/CH2/CH base value). Numbers are coarse approximations of
# Shoolery's rules and the Friebolin tables.
_ALPHA_H_INC = {
    "F": 3.2,
    "Cl": 2.4,
    "Br": 2.2,
    "I": 1.9,
    "O": 2.4,
    "N": 1.4,
    "S": 1.3,
    "P": 0.7,
    "Si": 0.0,
    # Carbons get refined below depending on context (=O, aromatic, …)
    "C": 0.0,
}


def _proton_shift_for_carbon(atom: Chem.Atom) -> float | None:
    """Estimate the predicted 1H shift for the H atoms on a carbon."""
    n_h = atom.GetTotalNumHs()
    if n_h == 0:
        return None

    if atom.GetIsAromatic():
        # Base aromatic CH ~7.26 (similar to chloroform residual). Shift
        # the whole ring up by 0.3 if any aromatic atom carries a strong
        # EWG (NO2, C=O, CN), down by 0.3 if a strong EDG (OMe, NH2, OH).
        return _aromatic_proton_shift(atom)

    hyb = atom.GetHybridization()
    if hyb == Chem.HybridizationType.SP2:
        # Vinyl C–H (or aldehyde, handled below).
        if _has_carbonyl(atom) and n_h >= 1:
            return 9.7  # aldehyde –CHO
        return _vinyl_proton_shift(atom)
    if hyb == Chem.HybridizationType.SP:
        return 2.2  # terminal alkyne C–H

    # sp3
    base = {3: 0.86, 2: 1.20, 1: 1.50}.get(n_h, 1.0)
    increment = 0.0
    for nbr in atom.GetNeighbors():
        if nbr.GetSymbol() == "H":
            continue
        sym = nbr.GetSymbol()
        if sym == "C":
            # Carbon neighbours: refine.
            if nbr.GetIsAromatic():
                increment += 1.4  # benzylic
            elif _has_carbonyl(nbr):
                increment += 1.1  # α to C=O
            elif nbr.GetHybridization() == Chem.HybridizationType.SP2 and not _has_carbonyl(nbr):
                increment += 0.7  # allylic
            # Plain sp3 C neighbour contributes 0.
        else:
            increment += _ALPHA_H_INC.get(sym, 0.0)

    # Multiple substituents on the same C compound roughly additively;
    # cap so a CH with three halogens doesn't shoot to 12 ppm.
    return min(base + increment, 9.5)


def _vinyl_proton_shift(atom: Chem.Atom) -> float:
    """Approximate vinyl proton shift, with α-EWG/EDG bumps."""
    base = 5.4
    for nbr in atom.GetNeighbors():
        if nbr.GetSymbol() in ("O", "N"):
            base += 0.6  # enol ether / enamine
        if nbr.GetSymbol() == "C" and _has_carbonyl(nbr):
            base += 0.7  # vinyl-COR
    return min(base, 7.0)


def _aromatic_proton_shift(atom: Chem.Atom) -> float:
    """Aromatic CH base shift, perturbed by ring substituents."""
    base = 7.26
    # Look at ring neighbours' substituents (one bond out of the ring).
    bump = 0.0
    for ring_nbr in atom.GetNeighbors():
        if not ring_nbr.GetIsAromatic():
            continue
        for outside in ring_nbr.GetNeighbors():
            if outside.GetIdx() == atom.GetIdx() or outside.GetIsAromatic():
                continue
            sym = outside.GetSymbol()
            if sym == "N" and outside.GetTotalNumHs() > 0:
                bump -= 0.6  # –NH2
            elif sym == "O" and outside.GetTotalNumHs() > 0:
                bump -= 0.4  # –OH
            elif sym == "O" and outside.GetTotalNumHs() == 0:
                bump -= 0.2  # –OR
            elif sym == "N":
                # –NO2 has formal charges; check explicitly.
                if outside.GetFormalCharge() > 0:
                    bump += 0.9
            elif sym == "C" and _has_carbonyl(outside):
                bump += 0.5  # –COR / –COOR
    return base + bump


def _multiplicity_for(atom: Chem.Atom) -> str:
    """n+1 multiplicity from neighbouring CH proton count."""
    neighbours_h = sum(nbr.GetTotalNumHs() for nbr in atom.GetNeighbors() if nbr.GetSymbol() == "C")
    return {0: "s", 1: "d", 2: "t", 3: "q", 4: "quint", 5: "sext", 6: "sept"}.get(neighbours_h, "m")


def _heteroatom_proton_shift(atom: Chem.Atom) -> float | None:
    """Shift for protons attached to N/O/S/P heteroatoms."""
    n_h = atom.GetTotalNumHs()
    if n_h == 0:
        return None
    sym = atom.GetSymbol()
    if sym == "O":
        if _carbonyl_neighbour(atom):
            return 11.5  # carboxylic acid (very broad)
        if _is_aromatic_neighbour(atom):
            return 5.5  # phenol
        return 2.5  # alcohol (broad, variable)
    if sym == "N":
        if _is_aromatic_neighbour(atom):
            return 4.0  # aniline NH
        if _carbonyl_neighbour(atom):
            return 7.0  # amide NH
        return 1.8  # alkyl amine
    if sym == "S":
        return 1.5  # thiol SH
    return None


def predict_1h_nmr(mol: Molecule, *, title: str = "") -> Spectrum:
    """Predict a 1H NMR stick spectrum for ``mol``.

    Adds aggregated peaks for every C–H and X–H environment, plus a
    small TMS reference at 0 ppm and a faint CDCl₃ residual at 7.26 ppm.
    """
    rd = _sanitized_mol(mol)
    raw_peaks: list[Peak] = []

    if rd is not None:
        for atom in rd.GetAtoms():
            sym = atom.GetSymbol()
            if sym == "H":
                continue
            n_h = atom.GetTotalNumHs()
            if n_h == 0:
                continue
            if sym == "C":
                shift = _proton_shift_for_carbon(atom)
                if shift is None:
                    continue
                mult = _multiplicity_for(atom)
                label = f"{n_h}H {mult}"
            else:
                shift = _heteroatom_proton_shift(atom)
                if shift is None:
                    continue
                mult = "br"
                label = f"{n_h}H br ({sym}H)"
            raw_peaks.append(
                Peak(x=round(shift, 3), intensity=float(n_h), label=label, multiplicity=mult)
            )

    peaks = _aggregate_peaks(raw_peaks, window=0.05)

    # Reference markers — only if we actually predicted something, so an
    # empty Molecule produces an empty Spectrum.
    if peaks:
        peaks.append(Peak(x=0.0, intensity=0.6, label="TMS", multiplicity="s"))
        peaks.append(Peak(x=7.26, intensity=0.4, label="CHCl₃", multiplicity="s"))

    x_values = [p.x for p in peaks]
    y_values = [p.intensity for p in peaks]

    return Spectrum(
        id=0,
        spectrum_type=SpectrumType.NMR_1H,
        x_values=x_values,
        y_values=y_values,
        peaks=peaks,
        title=title or "Predicted ¹H NMR",
        origin="predicted",
        metadata={"solvent": "CDCl₃", "frequency": "400 MHz", "reference": "TMS"},
    )


# ---- 13C NMR ---------------------------------------------------------------

# α-substituent increments for sp3 carbons (Lindeman-Adams style, very
# rough averages). Per heavy α neighbour.
_ALPHA_C_INC = {
    "C": 9.0,
    "N": 21.0,
    "O": 35.0,
    "F": 53.0,
    "Cl": 30.0,
    "Br": 16.0,
    "I": -7.0,
    "S": 13.0,
    "P": 8.0,
}


def _sp3_carbon_shift(atom: Chem.Atom) -> float:
    """Approximate sp3 13C shift via base + α-substituent additivity."""
    n_h = atom.GetTotalNumHs()
    base = {3: -2.0, 2: 5.0, 1: 12.0, 0: 24.0}.get(n_h, 0.0)
    increment = 0.0
    for nbr in atom.GetNeighbors():
        if nbr.GetSymbol() == "H":
            continue
        increment += _ALPHA_C_INC.get(nbr.GetSymbol(), 5.0)
    # Bump for adjacent carbonyl (β-effect ~+5).
    if _carbonyl_neighbour(atom):
        increment += 5.0
    return min(max(base + increment, 5.0), 95.0)


def _sp2_carbon_shift(atom: Chem.Atom) -> float:
    """Approximate sp2 13C shift, including carbonyl differentiation."""
    if _has_carbonyl(atom):
        return _carbonyl_carbon_shift(atom)
    # Plain alkene C: 110-150, default 125.
    base = 125.0
    for nbr in atom.GetNeighbors():
        if nbr.GetSymbol() == "O":
            base += 25.0  # enol ether
        elif nbr.GetSymbol() == "N":
            base += 15.0
    return min(base, 160.0)


def _carbonyl_carbon_shift(atom: Chem.Atom) -> float:
    """Differentiate carbonyl C: aldehyde / ketone / acid / ester / amide."""
    has_h = atom.GetTotalNumHs() > 0
    has_or = False
    has_oh = False
    has_n = False
    for nbr in atom.GetNeighbors():
        if nbr.GetSymbol() == "O":
            # Skip the =O
            for bond in atom.GetBonds():
                if (
                    bond.GetOtherAtom(atom).GetIdx() == nbr.GetIdx()
                    and bond.GetBondType() == Chem.BondType.DOUBLE
                ):
                    break
            else:
                if nbr.GetTotalNumHs() > 0:
                    has_oh = True
                else:
                    has_or = True
        elif nbr.GetSymbol() == "N":
            has_n = True
    if has_oh:
        return 178.0  # carboxylic acid
    if has_or:
        return 170.0  # ester
    if has_n:
        return 172.0  # amide
    if has_h:
        return 192.0  # aldehyde
    return 207.0  # ketone


def _aromatic_carbon_shift(atom: Chem.Atom) -> float:
    """Aromatic 13C shift; ipso carbons differ from CH carbons."""
    n_h = atom.GetTotalNumHs()
    if n_h == 0:
        # Ipso (substituted) ring carbon — 130-150 depending on substituent.
        for nbr in atom.GetNeighbors():
            if nbr.GetIsAromatic():
                continue
            sym = nbr.GetSymbol()
            if sym == "O":
                return 155.0  # phenol/anisole ipso
            if sym == "N":
                return 148.0
            if sym == "C" and _has_carbonyl(nbr):
                return 140.0
        return 138.0
    return 128.5  # plain aromatic CH


def _predict_carbon_shift(atom: Chem.Atom) -> float | None:
    if atom.GetSymbol() != "C":
        return None
    if atom.GetIsAromatic():
        return _aromatic_carbon_shift(atom)
    hyb = atom.GetHybridization()
    if hyb == Chem.HybridizationType.SP:
        for nbr in atom.GetNeighbors():
            if nbr.GetSymbol() == "N" and any(
                b.GetBondType() == Chem.BondType.TRIPLE for b in atom.GetBonds()
            ):
                return 118.0  # nitrile
        return 80.0  # alkyne
    if hyb == Chem.HybridizationType.SP2:
        return _sp2_carbon_shift(atom)
    return _sp3_carbon_shift(atom)


def predict_13c_nmr(mol: Molecule, *, title: str = "") -> Spectrum:
    """Predict a 13C NMR stick spectrum for ``mol``."""
    rd = _sanitized_mol(mol)
    raw_peaks: list[Peak] = []
    if rd is not None:
        for atom in rd.GetAtoms():
            shift = _predict_carbon_shift(atom)
            if shift is None:
                continue
            label = "C" + ("H" * atom.GetTotalNumHs() if atom.GetTotalNumHs() else "")
            raw_peaks.append(Peak(x=round(shift, 2), intensity=1.0, label=label))

    peaks = _aggregate_peaks(raw_peaks, window=0.5)

    # Reference markers — only if we actually predicted something.
    if peaks:
        peaks.append(Peak(x=0.0, intensity=0.4, label="TMS"))
        peaks.append(Peak(x=77.16, intensity=0.4, label="CDCl₃"))

    x_values = [p.x for p in peaks]
    y_values = [p.intensity for p in peaks]

    return Spectrum(
        id=0,
        spectrum_type=SpectrumType.NMR_13C,
        x_values=x_values,
        y_values=y_values,
        peaks=peaks,
        title=title or "Predicted ¹³C NMR",
        origin="predicted",
        metadata={"solvent": "CDCl₃", "frequency": "100 MHz", "reference": "TMS"},
    )


__all__ = ["predict_1h_nmr", "predict_13c_nmr"]
