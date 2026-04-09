"""Geometry helpers for the canvas: snapping, vectors, bond geometry.

These helpers are intentionally framework-free (no Qt imports) so they can
be unit-tested without spinning up a ``QApplication``.

Conventions:

- All angles are in **radians** unless a parameter name ends in ``_deg``.
- The canvas uses Qt scene coordinates: ``+x`` is right, ``+y`` is **down**.
  When you think "up at 30°" in chemistry-publication terms you actually
  want a *negative* y delta. Helpers below stay agnostic so this only
  matters when you draw something for the first time.
- The default bond length is the length we want every freshly-drawn bond
  to have, regardless of how far the user dragged.
"""

from __future__ import annotations

import math

# Default scene-unit length for a single bond. Picked so that 14-point atom
# labels look balanced at zoom=1; tweak together with ATOM_FONT_SIZE if you
# change either.
DEFAULT_BOND_LENGTH: float = 50.0

# ChemDraw-style 30° snap grid: bonds align with horizontal and the standard
# hexagon vertices. Override at the call site for specialized tools.
DEFAULT_SNAP_DEG: float = 30.0


def snap_angle(angle_rad: float, increment_deg: float = DEFAULT_SNAP_DEG) -> float:
    """Snap ``angle_rad`` to the nearest multiple of ``increment_deg``."""
    increment = math.radians(increment_deg)
    return round(angle_rad / increment) * increment


def snap_endpoint(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    *,
    length: float = DEFAULT_BOND_LENGTH,
    increment_deg: float = DEFAULT_SNAP_DEG,
) -> tuple[float, float]:
    """Return a snapped endpoint at fixed ``length`` from ``(start_x, start_y)``.

    The angle from start to end is snapped to a multiple of ``increment_deg``,
    and the result is placed at exactly ``length`` from the start. If the user
    dragged onto the start point we fall back to a horizontal stub so we never
    return ``(start, start)``.
    """
    dx = end_x - start_x
    dy = end_y - start_y
    if dx == 0.0 and dy == 0.0:
        return start_x + length, start_y
    angle = math.atan2(dy, dx)
    snapped = snap_angle(angle, increment_deg)
    return (
        start_x + length * math.cos(snapped),
        start_y + length * math.sin(snapped),
    )


def free_endpoint_at_default_length(
    start_x: float,
    start_y: float,
    angle_rad: float,
    *,
    length: float = DEFAULT_BOND_LENGTH,
) -> tuple[float, float]:
    """Endpoint exactly ``length`` from ``start`` in the given direction."""
    return start_x + length * math.cos(angle_rad), start_y + length * math.sin(angle_rad)


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Euclidean distance between two points."""
    return math.hypot(x2 - x1, y2 - y1)


def angle_between(x1: float, y1: float, x2: float, y2: float) -> float:
    """Angle in radians from point 1 to point 2."""
    return math.atan2(y2 - y1, x2 - x1)


def neighbor_angles(
    center_x: float, center_y: float, neighbors: list[tuple[float, float]]
) -> list[float]:
    """Return angles (rad) from ``center`` to each neighbor in input order."""
    return [angle_between(center_x, center_y, nx, ny) for nx, ny in neighbors]


def best_new_bond_angle(existing_neighbor_angles: list[float]) -> float:
    """Pick a "good" angle for a new bond off an atom that already has neighbors.

    Heuristic: rotate to the direction with the largest gap to its nearest
    existing neighbor. With zero neighbors we return ``-π/6`` (30° above
    horizontal) to match the standard chemistry-textbook orientation. With
    one neighbor we offset by 120° to keep sp3 / sp2 angles natural.
    """
    if not existing_neighbor_angles:
        return -math.pi / 6  # 30° "up-right" in scene coords (y-down)
    if len(existing_neighbor_angles) == 1:
        return existing_neighbor_angles[0] + math.radians(120.0)

    sorted_angles = sorted(a % (2 * math.pi) for a in existing_neighbor_angles)
    best_gap = -1.0
    best_mid = sorted_angles[0]
    n = len(sorted_angles)
    for i in range(n):
        a = sorted_angles[i]
        b = sorted_angles[(i + 1) % n]
        gap = (b - a) % (2 * math.pi)
        if gap == 0:
            gap = 2 * math.pi
        if gap > best_gap:
            best_gap = gap
            best_mid = (a + gap / 2) % (2 * math.pi)
    return best_mid


def zigzag_extension_angle(
    tip_x: float,
    tip_y: float,
    neighbor_x: float,
    neighbor_y: float,
    grandparent_x: float | None = None,
    grandparent_y: float | None = None,
) -> float:
    """Compute the direction for a new bond that extends a zigzag chain.

    The "tip" is the atom the user just clicked on; the "neighbor" is the
    tip's only existing neighbor; the "grandparent" is the neighbor's
    other neighbor (the atom one step further back along the chain).

    Chemistry drawings use a 120° interior angle with the turn direction
    *alternating*, so a proper zigzag chain has every other bond running
    parallel to each other. If we just put each new bond at
    ``neighbor_angle + 120°`` (as the generic heuristic does) the chain
    curls into a regular hexagon and closes on itself. Instead, the next
    bond ``tip → new`` should run **parallel** to ``grandparent → neighbor``
    — same direction, same magnitude — which is what gives you the
    textbook ↗↘↗↘ shape.

    If no grandparent exists yet (the tip's neighbor is itself a chain
    end), we fall back to the generic 120° offset, which just picks one
    of the two valid zigzag orientations.
    """
    if grandparent_x is None or grandparent_y is None:
        # No grandparent to mirror: use the generic 120° offset from the
        # neighbor direction. Either orientation starts a valid zigzag.
        neighbor_dir = math.atan2(neighbor_y - tip_y, neighbor_x - tip_x)
        return neighbor_dir + math.radians(120.0)
    # The new bond points in the same direction as grandparent → neighbor,
    # so the four atoms lie on a zigzag with parallel alternate bonds.
    return math.atan2(neighbor_y - grandparent_y, neighbor_x - grandparent_x)


__all__ = [
    "DEFAULT_BOND_LENGTH",
    "DEFAULT_SNAP_DEG",
    "snap_angle",
    "snap_endpoint",
    "free_endpoint_at_default_length",
    "distance",
    "angle_between",
    "neighbor_angles",
    "best_new_bond_angle",
    "zigzag_extension_angle",
]
