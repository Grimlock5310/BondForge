"""Tests for the framework-free geometry helpers."""

from __future__ import annotations

import math

import pytest

from bondforge.canvas.geometry import (
    DEFAULT_BOND_LENGTH,
    best_new_bond_angle,
    distance,
    free_endpoint_at_default_length,
    snap_angle,
    snap_endpoint,
)


def _approx(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) < tol


@pytest.mark.parametrize(
    "angle_deg,expected_deg",
    [
        (0, 0),
        (14, 0),
        (16, 30),
        (44, 30),
        (46, 60),
        (90, 90),
        (179, 180),
        (-29, -30),
    ],
)
def test_snap_angle_30deg_grid(angle_deg: float, expected_deg: float) -> None:
    out = snap_angle(math.radians(angle_deg))
    assert _approx(out, math.radians(expected_deg))


def test_snap_endpoint_uses_default_length() -> None:
    sx, sy = snap_endpoint(0.0, 0.0, 200.0, 0.0)
    assert _approx(distance(0, 0, sx, sy), DEFAULT_BOND_LENGTH)


def test_snap_endpoint_picks_nearest_30deg() -> None:
    sx, sy = snap_endpoint(0.0, 0.0, 100.0, 60.0)
    angle = math.degrees(math.atan2(sy - 0.0, sx - 0.0))
    # 100,60 is roughly 31°; should snap to 30°.
    assert abs(angle - 30.0) < 0.001


def test_snap_endpoint_zero_drag_returns_horizontal_stub() -> None:
    sx, sy = snap_endpoint(10.0, 20.0, 10.0, 20.0)
    assert _approx(sx, 10.0 + DEFAULT_BOND_LENGTH)
    assert _approx(sy, 20.0)


def test_free_endpoint_uses_default_length() -> None:
    ex, ey = free_endpoint_at_default_length(0.0, 0.0, 0.0)
    assert _approx(ex, DEFAULT_BOND_LENGTH)
    assert _approx(ey, 0.0)


def test_best_new_bond_angle_zero_neighbors_textbook_orientation() -> None:
    angle = best_new_bond_angle([])
    # Default orientation should be -30° (up-right in scene-space y-down).
    assert _approx(angle, -math.pi / 6)


def test_best_new_bond_angle_one_neighbor_offsets_120deg() -> None:
    angle = best_new_bond_angle([0.0])
    assert _approx(angle, math.radians(120))


def test_best_new_bond_angle_two_neighbors_picks_largest_gap() -> None:
    # Neighbors at 0° and 60°. Largest gap is the 300° span on the other side;
    # midpoint of that span is (60 + 300/2) = 210°.
    a = best_new_bond_angle([0.0, math.radians(60)])
    assert _approx(a % (2 * math.pi), math.radians(210))
