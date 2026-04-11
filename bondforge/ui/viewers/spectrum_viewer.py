"""Spectrum viewer — native QPainter 1D plot widget.

A lightweight QWidget that draws a :class:`Spectrum` directly with
QPainter. It handles both sparse "stick" plots (predicted NMR, MS) and
continuous polyline traces (IR, UV/Vis), auto-reverses the x-axis for
NMR and IR, and supports mouse wheel zoom on the x-range plus middle-
drag panning.

The viewer aims to look like the figures chemists are used to:

- Per-spectrum-type colour schemes (NMR blue, IR green, MS purple).
- "Nice" tick spacing (1-2-5 rounding) so axis labels never read
  `2.873` and always include a sensible number of decimals.
- Y-axis ticks and labels alongside the existing x-axis.
- Subtitle line under the title summarising metadata
  (frequency / solvent / ionization).
- Filled IR trace below the polyline for better visual contrast.
- Stick-plot peak labels are vertically staggered to avoid overlap.
- IR labels go at the trough (just below the dip) so the dotted
  guide visually points at the corresponding band.

No WebEngine, no matplotlib — works fully offline, matches the
existing 3D viewer's philosophy (see ``viewer_3d.py``).
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPen,
    QPolygonF,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from bondforge.core.model.spectrum import Spectrum, SpectrumType

# Background + axis colors, tuned for the app's light theme.
_BACKGROUND = QColor(252, 252, 250)
_AXIS_COLOR = QColor(60, 60, 60)
_GRID_COLOR = QColor(228, 228, 228)
_SUBTITLE_COLOR = QColor(110, 110, 110)
_PEAK_LABEL_COLOR = QColor(80, 20, 140)
_EMPTY_TEXT_COLOR = QColor(160, 160, 160)

# Trace + label colours per spectrum type. Each entry is
# (trace, fill, label) — fill is the polyline-fill colour for IR.
_THEME: dict[SpectrumType, tuple[QColor, QColor, QColor]] = {
    SpectrumType.NMR_1H: (QColor(20, 70, 170), QColor(0, 0, 0, 0), QColor(40, 80, 150)),
    SpectrumType.NMR_13C: (QColor(20, 70, 170), QColor(0, 0, 0, 0), QColor(40, 80, 150)),
    SpectrumType.IR: (QColor(20, 110, 70), QColor(20, 110, 70, 35), QColor(30, 90, 60)),
    SpectrumType.MS: (QColor(110, 30, 130), QColor(0, 0, 0, 0), QColor(80, 20, 110)),
    SpectrumType.UV_VIS: (QColor(180, 70, 30), QColor(180, 70, 30, 35), QColor(140, 50, 20)),
}

_MARGIN_LEFT = 70
_MARGIN_RIGHT = 24
_MARGIN_TOP = 50
_MARGIN_BOTTOM = 60


def _nice_step(span: float, target_ticks: int = 8) -> float:
    """Return a 1-2-5 step that yields roughly ``target_ticks`` ticks."""
    if span <= 0:
        return 1.0
    raw = span / max(target_ticks, 1)
    exp = math.floor(math.log10(raw))
    base = raw / (10**exp)
    if base < 1.5:
        nice = 1.0
    elif base < 3.5:
        nice = 2.0
    elif base < 7.5:
        nice = 5.0
    else:
        nice = 10.0
    return nice * (10**exp)


def _decimals_for_step(step: float) -> int:
    """How many decimal places make sense for a given tick step."""
    if step >= 10:
        return 0
    if step >= 1:
        return 1
    return max(0, int(math.ceil(-math.log10(step))) + 1)


class SpectrumViewer(QWidget):
    """Widget that renders a single :class:`Spectrum`.

    Controls:
    - Mouse wheel: zoom in/out on the x-range (centered on the cursor).
    - Middle-button drag: pan horizontally.
    - Double-click: reset view to full range.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(560, 340)
        self._spectrum: Spectrum | None = None
        self._x_min: float = 0.0
        self._x_max: float = 1.0
        self._full_x_min: float = 0.0
        self._full_x_max: float = 1.0
        self._pan_last: QPointF | None = None

    # ----- public API ------------------------------------------------------

    def set_spectrum(self, spectrum: Spectrum | None) -> None:
        """Load a spectrum into the viewer (or clear with ``None``)."""
        self._spectrum = spectrum
        if spectrum is None or not spectrum.x_values:
            self._x_min = 0.0
            self._x_max = 1.0
        else:
            self._full_x_min, self._full_x_max = spectrum.x_range()
            # Pad 4% on either side so peaks at the edges don't touch.
            span = self._full_x_max - self._full_x_min or 1.0
            pad = span * 0.04
            self._full_x_min -= pad
            self._full_x_max += pad
            self._x_min = self._full_x_min
            self._x_max = self._full_x_max
        self.update()

    def spectrum(self) -> Spectrum | None:
        return self._spectrum

    def reset_view(self) -> None:
        """Restore the default full x-range."""
        self._x_min = self._full_x_min
        self._x_max = self._full_x_max
        self.update()

    # ----- events ----------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if self._spectrum is None:
            return
        delta = event.angleDelta().y()
        factor = 0.85 if delta > 0 else 1.0 / 0.85
        cursor_x = self._screen_to_data_x(event.position().x())
        new_span = (self._x_max - self._x_min) * factor
        fraction = (cursor_x - self._x_min) / max(self._x_max - self._x_min, 1e-9)
        self._x_min = cursor_x - new_span * fraction
        self._x_max = cursor_x + new_span * (1 - fraction)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_last = event.position()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._pan_last is not None and self._spectrum is not None:
            pos = event.position()
            dx_px = pos.x() - self._pan_last.x()
            plot_w = max(self.width() - _MARGIN_LEFT - _MARGIN_RIGHT, 1)
            dx_data = dx_px * (self._x_max - self._x_min) / plot_w
            if self._spectrum.spectrum_type.x_reversed:
                dx_data = -dx_data
            self._x_min -= dx_data
            self._x_max -= dx_data
            self._pan_last = pos
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_last = None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.reset_view()

    # ----- coordinate helpers ---------------------------------------------

    def _plot_rect(self) -> QRectF:
        return QRectF(
            _MARGIN_LEFT,
            _MARGIN_TOP,
            max(self.width() - _MARGIN_LEFT - _MARGIN_RIGHT, 1),
            max(self.height() - _MARGIN_TOP - _MARGIN_BOTTOM, 1),
        )

    def _data_to_screen(
        self, x: float, y: float, y_min: float, y_max: float, rect: QRectF
    ) -> QPointF:
        assert self._spectrum is not None
        x_span = self._x_max - self._x_min or 1.0
        fx = (x - self._x_min) / x_span
        if self._spectrum.spectrum_type.x_reversed:
            fx = 1.0 - fx
        y_span = y_max - y_min or 1.0
        fy = (y - y_min) / y_span
        sx = rect.left() + fx * rect.width()
        sy = rect.bottom() - fy * rect.height()
        return QPointF(sx, sy)

    def _screen_to_data_x(self, sx: float) -> float:
        rect = self._plot_rect()
        fx = (sx - rect.left()) / max(rect.width(), 1.0)
        if self._spectrum is not None and self._spectrum.spectrum_type.x_reversed:
            fx = 1.0 - fx
        return self._x_min + fx * (self._x_max - self._x_min)

    # ----- painting --------------------------------------------------------

    def _subtitle_text(self) -> str:
        if self._spectrum is None:
            return ""
        meta = self._spectrum.metadata
        bits: list[str] = []
        # Friendly metadata snippets per spectrum type.
        for key in (
            "frequency",
            "solvent",
            "reference",
            "sample",
            "resolution",
            "ionization",
            "formula",
            "monoisotopic",
        ):
            if key in meta and meta[key]:
                bits.append(f"{meta[key]}")
        return "  ·  ".join(bits)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(0, 0, self.width(), self.height(), _BACKGROUND)

        if self._spectrum is None or self._spectrum.n_points == 0:
            painter.setPen(_EMPTY_TEXT_COLOR)
            painter.drawText(
                QRectF(0, 0, self.width(), self.height()),
                Qt.AlignmentFlag.AlignCenter,
                "No spectrum loaded",
            )
            painter.end()
            return

        spec = self._spectrum
        rect = self._plot_rect()
        trace_color, fill_color, label_color = _THEME.get(
            spec.spectrum_type, (QColor(30, 80, 180), QColor(0, 0, 0, 0), _PEAK_LABEL_COLOR)
        )

        # ---- Y range -----------------------------------------------------
        y_min, y_max = spec.y_range()
        if spec.spectrum_type == SpectrumType.IR:
            y_min, y_max = 0.0, 105.0
        elif spec.spectrum_type == SpectrumType.MS:
            y_min, y_max = 0.0, max(y_max * 1.10, 110.0)
        else:
            # NMR / UV: pad the top so labels have room.
            y_min = 0.0 if y_min >= 0 else y_min
            y_max = (y_max if y_max != y_min else y_min + 1.0) * 1.18

        # ---- Grid + ticks ------------------------------------------------
        x_span = self._x_max - self._x_min
        x_step = _nice_step(x_span)
        x_decimals = _decimals_for_step(x_step)
        y_span = y_max - y_min
        y_step = _nice_step(y_span, target_ticks=5)
        y_decimals = _decimals_for_step(y_step)

        painter.setPen(QPen(_GRID_COLOR, 1, Qt.PenStyle.DashLine))
        # Vertical grid lines aligned to data X ticks.
        x_tick_start = math.ceil(self._x_min / x_step) * x_step
        x_ticks: list[float] = []
        x = x_tick_start
        while x <= self._x_max + 1e-9:
            x_ticks.append(x)
            x += x_step
        for xv in x_ticks:
            sp = self._data_to_screen(xv, y_min, y_min, y_max, rect)
            painter.drawLine(QPointF(sp.x(), rect.top()), QPointF(sp.x(), rect.bottom()))
        # Horizontal grid lines on Y ticks.
        y_tick_start = math.ceil(y_min / y_step) * y_step
        y_ticks: list[float] = []
        yv = y_tick_start
        while yv <= y_max + 1e-9:
            y_ticks.append(yv)
            yv += y_step
        for yv in y_ticks:
            sp = self._data_to_screen(self._x_min, yv, y_min, y_max, rect)
            painter.drawLine(QPointF(rect.left(), sp.y()), QPointF(rect.right(), sp.y()))

        # ---- Axis box ----------------------------------------------------
        painter.setPen(QPen(_AXIS_COLOR, 1.2))
        painter.drawRect(rect)

        # ---- Trace -------------------------------------------------------
        if spec.spectrum_type == SpectrumType.IR:
            self._draw_ir_trace(painter, spec, y_min, y_max, rect, trace_color, fill_color)
        elif spec.spectrum_type == SpectrumType.UV_VIS:
            self._draw_polyline_trace(painter, spec, y_min, y_max, rect, trace_color, fill_color)
        else:
            self._draw_stick_trace(painter, spec, y_min, y_max, rect, trace_color)

        # ---- Tick labels (drawn on top of trace) -------------------------
        painter.setPen(QPen(_AXIS_COLOR, 1))
        tick_font = QFont()
        tick_font.setPointSize(8)
        painter.setFont(tick_font)
        for xv in x_ticks:
            sp = self._data_to_screen(xv, y_min, y_min, y_max, rect)
            painter.drawLine(QPointF(sp.x(), rect.bottom()), QPointF(sp.x(), rect.bottom() + 4))
            painter.drawText(
                QRectF(sp.x() - 32, rect.bottom() + 5, 64, 14),
                Qt.AlignmentFlag.AlignCenter,
                f"{xv:.{x_decimals}f}",
            )
        for yv in y_ticks:
            sp = self._data_to_screen(self._x_min, yv, y_min, y_max, rect)
            painter.drawLine(QPointF(rect.left() - 4, sp.y()), QPointF(rect.left(), sp.y()))
            painter.drawText(
                QRectF(0, sp.y() - 7, _MARGIN_LEFT - 6, 14),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{yv:.{y_decimals}f}",
            )

        # ---- Axis titles -------------------------------------------------
        axis_label_font = QFont()
        axis_label_font.setPointSize(9)
        painter.setFont(axis_label_font)
        painter.setPen(_AXIS_COLOR)
        painter.drawText(
            QRectF(0, self.height() - _MARGIN_BOTTOM + 22, self.width(), 18),
            Qt.AlignmentFlag.AlignCenter,
            f"{spec.x_unit}",
        )
        # Vertical y-axis label.
        painter.save()
        painter.translate(14, rect.top() + rect.height() / 2)
        painter.rotate(-90)
        painter.drawText(
            QRectF(-rect.height() / 2, -10, rect.height(), 18),
            Qt.AlignmentFlag.AlignCenter,
            f"{spec.y_unit}",
        )
        painter.restore()

        # ---- Title and subtitle ------------------------------------------
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)
        painter.setFont(title_font)
        painter.setPen(_AXIS_COLOR)
        title_text = spec.title
        if spec.origin and spec.origin != "predicted":
            title_text += f"   [{spec.origin}]"
        painter.drawText(QRectF(0, 6, self.width(), 18), Qt.AlignmentFlag.AlignCenter, title_text)

        subtitle = self._subtitle_text()
        if subtitle:
            sub_font = QFont()
            sub_font.setPointSize(8)
            painter.setFont(sub_font)
            painter.setPen(_SUBTITLE_COLOR)
            painter.drawText(
                QRectF(0, 25, self.width(), 14),
                Qt.AlignmentFlag.AlignCenter,
                subtitle,
            )

        # ---- Peak labels (collision-aware staggering) --------------------
        self._draw_peak_labels(painter, spec, y_min, y_max, rect, label_color)

        painter.end()

    # ----- trace painters --------------------------------------------------

    def _draw_polyline_trace(
        self,
        painter: QPainter,
        spec: Spectrum,
        y_min: float,
        y_max: float,
        rect: QRectF,
        trace_color: QColor,
        fill_color: QColor,
    ) -> None:
        """Draw a continuous polyline (UV/Vis style)."""
        pts: list[QPointF] = []
        for x, y in zip(spec.x_values, spec.y_values, strict=True):
            if not (self._x_min <= x <= self._x_max):
                continue
            pts.append(self._data_to_screen(x, y, y_min, y_max, rect))
        if len(pts) < 2:
            return
        if fill_color.alpha() > 0:
            poly = QPolygonF(
                [*pts, QPointF(pts[-1].x(), rect.bottom()), QPointF(pts[0].x(), rect.bottom())]
            )
            painter.setBrush(fill_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(poly)
        painter.setPen(QPen(trace_color, 1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for a, b in zip(pts, pts[1:], strict=False):
            painter.drawLine(a, b)

    def _draw_ir_trace(
        self,
        painter: QPainter,
        spec: Spectrum,
        y_min: float,
        y_max: float,
        rect: QRectF,
        trace_color: QColor,
        fill_color: QColor,
    ) -> None:
        """Draw the IR transmittance polyline with a soft fill above."""
        pts: list[QPointF] = []
        for x, y in zip(spec.x_values, spec.y_values, strict=True):
            if not (self._x_min <= x <= self._x_max):
                continue
            pts.append(self._data_to_screen(x, y, y_min, y_max, rect))
        if len(pts) < 2:
            return
        # Fill the area between the trace and the top of the plot — that
        # gives the dips visual weight without inverting the curve.
        if fill_color.alpha() > 0:
            poly = QPolygonF(
                [
                    QPointF(pts[0].x(), rect.top()),
                    *pts,
                    QPointF(pts[-1].x(), rect.top()),
                ]
            )
            gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            top_col = QColor(fill_color)
            top_col.setAlpha(20)
            bot_col = QColor(fill_color)
            bot_col.setAlpha(60)
            gradient.setColorAt(0.0, top_col)
            gradient.setColorAt(1.0, bot_col)
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(poly)
        painter.setPen(QPen(trace_color, 1.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for a, b in zip(pts, pts[1:], strict=False):
            painter.drawLine(a, b)

    def _draw_stick_trace(
        self,
        painter: QPainter,
        spec: Spectrum,
        y_min: float,
        y_max: float,
        rect: QRectF,
        trace_color: QColor,
    ) -> None:
        """Draw vertical sticks from baseline to peak (NMR / MS)."""
        baseline_y = self._data_to_screen(self._x_min, 0.0, y_min, y_max, rect).y()
        baseline_y = min(baseline_y, rect.bottom())
        painter.setPen(QPen(trace_color, 1.6))
        for x, y in zip(spec.x_values, spec.y_values, strict=True):
            if not (self._x_min <= x <= self._x_max):
                continue
            p = self._data_to_screen(x, y, y_min, y_max, rect)
            painter.drawLine(QPointF(p.x(), baseline_y), QPointF(p.x(), p.y()))
        # A faint baseline line for visual grounding.
        painter.setPen(QPen(_AXIS_COLOR, 0.7))
        painter.drawLine(
            QPointF(rect.left(), baseline_y),
            QPointF(rect.right(), baseline_y),
        )

    # ----- peak labels -----------------------------------------------------

    def _draw_peak_labels(
        self,
        painter: QPainter,
        spec: Spectrum,
        y_min: float,
        y_max: float,
        rect: QRectF,
        label_color: QColor,
    ) -> None:
        label_font = QFont()
        label_font.setPointSize(8)
        painter.setFont(label_font)
        metrics = QFontMetrics(label_font)
        painter.setPen(label_color)

        # Pick which peaks deserve a label. For IR, sort by stash priority
        # (lower = more diagnostic). For NMR/MS, sort by intensity. Cap at
        # twelve labels to avoid overcrowding.
        candidates = [p for p in spec.peaks if p.label]
        if spec.spectrum_type == SpectrumType.IR:

            def ir_key(peak):
                try:
                    prio = int(peak.multiplicity) if peak.multiplicity else 5
                except ValueError:
                    prio = 5
                return (prio, -peak.intensity)

            candidates.sort(key=ir_key)
        else:
            candidates.sort(key=lambda p: -p.intensity)
        candidates = candidates[:12]

        # Track placed label rects so we can stagger overlapping ones.
        placed_rects: list[QRectF] = []

        for peak in candidates:
            if not (self._x_min <= peak.x <= self._x_max):
                continue
            anchor = self._data_to_screen(peak.x, peak.intensity, y_min, y_max, rect)
            text = peak.label
            text_w = metrics.horizontalAdvance(text) + 4
            text_h = metrics.height()

            if spec.spectrum_type == SpectrumType.IR:
                # Place below the trough (transmittance dip).
                base_y = anchor.y() + 14
                base_x = anchor.x() - text_w / 2
            else:
                # Above the stick (or above the M⁺ peak for MS).
                base_y = anchor.y() - text_h - 2
                base_x = anchor.x() - text_w / 2

            # Stagger downward (for IR) or upward (for sticks) until no
            # collision is detected, but don't push out of the plot rect.
            label_rect = QRectF(base_x, base_y, text_w, text_h)
            attempts = 0
            while attempts < 6 and any(label_rect.intersects(r) for r in placed_rects):
                if spec.spectrum_type == SpectrumType.IR:
                    label_rect.translate(0, text_h + 1)
                else:
                    label_rect.translate(0, -(text_h + 1))
                attempts += 1
            # Skip if pushed out of the plot region.
            if not rect.intersects(label_rect):
                continue
            placed_rects.append(QRectF(label_rect))

            # Optional dotted guide line from anchor to label edge.
            painter.setPen(QPen(label_color, 0.6, Qt.PenStyle.DotLine))
            mid_x = label_rect.center().x()
            painter.drawLine(
                QPointF(anchor.x(), anchor.y()), QPointF(mid_x, label_rect.center().y())
            )
            painter.setPen(label_color)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, text)


__all__ = ["SpectrumViewer"]
