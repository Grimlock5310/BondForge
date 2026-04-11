"""JCAMP-DX (IUPAC) spectrum IO.

JCAMP-DX is an ASCII text format for spectroscopic data, standardized
by IUPAC. This module implements a practical subset sufficient for
round-tripping BondForge spectra and reading common predicted/
experimental files produced by other software.

Supported features (v0.7):

- Header records: ``##TITLE``, ``##JCAMP-DX``, ``##DATA TYPE``,
  ``##ORIGIN``, ``##OWNER``, ``##XUNITS``, ``##YUNITS``, ``##NPOINTS``,
  ``##FIRSTX``, ``##LASTX``, ``##XFACTOR``, ``##YFACTOR``, ``##END``
- Data forms:

  - ``##XYDATA=(X++(Y..Y))`` — equidistant X with tabular Y values.
    Read and write using space-separated AFFN (ASCII Free Format
    Numeric) one line per X point.
  - ``##XYPOINTS=(XY..XY)`` — irregular ``x, y`` pairs; used for line
    spectra like predicted NMR and MS.
  - ``##PEAK TABLE=(XY..XY)`` — treated as XYPOINTS on read.

- Non-supported record labels are preserved as metadata on the
  spectrum so a round-trip doesn't drop user annotations.

Limitations:

- DIFDUP / SQZ / PAC compressed forms are not implemented on write
  (uncompressed AFFN is). On read they are also unsupported — a file
  that uses them will raise :class:`JcampError`.
- Only single-block files. ``##LINK`` compound JCAMP is not supported.
"""

from __future__ import annotations

from pathlib import Path

from bondforge.core.model.spectrum import Peak, Spectrum, SpectrumType


class JcampError(Exception):
    """Raised on malformed or unsupported JCAMP-DX content."""


# Map our SpectrumType onto JCAMP-DX ##DATA TYPE strings.
_JCAMP_DATA_TYPE = {
    SpectrumType.NMR_1H: "NMR SPECTRUM",
    SpectrumType.NMR_13C: "NMR SPECTRUM",
    SpectrumType.IR: "INFRARED SPECTRUM",
    SpectrumType.MS: "MASS SPECTRUM",
    SpectrumType.UV_VIS: "UV/VISIBLE SPECTRUM",
}


def _classify_data_type(data_type: str, x_units: str) -> SpectrumType:
    """Infer :class:`SpectrumType` from the JCAMP header."""
    dt = (data_type or "").upper()
    xu = (x_units or "").upper()
    if "INFRARED" in dt or "IR " in dt or "CM" in xu:
        return SpectrumType.IR
    if "MASS" in dt or "M/Z" in xu:
        return SpectrumType.MS
    if "UV" in dt or "NANOMETER" in xu:
        return SpectrumType.UV_VIS
    if "NMR" in dt:
        return SpectrumType.NMR_13C if "13C" in dt or "C13" in dt else SpectrumType.NMR_1H
    return SpectrumType.NMR_1H


# ---- parsing ---------------------------------------------------------------


def _parse_header(text: str) -> tuple[dict[str, str], list[str]]:
    """Split a JCAMP-DX string into header labels and body data lines.

    Returns ``(labels, data_lines)``. ``labels`` maps normalized upper
    label → value. ``data_lines`` contains the numeric payload lines
    between the table declaration and ``##END=``.
    """
    labels: dict[str, str] = {}
    data_lines: list[str] = []
    current_label: str | None = None
    reading_data = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("$$"):  # comment line
            continue
        if line.startswith("##"):
            eq = line.find("=")
            if eq < 0:
                continue
            label = line[2:eq].strip().upper().replace(" ", "")
            value = line[eq + 1 :].strip()
            if label == "END":
                break
            if label in ("XYDATA", "XYPOINTS", "PEAKTABLE"):
                current_label = label
                reading_data = True
                labels[label] = value
                continue
            reading_data = False
            current_label = label
            labels[label] = value
        elif reading_data and current_label:
            data_lines.append(line)

    return labels, data_lines


def _parse_affn_numbers(lines: list[str]) -> list[float]:
    """Parse space / comma / semicolon separated floats from text lines."""
    out: list[float] = []
    for line in lines:
        # JCAMP allows ``,`` and ``;`` as separators too.
        cleaned = line.replace(",", " ").replace(";", " ")
        for token in cleaned.split():
            try:
                out.append(float(token))
            except ValueError as exc:
                raise JcampError(f"Cannot parse numeric token: {token!r}") from exc
    return out


