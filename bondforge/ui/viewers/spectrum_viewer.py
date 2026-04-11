"""Spectrum viewer — native QPainter 1D plot widget.

A lightweight QWidget that draws a :class:`Spectrum` directly with
QPainter. It handles both sparse "stick" plots (predicted NMR, MS) and
continuous polyline traces (IR, UV/Vis), auto-reverses the x-axis for
NMR and IR, and supports mouse wheel zoom on the x-range plus middle-
drag panning.

No WebEngine, no matplotlib — works fully offline, matches the
existing 3D viewer's philosophy (see ``viewer_3d.py``).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from bondforge.core.model.spectrum import Spectrum, SpectrumType

# Background + trace colours, picked to match the app's light theme.
_BACKGROUND = QColor(252, 252, 250)
_AXIS_COLOR = QColor(60, 60, 60)
_GRID_COLOR = QColor(225, 225, 225)
_TRACE_COLOR = QColor(30, 80, 180)
_PEAK_LABEL_COLOR = QColor(80, 20, 140)
_EMPTY_TEXT_COLOR = QColor(160, 160, 160)

_MARGIN_LEFT = 60
_MARGIN_RIGHT = 20
_MARGIN_TOP = 30
_MARGIN_BOTTOM = 45


class SpectrumViewer(QWidget):
    """Widget that renders a single :class:`Spectrum`.

    Controls:
    - Mouse wheel: zoom in/out on the x-range (centered on the cursor).
    - Middle-button drag: pan horizontally.
    - Double-click: reset view to full range.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(500, 300)
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
            # Pad 3% on either side so peaks at the edges don't touch.
            span = self._full_x_max - self._full_x_min or 1.0
            pad = span * 0.03
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
        # Zoom centered on the cursor position.
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

        rect = self._plot_rect()
        y_min, y_max = self._spectrum.y_range()
        if y_max == y_min:
            y_max = y_min + 1.0
        # For %T (IR), axis bottom is 0 and top is 105.
        if self._spectrum.spectrum_type == SpectrumType.IR:
            y_min, y_max = 0.0, 105.0

        # Draw grid lines.
        painter.setPen(QPen(_GRID_COLOR, 1, Qt.PenStyle.DashLine))
        for i in range(1, 10):
            x = rect.left() + i * rect.width() / 10
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        for i in range(1, 5):
            y = rect.top() + i * rect.height() / 5
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

        # Draw axes box.
        painter.setPen(QPen(_AXIS_COLOR, 1))
        painter.drawRect(rect)

        # Axis labels.
        painter.setPen(_AXIS_COLOR)
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(
            QRectF(0, self.height() - _MARGIN_BOTTOM + 22, self.width(), 20),
            Qt.AlignmentFlag.AlignCenter,
            f"{self._spectrum.x_unit}",
        )

        # X-axis tick labels.
        for i in range(11):
            frac = i / 10
            x_data = self._x_min + frac * (self._x_max - self._x_min)
            if self._spectrum.spectrum_type.x_reversed:
                x_data = self._x_max - frac * (self._x_max - self._x_min)
            sx = rect.left() + frac * rect.width()
            painter.drawLine(QPointF(sx, rect.bottom()), QPointF(sx, rect.bottom() + 4))
            painter.drawText(
                QRectF(sx - 30, rect.bottom() + 5, 60, 14),
                Qt.AlignmentFlag.AlignCenter,
                f"{x_data:.1f}",
            )

        # Title.
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        painter.setFont(title_font)
        title_text = self._spectrum.title
        if self._spectrum.origin:
            title_text += f"   [{self._spectrum.origin}]"
        painter.drawText(QRectF(0, 5, self.width(), 20), Qt.AlignmentFlag.AlignCenter, title_text)

        # Draw the trace.
        painter.setPen(QPen(_TRACE_COLOR, 1.5))
        if self._spectrum.spectrum_type == SpectrumType.IR:
            # Continuous polyline.
            prev: QPointF | None = None
            for x, y in zip(self._spectrum.x_values, self._spectrum.y_values, strict=True):
                if not (self._x_min <= x <= self._x_max):
                    prev = None
                    continue
                p = self._data_to_screen(x, y, y_min, y_max, rect)
                if prev is not None:
                    painter.drawLine(prev, p)
                prev = p
        else:
            # Stick plot — vertical line from baseline to peak.
            baseline_y = rect.bottom()
            for x, y in zip(self._spectrum.x_values, self._spectrum.y_values, strict=True):
                if not (self._x_min <= x <= self._x_max):
                    continue
                p = self._data_to_screen(x, y, y_min, y_max, rect)
                painter.drawLine(QPointF(p.x(), baseline_y), QPointF(p.x(), p.y()))

        # Annotate up to 10 tallest peaks with labels.
        label_font = QFont()
        label_font.setPointSize(8)
        painter.setFont(label_font)
        painter.setPen(_PEAK_LABEL_COLOR)
        labeled_peaks = sorted(
            (p for p in self._spectrum.peaks if p.label),
            key=lambda p: -p.intensity,
        )[:10]
        for peak in labeled_peaks:
            if not (self._x_min <= peak.x <= self._x_max):
                continue
            # Special case IR: labels go at the trough.
            if self._spectrum.spectrum_type == SpectrumType.IR:
                p = self._data_to_screen(peak.x, peak.intensity, y_min, y_max, rect)
                painter.drawText(QPointF(p.x() + 2, p.y() + 10), peak.label)
            else:
                p = self._data_to_screen(peak.x, peak.intensity, y_min, y_max, rect)
                painter.drawText(QPointF(p.x() + 2, p.y() - 2), peak.label)

        painter.end()


__all__ = ["SpectrumViewer"]
