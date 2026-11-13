"""Regions (registry 1.9; docs/native/kernel.md §16).

A ``region`` value is ``{rings, shape, area}``. ``rings`` lists the closed
boundaries, each the pieces of one ring in the order of the walk:

- ``line`` — ``[[x0, y0], [x1, y1]]``;
- ``arc`` — ``[[x0, y0], [x1, y1], [cx, cy, r]]`` from the start to the
  end, counterclockwise (``ccw``) or clockwise (``cw``) as ``shape`` says;
  a start equal to its end is the whole circle;
- ``graph`` — ``[[x, y] × 257]``: 256 equal steps of ``x`` from the start
  of the piece to its end (the last ``x`` is the end itself).

``shape`` gives each piece ``[kind, source]`` (``kind`` one of ``line``,
``ccw``, ``cw``, ``graph``; ``source`` the slot of its carrier) and compares
exactly. The region lies left of every ring: outer rings run
counterclockwise (a positive signed area), holes clockwise, so the nonzero
and the even-odd rule fill the same set.

The signed area of a ring is ``Σ −∫ y dx`` over its pieces: exact for a
line (a trapezoid) and an arc (:func:`arc_area`), composite Simpson for a
graph (:func:`graph_area`, the nodes and the cell midpoints). The helpers
below are the contract of the web copy, step by step.
"""
from __future__ import annotations

import math

__all__ = ['ARC_FLATTEN_STEP', 'GRAPH_STEPS', 'arc_area', 'arc_sweep', 'flatten', 'graph_area', 'graph_xs', 'ring_length',
           'inside', 'label_anchor', 'line_area', 'perimeter', 'piece_length']

GRAPH_STEPS = 256                       # equal steps of a graph piece (257 points)
ARC_FLATTEN_STEP = math.radians(2.0)    # the largest step of a flattened arc
TWO_PI = 2.0 * math.pi


def graph_xs(x_start: float, x_end: float, steps: int = GRAPH_STEPS) -> list:
    """``x_k = x_start + k·(x_end − x_start)/steps``, ``k = 0 … steps``; the
    last one is ``x_end`` itself (not the rounded sum)."""
    xs = [x_start + (k * (x_end - x_start)) / steps for k in range(steps + 1)]
    xs[-1] = x_end
    return xs


def line_area(p0, p1) -> float:
    """``−∫ y dx`` along the line from ``p0`` to ``p1`` (a trapezoid)."""
    return -(p1[0] - p0[0]) * (p0[1] + p1[1]) / 2.0


def arc_sweep(piece, kind: str) -> tuple:
    """``(θ0, sweep)`` of an arc piece: ``θ0 = atan2`` of the start about the
    centre, ``sweep`` in ``(0, 2π]`` counterclockwise (``ccw``) or in
    ``[−2π, 0)`` clockwise (``cw``); a start equal to its end is the whole
    circle."""
    (x0, y0), (x1, y1), (cx, cy, _r) = piece
    t0 = math.atan2(y0 - cy, x0 - cx)
    t1 = math.atan2(y1 - cy, x1 - cx)
    if kind == 'ccw':
        sweep = (t1 - t0) % TWO_PI
        if sweep == 0.0:
            sweep = TWO_PI
    else:
        sweep = -((t0 - t1) % TWO_PI)
        if sweep == 0.0:
            sweep = -TWO_PI
    return t0, sweep


def arc_area(piece, kind: str) -> float:
    """``−∫ y dx`` along an arc piece: with ``x = cx + r cos θ``,
    ``y = cy + r sin θ`` from ``θ0`` to ``θ1 = θ0 + sweep`` it is
    ``cy·r·(cos θ0 − cos θ1) + r²·(sweep/2 − (sin 2θ1 − sin 2θ0)/4)``."""
    _p0, _p1, (_cx, cy, r) = piece
    t0, sweep = arc_sweep(piece, kind)
    t1 = t0 + sweep
    return cy * r * (math.cos(t0) - math.cos(t1)) + r * r * (sweep / 2.0 - (math.sin(2 * t1) - math.sin(2 * t0)) / 4.0)


def graph_area(points, mids) -> float:
    """``−∫ y dx`` along a graph piece: composite Simpson over its cells,
    ``−Σ (x_{k+1} − x_k)/6 · (y_k + 4·m_k + y_{k+1})``, ``m_k`` the value at
    the midpoint ``x_k + (x_{k+1} − x_k)/2`` of cell ``k``."""
    acc = 0.0
    for k in range(len(points) - 1):
        (xa, ya), (xb, yb) = points[k], points[k + 1]
        acc = acc - (xb - xa) * (ya + 4.0 * mids[k] + yb) / 6.0
    return acc


