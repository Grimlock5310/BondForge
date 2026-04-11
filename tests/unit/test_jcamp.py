"""Tests for the JCAMP-DX reader/writer."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from bondforge.core.io.jcamp import (
    JcampError,
    parse_jcamp,
    read_jcamp_file,
    write_jcamp,
    write_jcamp_file,
)
from bondforge.core.model.spectrum import Peak, Spectrum, SpectrumType


def test_write_read_peak_table_roundtrip() -> None:
    spec = Spectrum(
        id=1,
        spectrum_type=SpectrumType.NMR_1H,
        x_values=[1.0, 2.5, 7.3],
        y_values=[3.0, 2.0, 5.0],
        title="Test NMR",
        origin="unit test",
    )
    text = write_jcamp(spec)
    assert "##TITLE=Test NMR" in text
    assert "##DATA TYPE=NMR SPECTRUM" in text
    assert "##XYPOINTS=(XY..XY)" in text

    restored = parse_jcamp(text)
    assert restored.spectrum_type == SpectrumType.NMR_1H
    assert restored.title == "Test NMR"
    assert len(restored.x_values) == 3
    assert restored.x_values[0] == pytest.approx(1.0)
    assert restored.y_values[2] == pytest.approx(5.0)


def test_write_read_ir_continuous_roundtrip() -> None:
    xs = [500.0 + i * 10.0 for i in range(200)]
    ys = [100.0 - i * 0.1 for i in range(200)]
    spec = Spectrum(
        id=1,
        spectrum_type=SpectrumType.IR,
        x_values=xs,
        y_values=ys,
        title="IR trace",
    )
    text = write_jcamp(spec)
    assert "##XYDATA=(X++(Y..Y))" in text
    assert "##FIRSTX=500.0000" in text

    restored = parse_jcamp(text)
    assert restored.spectrum_type == SpectrumType.IR
    assert restored.n_points == 200
    assert restored.x_values[0] == pytest.approx(500.0)
    assert restored.x_values[-1] == pytest.approx(2490.0)


def test_parse_empty_raises() -> None:
    with pytest.raises(JcampError):
        parse_jcamp("")


def test_parse_missing_data_block_raises() -> None:
    text = "##TITLE=Nothing\n##JCAMP-DX=4.24\n##END=\n"
    with pytest.raises(JcampError):
        parse_jcamp(text)


def test_data_type_classification() -> None:
    text = """##TITLE=IR test
##JCAMP-DX=4.24
##DATA TYPE=INFRARED SPECTRUM
##XUNITS=1/CM
##YUNITS=TRANSMITTANCE
##NPOINTS=2
##XYPOINTS=(XY..XY)
1500, 90
1700, 80
##END=
"""
    spec = parse_jcamp(text)
    assert spec.spectrum_type == SpectrumType.IR


def test_mass_spectrum_classification() -> None:
    text = """##TITLE=MS test
##JCAMP-DX=4.24
##DATA TYPE=MASS SPECTRUM
##XUNITS=M/Z
##YUNITS=RELATIVE ABUNDANCE
##NPOINTS=1
##XYPOINTS=(XY..XY)
100, 100
##END=
"""
    spec = parse_jcamp(text)
    assert spec.spectrum_type == SpectrumType.MS


def test_file_roundtrip() -> None:
    spec = Spectrum(
        id=1,
        spectrum_type=SpectrumType.MS,
        x_values=[120.0, 105.0, 91.0],
        y_values=[100.0, 45.0, 30.0],
        peaks=[Peak(x=120.0, intensity=100.0, label="M⁺")],
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.jdx"
        write_jcamp_file(spec, path)
        restored = read_jcamp_file(path)
    assert restored.n_points == 3
    assert restored.x_values[0] == pytest.approx(120.0)
