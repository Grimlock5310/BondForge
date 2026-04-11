"""Spectrum — 1D spectroscopic data (NMR, IR, MS, UV/Vis).

A :class:`Spectrum` is a pair of parallel numeric arrays (``x_values``,
``y_values``) plus metadata describing the axis conventions, units,
origin, and a list of discrete ``peaks`` used for annotation and peak
picking.

Supported spectrum types (v0.7):

- ``NMR_1H`` — proton NMR, x=ppm (decreasing left-to-right), y=intensity
- ``NMR_13C`` — carbon-13 NMR, x=ppm (decreasing left-to-right)
- ``IR`` — infrared absorption, x=wavenumber cm⁻¹ (decreasing L→R), y=%T
- ``MS`` — mass spectrum, x=m/z, y=relative intensity (0–100)
- ``UV_VIS`` — UV/visible absorption, x=nm, y=absorbance

Intensities are stored as Python floats. For sparse line spectra such as
MS or the stick plots used for predicted NMR, ``x_values`` and
``y_values`` hold just the line positions; a continuous envelope can be
computed on demand by the viewer. Continuous spectra (IR, experimental
NMR) store the full ``(x, y)`` trace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SpectrumType(Enum):
    """The five spectrum flavors recognized by the viewer."""

    NMR_1H = "1H NMR"
    NMR_13C = "13C NMR"
    IR = "IR"
    MS = "MS"
    UV_VIS = "UV/Vis"

    @property
    def x_unit(self) -> str:
        return {
            SpectrumType.NMR_1H: "ppm",
            SpectrumType.NMR_13C: "ppm",
            SpectrumType.IR: "cm⁻¹",
            SpectrumType.MS: "m/z",
            SpectrumType.UV_VIS: "nm",
        }[self]

    @property
    def y_unit(self) -> str:
        return {
            SpectrumType.NMR_1H: "intensity",
            SpectrumType.NMR_13C: "intensity",
            SpectrumType.IR: "%T",
            SpectrumType.MS: "relative intensity",
            SpectrumType.UV_VIS: "absorbance",
        }[self]

    @property
    def x_reversed(self) -> bool:
        """True if the x-axis is conventionally drawn high→low (NMR, IR)."""
        return self in (SpectrumType.NMR_1H, SpectrumType.NMR_13C, SpectrumType.IR)


@dataclass
class Peak:
    """A single annotated peak in a spectrum.

    ``x`` is in the spectrum's x-unit (ppm, cm⁻¹, m/z, nm). ``intensity``
    is in the spectrum's y-unit. ``label`` is an optional display string
    such as ``"CH₃"`` or ``"M⁺"``. ``multiplicity`` is NMR-specific
    (``"s"``, ``"d"``, ``"t"``, ``"q"``, ``"m"``) and empty for other
    spectrum types.
    """

    x: float
    intensity: float = 1.0
    label: str = ""
    multiplicity: str = ""


@dataclass
class Spectrum:
    """A 1D spectroscopic dataset.

    Parallel-array layout: ``x_values[i]`` and ``y_values[i]`` define one
    sample. For predicted line spectra (NMR stick plots, MS) the arrays
    hold just the discrete lines; the viewer draws vertical sticks. For
    continuous spectra the arrays hold the full trace and the viewer
    draws a polyline.
    """

    id: int
    spectrum_type: SpectrumType
    x_values: list[float] = field(default_factory=list)
    y_values: list[float] = field(default_factory=list)
    peaks: list[Peak] = field(default_factory=list)
    title: str = ""
    origin: str = ""  # "predicted", "experimental", "JCAMP-DX import", …
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.x_values) != len(self.y_values):
            raise ValueError(
                f"x_values and y_values must be the same length "
                f"({len(self.x_values)} vs {len(self.y_values)})"
            )

    @property
    def x_unit(self) -> str:
        return self.spectrum_type.x_unit

    @property
    def y_unit(self) -> str:
        return self.spectrum_type.y_unit

    @property
    def n_points(self) -> int:
        return len(self.x_values)

    def x_range(self) -> tuple[float, float]:
        """Return ``(xmin, xmax)`` across both samples and peaks."""
        xs: list[float] = list(self.x_values)
        xs.extend(p.x for p in self.peaks)
        if not xs:
            return (0.0, 1.0)
        return (min(xs), max(xs))

    def y_range(self) -> tuple[float, float]:
        """Return ``(ymin, ymax)`` across both samples and peaks."""
        ys: list[float] = list(self.y_values)
        ys.extend(p.intensity for p in self.peaks)
        if not ys:
            return (0.0, 1.0)
        return (min(ys), max(ys))


__all__ = ["Spectrum", "SpectrumType", "Peak"]
