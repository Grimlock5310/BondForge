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
    zigzag_extension_angle,
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


def test_zigzag_extension_no_grandparent_offsets_120deg() -> None:
    # Tip at (1, 0), neighbor at (0, 0) (directly to the left).
    # Neighbor direction from tip = 180°. +120° => 300° = -60°.
    angle = zigzag_extension_angle(1.0, 0.0, 0.0, 0.0)
    assert _approx(angle % (2 * math.pi), math.radians(300))


def test_zigzag_extension_parallel_to_grandparent_neighbor_bond() -> None:
    # Chain: G(0,0) -> N(0.866, -0.5) -> T(1.732, 0).
    # G->N direction: atan2(-0.5, 0.866) = -30°.
    # The new bond T -> P should point in the same direction (-30°),
    # so P lands on the other peak of the zigzag.
    import math as _m

    gx, gy = 0.0, 0.0
    nx, ny = _m.cos(-_m.pi / 6) * 50, _m.sin(-_m.pi / 6) * 50
    tx, ty = 2 * nx, 0.0
    angle = zigzag_extension_angle(tx, ty, nx, ny, gx, gy)
    assert _approx(angle, -_m.pi / 6)


def test_zigzag_extension_does_not_form_hexagon() -> None:
    """Walking a chain with the zigzag helper should never close on itself.

    Six successive extensions from an empty atom form a straight-ish
    zigzag; the end position must be far from the starting atom rather
    than returning to it (which is what the naive +120° heuristic does).
    """
    import math as _m

    positions = [(0.0, 0.0)]
    # First extension: no neighbor yet, so we use the default orientation.
    dx = _m.cos(-_m.pi / 6) * 50
    dy = _m.sin(-_m.pi / 6) * 50
    positions.append((positions[-1][0] + dx, positions[-1][1] + dy))
    # Second extension: neighbor only (no grandparent).
    tip = positions[-1]
    nbr = positions[-2]
    a = zigzag_extension_angle(tip[0], tip[1], nbr[0], nbr[1])
    positions.append((tip[0] + 50 * _m.cos(a), tip[1] + 50 * _m.sin(a)))
    # Subsequent extensions: full grandparent zigzag.
    for _ in range(4):
        tip = positions[-1]
        nbr = positions[-2]
        gp = positions[-3]
        a = zigzag_extension_angle(tip[0], tip[1], nbr[0], nbr[1], gp[0], gp[1])
        positions.append((tip[0] + 50 * _m.cos(a), tip[1] + 50 * _m.sin(a)))
    # After 6 bonds the tip must be nowhere near the origin — a hexagon
    # would have closed the loop, landing within a bond length of (0, 0).
    end_x, end_y = positions[-1]
    assert _m.hypot(end_x, end_y) > 100.0
