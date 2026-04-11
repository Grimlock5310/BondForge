"""Heuristic 1H and 13C NMR prediction.

This module implements a simple increment-based shift estimator. It's
not meant to compete with HOSE-code, DFT, or ML-based predictors
(nmrglue, nmrML, MNova, etc.) — the goal is to give a plausible
looking spectrum for teaching purposes and to demonstrate the viewer.

Algorithm:

1. Sanitize the molecule through RDKit.
2. Walk every heavy atom; for each hydrogen count > 0 atom, emit a
   proton shift derived from a base value for the atom's hybridization
   plus adjacency increments for electron-withdrawing neighbors.
3. For 13C, emit a shift per carbon atom based on hybridization plus
   adjacency increments.

Base values (ppm) — coarse group averages taken from the standard
Silverstein tables:

- sp3 C–H alkyl: 1.0 ppm
- sp3 C–H α to heteroatom: 3.5 ppm
- aromatic C–H: 7.3 ppm
- vinyl/alkene C–H: 5.5 ppm
- aldehyde H–C=O: 9.7 ppm
- carboxylic acid O–H: 12.0 ppm
- amine N–H: 2.5 ppm
- alcohol O–H: 2.0 ppm

13C base values:

- sp3 C alkyl: 20 ppm
- sp3 C–O: 65 ppm
- aromatic C: 128 ppm
- alkene C: 125 ppm
- nitrile C≡N: 118 ppm
- alkyne C: 80 ppm
- carbonyl C=O: 170 ppm (acid/ester), 200 ppm (aldehyde/ketone)
"""

from __future__ import annotations

from rdkit import Chem

from bondforge.core.model.molecule import Molecule
from bondforge.core.model.spectrum import Peak, Spectrum, SpectrumType
from bondforge.engine.rdkit_adapter import molecule_to_rwmol

# Electronegativity table for α-shift increments.
_EN = {
    "O": 3.44,
    "N": 3.04,
    "F": 3.98,
    "Cl": 3.16,
    "Br": 2.96,
    "I": 2.66,
    "S": 2.58,
    "P": 2.19,
}


def _sanitized_mol(mol: Molecule) -> Chem.Mol | None:
    """Sanitize and return the mol. Hydrogens stay implicit so
    ``GetTotalNumHs()`` returns the usable count for shift prediction."""
    if not mol.atoms:
        return None
    rw = molecule_to_rwmol(mol)
    try:
        Chem.SanitizeMol(rw)
    except Exception:
        return None
    return rw.GetMol()


def _is_aromatic_c(atom: Chem.Atom) -> bool:
    return atom.GetSymbol() == "C" and atom.GetIsAromatic()


def _is_sp2_c(atom: Chem.Atom) -> bool:
    return atom.GetSymbol() == "C" and atom.GetHybridization() == Chem.HybridizationType.SP2


def _has_carbonyl(atom: Chem.Atom) -> bool:
    """True if ``atom`` has a double-bonded oxygen."""
    for bond in atom.GetBonds():
        nbr = bond.GetOtherAtom(atom)
        if nbr.GetSymbol() == "O" and bond.GetBondType() == Chem.BondType.DOUBLE:
            return True
    return False


def _predict_proton_shift(atom: Chem.Atom) -> float | None:
    """Return the predicted 1H shift for atom, or None to skip.

    ``atom`` must be a heavy atom carrying ≥1 attached hydrogen. The
    returned chemical shift is the estimated ppm for all protons on
    that atom — we collapse chemically inequivalent protons (CH2, CH3)
    into a single peak keyed on the parent heavy atom.
    """
    n_h = atom.GetTotalNumHs()
    if n_h == 0:
        return None

    sym = atom.GetSymbol()
    if sym == "C":
        if atom.GetIsAromatic():
            base = 7.3
        elif atom.GetHybridization() == Chem.HybridizationType.SP2:
            base = 5.5
            if _has_carbonyl(atom):
                return 9.7  # aldehyde
        elif atom.GetHybridization() == Chem.HybridizationType.SP:
            base = 2.0
        else:
            base = 1.0
            # α to heteroatom shift bump.
            for nbr in atom.GetNeighbors():
                en = _EN.get(nbr.GetSymbol(), 0)
                if en >= 3.0:
                    base = max(base, 3.5)
                elif en > 2.5:
                    base = max(base, 2.7)
            # β to carbonyl bump.
            for nbr in atom.GetNeighbors():
                if nbr.GetSymbol() == "C" and _has_carbonyl(nbr):
                    base += 1.0
        return base
    if sym == "O":
        # OH — broad, variable. Carboxylic if the O is attached to
        # a carbonyl carbon.
        for nbr in atom.GetNeighbors():
            if nbr.GetSymbol() == "C" and _has_carbonyl(nbr):
                return 12.0
        return 2.0
    if sym == "N":
        return 2.5
    return None


