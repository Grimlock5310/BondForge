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
    # Empty molecule emits no peaks at all (not even reference markers).
    assert spec.n_points == 0


def test_predict_1h_nmr_emits_tms_reference() -> None:
    spec = predict_1h_nmr(_make_ethanol())
    assert any(p.label == "TMS" and p.x == 0.0 for p in spec.peaks)
    assert any(p.label == "CHCl₃" for p in spec.peaks)


def test_predict_1h_nmr_aggregates_methyl_protons() -> None:
    """Three CH3 protons should collapse to one peak with intensity 3."""
    spec = predict_1h_nmr(_make_acetone())
    # Acetone has two equivalent methyls; aggregation collapses them
    # into one peak with integral 6 (sum of all CH3 protons).
    methyl_peak = max(
        (p for p in spec.peaks if p.label.startswith(("3H", "6H"))),
        key=lambda p: p.intensity,
        default=None,
    )
    assert methyl_peak is not None
    assert methyl_peak.intensity >= 3.0


# ---- 13C NMR ---------------------------------------------------------------


def test_predict_13c_nmr_acetone_has_carbonyl() -> None:
    spec = predict_13c_nmr(_make_acetone())
    # Carbonyl carbon should be near 200 ppm
    assert any(180 <= x <= 210 for x in spec.x_values)
    # Methyl carbons should be in the sp3 range
    assert any(0 <= x <= 50 for x in spec.x_values)


def test_predict_13c_nmr_benzene() -> None:
    spec = predict_13c_nmr(_make_benzene())
    # All six aromatic carbons collapse into a single ~128 ppm peak
    # plus the TMS and CDCl₃ reference markers added by the predictor.
    aromatic = [p for p in spec.peaks if p.label and "C" in p.label and p.label != "TMS"]
    assert any(120 <= p.x <= 135 for p in aromatic)
    # The TMS reference is always emitted at 0 ppm.
    assert any(p.label == "TMS" and p.x == 0.0 for p in spec.peaks)


# ---- IR --------------------------------------------------------------------


def test_predict_ir_ethanol_has_oh() -> None:
    spec = predict_ir(_make_ethanol())
    assert spec.spectrum_type == SpectrumType.IR
    # 4 cm⁻¹ resolution from 500–4000 cm⁻¹ → 876 points.
    assert spec.n_points == 876
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


def test_predict_ms_acetone_has_methyl_loss_and_acylium() -> None:
    """A methyl ketone should produce M−CH₃CO loss and the acylium daughter."""
    spec = predict_ms(_make_acetone())
    labels = {p.label for p in spec.peaks}
    assert "M−CH₃CO" in labels
    # M−CH₃ and the m/z 43 acylium ion collide on the same peak for
    # acetone (both are C₂H₃O⁺), so we just check that *some* peak at
    # ~43 m/z is present.
    assert any(42.5 <= p.x <= 43.5 for p in spec.peaks)


def test_predict_ms_normalized_to_base_peak() -> None:
    """Every MS spectrum's tallest peak should land at intensity 100."""
    spec = predict_ms(_make_acetone())
    if spec.peaks:
        assert max(p.intensity for p in spec.peaks) == 100.0


def test_predict_ms_no_methyl_loss_for_benzene() -> None:
    """Benzene has no CH₃ → no M−CH₃ fragment should be emitted."""
    spec = predict_ms(_make_benzene())
    labels = {p.label for p in spec.peaks}
    assert "M−CH₃" not in labels


def test_predict_ms_empty_molecule() -> None:
    spec = predict_ms(Molecule())
    assert spec.n_points == 0
