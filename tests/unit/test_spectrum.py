"""Tests for the Spectrum dataclass."""

from __future__ import annotations

import pytest

from bondforge.core.model.spectrum import Peak, Spectrum, SpectrumType


def test_spectrum_construction() -> None:
    spec = Spectrum(
        id=1,
        spectrum_type=SpectrumType.NMR_1H,
        x_values=[1.0, 2.0, 3.0],
        y_values=[10.0, 20.0, 30.0],
    )
    assert spec.n_points == 3
    assert spec.x_unit == "ppm"
    assert spec.y_unit == "intensity"
    assert spec.spectrum_type.x_reversed is True


def test_ir_not_reversed_actually_is() -> None:
    assert SpectrumType.IR.x_reversed is True
    assert SpectrumType.MS.x_reversed is False


def test_mismatched_lengths_raise() -> None:
    with pytest.raises(ValueError):
        Spectrum(
            id=1,
            spectrum_type=SpectrumType.NMR_1H,
            x_values=[1.0, 2.0],
            y_values=[10.0],
        )


def test_x_range_with_peaks() -> None:
    spec = Spectrum(
        id=1,
        spectrum_type=SpectrumType.MS,
        x_values=[100.0, 200.0],
        y_values=[50.0, 100.0],
        peaks=[Peak(x=300.0, intensity=10.0)],
    )
    assert spec.x_range() == (100.0, 300.0)


def test_empty_spectrum_ranges() -> None:
    spec = Spectrum(id=1, spectrum_type=SpectrumType.IR)
    assert spec.x_range() == (0.0, 1.0)
    assert spec.y_range() == (0.0, 1.0)