def _predict_carbon_shift(atom: Chem.Atom) -> float | None:
    """Return the predicted 13C shift for a carbon atom."""
    if atom.GetSymbol() != "C":
        return None
    if atom.GetIsAromatic():
        return 128.0
    hyb = atom.GetHybridization()
    if hyb == Chem.HybridizationType.SP:
        # Distinguish nitrile from alkyne.
        for nbr in atom.GetNeighbors():
            if nbr.GetSymbol() == "N":
                return 118.0
        return 80.0
    if hyb == Chem.HybridizationType.SP2:
        if _has_carbonyl(atom):
            # Acid / ester / amide → 170; aldehyde / ketone → 200.
            for nbr in atom.GetNeighbors():
                if nbr.GetSymbol() == "O":
                    for b in nbr.GetBonds():
                        if (
                            b.GetBondType() == Chem.BondType.SINGLE
                            and b.GetOtherAtom(nbr).GetIdx() != atom.GetIdx()
                        ):
                            return 170.0  # ester
                    # single bond from O to something else means acid/alcohol
                elif nbr.GetSymbol() == "N":
                    return 170.0  # amide
            # Only the =O neighbor → aldehyde/ketone
            has_h = atom.GetTotalNumHs() > 0
            return 200.0 if has_h else 205.0
        return 125.0  # alkene
    # sp3
    base = 20.0
    for nbr in atom.GetNeighbors():
        en = _EN.get(nbr.GetSymbol(), 0)
        if en >= 3.0:
            base = max(base, 65.0)
        elif en > 2.5:
            base = max(base, 35.0)
    return base


def _multiplicity_for(atom: Chem.Atom) -> str:
    """Return an n+1 rule multiplicity label for neighboring H count."""
    neighbors_h = 0
    for nbr in atom.GetNeighbors():
        if nbr.GetSymbol() == "C":
            neighbors_h += nbr.GetTotalNumHs()
    return {0: "s", 1: "d", 2: "t", 3: "q", 4: "quint", 5: "sext"}.get(neighbors_h, "m")


def predict_1h_nmr(mol: Molecule, *, title: str = "") -> Spectrum:
    """Predict a 1H NMR stick spectrum for ``mol``."""
    rd = _sanitized_mol(mol)
    peaks: list[Peak] = []
    x_values: list[float] = []
    y_values: list[float] = []

    if rd is not None:
        for atom in rd.GetAtoms():
            if atom.GetSymbol() == "H":
                continue
            shift = _predict_proton_shift(atom)
            if shift is None:
                continue
            n_h = atom.GetTotalNumHs()
            if n_h == 0:
                continue
            mult = _multiplicity_for(atom) if atom.GetSymbol() == "C" else "br"
            intensity = float(n_h)
            label = f"{n_h}H {mult}" if atom.GetSymbol() == "C" else f"{atom.GetSymbol()}H"
            peaks.append(Peak(x=shift, intensity=intensity, label=label, multiplicity=mult))
            x_values.append(shift)
            y_values.append(intensity)

    return Spectrum(
        id=0,
        spectrum_type=SpectrumType.NMR_1H,
        x_values=x_values,
        y_values=y_values,
        peaks=peaks,
        title=title or "Predicted 1H NMR",
        origin="predicted",
        metadata={"solvent": "CDCl3", "frequency": "400 MHz"},
    )


def predict_13c_nmr(mol: Molecule, *, title: str = "") -> Spectrum:
    """Predict a 13C NMR stick spectrum for ``mol``."""
    rd = _sanitized_mol(mol)
    peaks: list[Peak] = []
    x_values: list[float] = []
    y_values: list[float] = []

    if rd is not None:
        for atom in rd.GetAtoms():
            shift = _predict_carbon_shift(atom)
            if shift is None:
                continue
            peaks.append(Peak(x=shift, intensity=1.0, label="C"))
            x_values.append(shift)
            y_values.append(1.0)

    return Spectrum(
        id=0,
        spectrum_type=SpectrumType.NMR_13C,
        x_values=x_values,
        y_values=y_values,
        peaks=peaks,
        title=title or "Predicted 13C NMR",
        origin="predicted",
        metadata={"solvent": "CDCl3", "frequency": "100 MHz"},
    )


__all__ = ["predict_1h_nmr", "predict_13c_nmr"]
