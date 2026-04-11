"""Tests for the heuristic spectrum predictors (NMR, IR, MS)."""

from __future__ import annotations

from bondforge.core.model.bond import BondOrder
from bondforge.core.model.molecule import Molecule
from bondforge.core.model.spectrum import SpectrumType
from bondforge.engine.prediction import (
    predict_1h_nmr,
    predict_13c_nmr,
    predict_ir,
    predict_ms,
)


def _make_ethanol() -> Molecule:
    """CH3-CH2-OH drawn with explicit atoms."""
    mol = Molecule()
    c1 = mol.add_atom("C", 0, 0)
    c2 = mol.add_atom("C", 50, 0)
    o = mol.add_atom("O", 100, 0)
    mol.add_bond(c1.id, c2.id, BondOrder.SINGLE)
    mol.add_bond(c2.id, o.id, BondOrder.SINGLE)
    return mol


def _make_benzene() -> Molecule:
    """C6H6 aromatic ring."""
    mol = Molecule()
    import math

    atoms = []
    for i in range(6):
        a = 2 * math.pi * i / 6
        atoms.append(mol.add_atom("C", 50 * math.cos(a), 50 * math.sin(a)))
    for i in range(6):
        order = BondOrder.DOUBLE if i % 2 == 0 else BondOrder.SINGLE
        mol.add_bond(atoms[i].id, atoms[(i + 1) % 6].id, order)
    return mol


def _make_acetone() -> Molecule:
    """CH3-C(=O)-CH3."""
    mol = Molecule()
    c1 = mol.add_atom("C", 0, 0)
    c2 = mol.add_atom("C", 50, 0)
    c3 = mol.add_atom("C", 100, 0)
    o = mol.add_atom("O", 50, -50)
    mol.add_bond(c1.id, c2.id, BondOrder.SINGLE)
    mol.add_bond(c2.id, c3.id, BondOrder.SINGLE)
    mol.add_bond(c2.id, o.id, BondOrder.DOUBLE)
    return mol


# ---- 1H NMR -----------------------------------------------------------------


def test_predict_1h_nmr_ethanol() -> None:
    spec = predict_1h_nmr(_make_ethanol())
    assert spec.spectrum_type == SpectrumType.NMR_1H
    assert spec.origin == "predicted"
    assert spec.n_points >= 2  # CH3, CH2, OH at minimum
    # OH proton should be reasonable (~2.0 ppm in our heuristic)
    assert any(1.0 <= x <= 5.0 for x in spec.x_values)


def test_predict_1h_nmr_benzene_has_aromatic_peak() -> None:
    spec = predict_1h_nmr(_make_benzene())
    # Aromatic protons should show up around 7.3 ppm
    assert any(6.5 <= x <= 8.0 for x in spec.x_values)


def test_predict_1h_nmr_empty_molecule() -> None:
    spec = predict_1h_nmr(Molecule())
    assert spec.n_points == 0


# ---- 13C NMR ---------------------------------------------------------------


def test_predict_13c_nmr_acetone_has_carbonyl() -> None:
    spec = predict_13c_nmr(_make_acetone())
    # Carbonyl carbon should be near 200 ppm
    assert any(180 <= x <= 210 for x in spec.x_values)
    # Methyl carbons should be in the sp3 range
    assert any(0 <= x <= 50 for x in spec.x_values)


def test_predict_13c_nmr_benzene() -> None:
    spec = predict_13c_nmr(_make_benzene())
    assert spec.n_points == 6
    # All carbons aromatic → ~128 ppm
    for x in spec.x_values:
        assert 120 <= x <= 135


# ---- IR --------------------------------------------------------------------


def test_predict_ir_ethanol_has_oh() -> None:
    spec = predict_ir(_make_ethanol())
    assert spec.spectrum_type == SpectrumType.IR
    assert spec.n_points == 501
    assert any("O–H" in p.label for p in spec.peaks)


def test_predict_ir_acetone_has_carbonyl() -> None:
    spec = predict_ir(_make_acetone())
    assert any("C=O" in p.label for p in spec.peaks)


def test_predict_ir_transmittance_bounded() -> None:
    spec = predict_ir(_make_ethanol())
    for y in spec.y_values:
        assert 0.0 <= y <= 100.0


# ---- MS --------------------------------------------------------------------


def test_predict_ms_ethanol_has_m_plus() -> None:
    spec = predict_ms(_make_ethanol())
    assert spec.spectrum_type == SpectrumType.MS
    labels = [p.label for p in spec.peaks]
    assert "M⁺" in labels
    # Ethanol exact mass ~46.04 (C2H6O)
    m_peak = next(p for p in spec.peaks if p.label == "M⁺")
    assert 45 <= m_peak.x <= 47


def test_predict_ms_has_fragment_peaks() -> None:
    spec = predict_ms(_make_acetone())
    # At least one standard fragment loss should be present
    labels = [p.label for p in spec.peaks]
    assert any(label.startswith("M−") for label in labels)


def test_predict_ms_empty_molecule() -> None:
    spec = predict_ms(Molecule())
    assert spec.n_points == 0