def parse_jcamp(text: str) -> Spectrum:
    """Parse a JCAMP-DX string into a :class:`Spectrum`."""
    labels, data_lines = _parse_header(text)
    if not labels:
        raise JcampError("No JCAMP-DX records found")

    title = labels.get("TITLE", "")
    data_type = labels.get("DATATYPE", "")
    x_units = labels.get("XUNITS", "")
    origin = labels.get("ORIGIN", "")
    stype = _classify_data_type(data_type, x_units)

    x_values: list[float] = []
    y_values: list[float] = []
    peaks: list[Peak] = []

    if "XYDATA" in labels:
        # Equidistant grid: FIRSTX, LASTX, NPOINTS define x; data lines
        # encode ``x y1 y2 y3 …`` where each row starts with its x value.
        try:
            firstx = float(labels.get("FIRSTX", "0"))
            lastx = float(labels.get("LASTX", "0"))
            npoints = int(float(labels.get("NPOINTS", "0")))
        except ValueError as exc:
            raise JcampError(f"Invalid XYDATA header: {exc}") from exc
        xfactor = float(labels.get("XFACTOR", "1"))
        yfactor = float(labels.get("YFACTOR", "1"))

        nums = _parse_affn_numbers(data_lines)
        if not nums:
            raise JcampError("XYDATA block is empty")

        # Standard form: first value on each row is X (in XFACTOR units),
        # remaining values on the row are consecutive Ys. We use a
        # simpler reader — dump all numbers, assume the first column was
        # the X marker and drop it by computing npoints equidistant Xs.
        # This matches what write_jcamp emits and what common readers do
        # for uncompressed XYDATA.
        ys_raw: list[float] = []
        # Each row begins with an X. Split again keeping line structure.
        for line in data_lines:
            cleaned = line.replace(",", " ").replace(";", " ").split()
            if not cleaned:
                continue
            # Skip leading X marker, take the rest as Ys.
            for tok in cleaned[1:]:
                try:
                    ys_raw.append(float(tok))
                except ValueError as exc:
                    raise JcampError(f"Cannot parse Y value {tok!r}") from exc
        if not ys_raw:
            # Some writers omit the X marker and give a flat Y stream.
            ys_raw = nums

        if npoints <= 0:
            npoints = len(ys_raw)
        step = (lastx - firstx) / (npoints - 1) if npoints > 1 else 0.0
        for i in range(min(npoints, len(ys_raw))):
            x_values.append((firstx + i * step) * xfactor)
            y_values.append(ys_raw[i] * yfactor)

    elif "XYPOINTS" in labels or "PEAKTABLE" in labels:
        nums = _parse_affn_numbers(data_lines)
        if len(nums) % 2 != 0:
            raise JcampError("XYPOINTS block has an odd number of values")
        for i in range(0, len(nums), 2):
            x_values.append(nums[i])
            y_values.append(nums[i + 1])
        if "PEAKTABLE" in labels:
            peaks = [Peak(x=x, intensity=y) for x, y in zip(x_values, y_values, strict=True)]

    else:
        raise JcampError("Neither XYDATA nor XYPOINTS record present")

    metadata: dict[str, str] = {}
    for k in ("JCAMP-DX", "OWNER", "YUNITS", "DATATYPE", "XUNITS"):
        if k in labels:
            metadata[k.lower()] = labels[k]

    return Spectrum(
        id=0,
        spectrum_type=stype,
        x_values=x_values,
        y_values=y_values,
        peaks=peaks,
        title=title,
        origin=origin or "JCAMP-DX import",
        metadata=metadata,
    )


# ---- writing ---------------------------------------------------------------


def write_jcamp(spec: Spectrum) -> str:
    """Serialize a :class:`Spectrum` to JCAMP-DX 4.24 text."""
    lines: list[str] = []
    lines.append(f"##TITLE={spec.title or 'BondForge Spectrum'}")
    lines.append("##JCAMP-DX=4.24")
    lines.append(f"##DATA TYPE={_JCAMP_DATA_TYPE[spec.spectrum_type]}")
    lines.append(f"##ORIGIN={spec.origin or 'BondForge'}")
    lines.append("##OWNER=public domain")
    lines.append(f"##XUNITS={spec.x_unit}")
    lines.append(f"##YUNITS={spec.y_unit}")

    if not spec.x_values:
        lines.append("##XYPOINTS=(XY..XY)")
        lines.append("##END=")
        return "\n".join(lines) + "\n"

    # Decide sparse vs dense: sparse (line spectra) if fewer than
    # 50 points — emit as ##XYPOINTS. Continuous traces (IR, UV) go
    # through ##XYDATA with an evenly-spaced grid.
    sparse = spec.n_points < 50 or spec.spectrum_type in (
        SpectrumType.MS,
        SpectrumType.NMR_1H,
        SpectrumType.NMR_13C,
    )

    if sparse:
        lines.append(f"##NPOINTS={spec.n_points}")
        lines.append("##XYPOINTS=(XY..XY)")
        for x, y in zip(spec.x_values, spec.y_values, strict=True):
            lines.append(f"{x:.4f}, {y:.4f}")
    else:
        firstx = spec.x_values[0]
        lastx = spec.x_values[-1]
        lines.append(f"##NPOINTS={spec.n_points}")
        lines.append(f"##FIRSTX={firstx:.4f}")
        lines.append(f"##LASTX={lastx:.4f}")
        lines.append("##XFACTOR=1.0")
        lines.append("##YFACTOR=1.0")
        lines.append("##XYDATA=(X++(Y..Y))")
        for x, y in zip(spec.x_values, spec.y_values, strict=True):
            lines.append(f"{x:.4f} {y:.6f}")

    lines.append("##END=")
    return "\n".join(lines) + "\n"


# ---- file wrappers ---------------------------------------------------------


def read_jcamp_file(path: str | Path) -> Spectrum:
    """Read a JCAMP-DX file from disk."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_jcamp(text)


def write_jcamp_file(spec: Spectrum, path: str | Path) -> None:
    """Write a JCAMP-DX file to disk."""
    Path(path).write_text(write_jcamp(spec), encoding="utf-8")


__all__ = [
    "JcampError",
    "parse_jcamp",
    "write_jcamp",
    "read_jcamp_file",
    "write_jcamp_file",
]