def piece_length(piece, kind: str) -> float:
    """The length of a piece: a line and an arc exactly, a graph by its points."""
    if kind == 'line':
        (x0, y0), (x1, y1) = piece
        return math.hypot(x1 - x0, y1 - y0)
    if kind in ('ccw', 'cw'):
        _t0, sweep = arc_sweep(piece, kind)
        return piece[2][2] * abs(sweep)
    acc = 0.0
    for (xa, ya), (xb, yb) in zip(piece, piece[1:]):
        acc = acc + math.hypot(xb - xa, yb - ya)
    return acc


def ring_length(value, index: int) -> float:
    """The length of ring ``index`` of a region value."""
    acc = 0.0
    for piece, (kind, _source) in zip(value['rings'][index], value['shape'][index]):
        acc = acc + piece_length(piece, kind)
    return acc


def perimeter(value) -> float:
    """The length of all rings of a region value."""
    acc = 0.0
    for ring, kinds in zip(value['rings'], value['shape']):
        for piece, (kind, _source) in zip(ring, kinds):
            acc = acc + piece_length(piece, kind)
    return acc


def flatten(value) -> list:
    """The rings as polygons ``[[[x, y], …], …]`` (each closed implicitly):
    a piece gives its start and its inner points, the next piece its end. A
    line gives its start; an arc ``n = ceil(|sweep| / 2°)`` points at equal
    steps of the angle from its start (the sagitta at most ``r·1.5·10⁻⁴``);
    a graph its points but the last."""
    out = []
    for ring, kinds in zip(value['rings'], value['shape']):
        pts = []
        for piece, (kind, _source) in zip(ring, kinds):
            if kind == 'line':
                pts.append([float(piece[0][0]), float(piece[0][1])])
            elif kind in ('ccw', 'cw'):
                cx, cy, r = piece[2]
                t0, sweep = arc_sweep(piece, kind)
                n = max(1, math.ceil(abs(sweep) / ARC_FLATTEN_STEP))
                pts.append([float(piece[0][0]), float(piece[0][1])])
                for i in range(1, n):
                    t = t0 + (i * sweep) / n
                    pts.append([cx + r * math.cos(t), cy + r * math.sin(t)])
            else:
                pts.extend([float(x), float(y)] for x, y in piece[:-1])
        out.append(pts)
    return out


def inside(rings, x: float, y: float) -> bool:
    """The even-odd test of ``(x, y)`` against flattened ``rings``: a ray to
    ``+x`` crosses an edge ``(a, b)`` when ``(a.y > y) != (b.y > y)`` and the
    crossing ``a.x + (y − a.y)(b.x − a.x)/(b.y − a.y)`` lies right of ``x``."""
    odd = False
    for pts in rings:
        n = len(pts)
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            if (ay > y) != (by > y):
                cross = ax + (y - ay) * (bx - ax) / (by - ay)
                if cross > x:
                    odd = not odd
    return odd


def _centroid(rings):
    a = cx = cy = 0.0
    for pts in rings:
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            w = x0 * y1 - x1 * y0
            a = a + w
            cx = cx + (x0 + x1) * w
            cy = cy + (y0 + y1) * w
    if a == 0.0:
        return None
    return cx / (3.0 * a), cy / (3.0 * a)


def label_anchor(value):
    """The spot of a region's label ``[x, y]``: the centroid of the
    flattened rings (shoelace sums over all rings, holes negative) when the
    even-odd test puts it inside; else the middle of the longest inside
    interval of the horizontal through it (the crossings of the flattened
    edges sorted by ``x``, taken in pairs). ``None`` for an empty value."""
    rings = flatten(value)
    c = _centroid(rings)
    if c is None:
        return None
    x, y = c
    if inside(rings, x, y):
        return [x, y]
    xs = []
    for pts in rings:
        n = len(pts)
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            if (ay > y) != (by > y):
                xs.append(ax + (y - ay) * (bx - ax) / (by - ay))
    xs.sort()
    best = None
    for i in range(0, len(xs) - 1, 2):
        width = xs[i + 1] - xs[i]
        if best is None or width > best[0]:
            best = (width, xs[i] + width / 2.0)
    return [x, y] if best is None else [best[1], y]
