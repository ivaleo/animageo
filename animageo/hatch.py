"""Hatching of filled regions by geometry (kernel spec §9.1).

``fill_pattern`` (``hatch``, ``crosshatch``, ``dots``) is drawn as plain
segments and dots cut by the region, not as an SVG pattern: cairo and manim
do not carry patterns into PDF, EPS, PNG and video alike, and TikZ gets the
same segments. Pure functions over floats (no numpy, no manim), so the
renderer, the TikZ exporter and the tests share one answer.

A family of parallel lines has the direction ``u = (cos a, sin a)`` and the
normal ``n = (−sin a, cos a)``; its lines are ``n·x = phase + k·spacing``
for every integer ``k``, so the hatching stays put in the plane when the
region moves (as in GeoGebra) and two regions with the same settings line up.

Regions::

    {"polygon": [(x, y), …]}            even-odd rule, any simple or self-crossing ring
    {"circle": (cx, cy, r)}             the disc
    {"sector": (cx, cy, r, a0, a1)}     the disc part counterclockwise from a0 to a1 (radians)
"""
from __future__ import annotations

import math

__all__ = ['FILL_PATTERNS', 'HATCH_DEFAULTS', 'hatch_dots', 'hatch_segments', 'hatch_spec', 'pattern_segments']

FILL_PATTERNS = ('solid', 'hatch', 'crosshatch', 'dots', 'none')
MAX_LINES = 2000          # a guard against a tiny spacing on a huge region
HATCH_DEFAULTS = {
    'fill_pattern': 'solid',
    'hatch_angle_deg': 45.0,
    'hatch_spacing_px': 6.0,
    'hatch_width_px': 0.75,
    'hatch_color': 'stroke',
    'hatch_opacity': 1.0,
}


def hatch_spec(resolve, elem, pt_unit_style: float) -> dict:
    """The pattern style of ``elem`` (``resolve(elem, key, default)``) in
    scene units: ``angle`` (radians), ``spacing_mu``, ``width_px`` (a line
    width, converted like ``stroke_width_px``), ``dot_radius_mu`` (a dot is
    as wide as two line widths), ``color`` (``None`` — the stroke colour of
    the element) and ``opacity``. Pixel sizes become scene units through
    ``pt_unit_style``, like every decoration, so they follow the export
    layout."""
    def number(key):
        try:
            return float(resolve(elem, key, HATCH_DEFAULTS[key]))
        except (TypeError, ValueError):
            return float(HATCH_DEFAULTS[key])

    spacing_px = number('hatch_spacing_px')
    if not spacing_px > 0.0:
        spacing_px = HATCH_DEFAULTS['hatch_spacing_px']
    width_px = max(0.0, number('hatch_width_px'))
    color = resolve(elem, 'hatch_color', 'stroke')
    return {
        'angle': math.radians(number('hatch_angle_deg')),
        'spacing_px': spacing_px,
        'spacing_mu': spacing_px / pt_unit_style,
        'width_px': width_px,
        'dot_radius_mu': width_px / pt_unit_style,
        'color': None if color in (None, 'stroke') else color,
        'opacity': min(1.0, max(0.0, number('hatch_opacity'))),
    }


def _intervals_polygon(vertices, n, u, c):
    """Parameters ``t = u·x`` of the parts of the line ``n·x = c`` inside the
    polygon (even-odd): crossings of the edges, half-open at the ends so a
    vertex on the line counts once."""
    ts = []
    count = len(vertices)
    for i in range(count):
        px, py = vertices[i]
        qx, qy = vertices[(i + 1) % count]
        sp = n[0] * px + n[1] * py
        sq = n[0] * qx + n[1] * qy
        if (sp < c) == (sq < c):
            continue
        k = (c - sp) / (sq - sp)
        x = px + k * (qx - px)
        y = py + k * (qy - py)
        ts.append(u[0] * x + u[1] * y)
    ts.sort()
    return [(ts[i], ts[i + 1]) for i in range(0, len(ts) - 1, 2)]


def _disc_interval(cx, cy, r, n, u, c):
    d = c - (n[0] * cx + n[1] * cy)
    if abs(d) >= r:
        return None
    half = math.sqrt(r * r - d * d)
    t0 = u[0] * cx + u[1] * cy
    return t0 - half, t0 + half


def _half_plane(e, cx, cy, n, u, c, sign):
    """``t`` where ``sign · cross(e, x − center) ≥ 0`` on the line, as
    ``(lo, hi)`` (``±inf`` for no bound) or ``None`` (nowhere)."""
    # x(t) = c·n + t·u
    x0, y0 = c * n[0] - cx, c * n[1] - cy
    f0 = sign * (e[0] * y0 - e[1] * x0)
    f1 = sign * (e[0] * u[1] - e[1] * u[0])
    if f1 == 0.0:
        return (-math.inf, math.inf) if f0 >= 0.0 else None
    t = -f0 / f1
    return (t, math.inf) if f1 > 0.0 else (-math.inf, t)


def _clip(a, b):
    if a is None or b is None:
        return None
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    return (lo, hi) if lo < hi else None


def _intervals_sector(cx, cy, r, a0, a1, n, u, c):
    disc = _disc_interval(cx, cy, r, n, u, c)
    if disc is None:
        return []
    sweep = a1 - a0
    if sweep >= 2.0 * math.pi:
        return [disc]
    if sweep <= 0.0:
        return []
    e0 = (math.cos(a0), math.sin(a0))
    e1 = (math.cos(a1), math.sin(a1))
    if sweep <= math.pi:
        # convex wedge: left of e0 and right of e1
        part = _clip(_clip(disc, _half_plane(e0, cx, cy, n, u, c, 1.0)),
                     _half_plane(e1, cx, cy, n, u, c, -1.0))
        return [part] if part else []
    # reflex wedge: the disc minus the open convex wedge from a1 to a0 + 2π
    hole = _clip(_half_plane(e1, cx, cy, n, u, c, 1.0), _half_plane(e0, cx, cy, n, u, c, -1.0))
    if hole is None:
        return [disc]
    out = []
    if disc[0] < hole[0]:
        out.append((disc[0], min(disc[1], hole[0])))
    if hole[1] < disc[1]:
        out.append((max(disc[0], hole[1]), disc[1]))
    return [p for p in out if p[0] < p[1]]


def _normal_range(region, n):
    if 'polygon' in region:
        values = [n[0] * x + n[1] * y for x, y in region['polygon']]
        return min(values), max(values)
    key = 'circle' if 'circle' in region else 'sector'
    cx, cy, r = region[key][:3]
    mid = n[0] * cx + n[1] * cy
    return mid - r, mid + r


def _intervals(region, n, u, c):
    if 'polygon' in region:
        return _intervals_polygon(region['polygon'], n, u, c)
    if 'circle' in region:
        part = _disc_interval(*region['circle'], n, u, c)
        return [part] if part else []
    return _intervals_sector(*region['sector'], n, u, c)


def _family(region, angle, spacing, phase):
    if not spacing > 0.0 or not math.isfinite(spacing):
        raise ValueError(f'hatch spacing must be a positive number, not {spacing!r}')
    u = (math.cos(angle), math.sin(angle))
    n = (-u[1], u[0])
    lo, hi = _normal_range(region, n)
    k0 = math.ceil((lo - phase) / spacing)
    k1 = math.floor((hi - phase) / spacing)
    if k1 - k0 + 1 > MAX_LINES:
        raise ValueError(f'hatch spacing {spacing} gives more than {MAX_LINES} lines')
    for k in range(k0, k1 + 1):
        c = phase + k * spacing
        yield n, u, c, _intervals(region, n, u, c)


def hatch_segments(region, angle, spacing, phase=0.0):
    """``[(x0, y0, x1, y1)]``: the parts inside ``region`` of the lines at
    ``angle`` (radians), ``spacing`` apart, offset ``phase`` along the
    normal; in the order of the lines, then along each line."""
    out = []
    for n, u, c, parts in _family(region, angle, spacing, phase):
        for t0, t1 in parts:
            out.append((c * n[0] + t0 * u[0], c * n[1] + t0 * u[1],
                        c * n[0] + t1 * u[0], c * n[1] + t1 * u[1]))
    return out


def hatch_dots(region, angle, spacing, phase=0.0):
    """``[(x, y)]``: the nodes of the square grid of step ``spacing`` turned
    by ``angle`` (both coordinates ``≡ phase`` modulo ``spacing``) inside
    ``region``."""
    out = []
    for n, u, c, parts in _family(region, angle, spacing, phase):
        for t0, t1 in parts:
            j0 = math.ceil((t0 - phase) / spacing)
            j1 = math.floor((t1 - phase) / spacing)
            for j in range(j0, j1 + 1):
                t = phase + j * spacing
                out.append((c * n[0] + t * u[0], c * n[1] + t * u[1]))
    return out


def pattern_segments(region, pattern, angle, spacing, phase=0.0):
    """Segments of a line pattern: ``hatch`` one family, ``crosshatch`` it
    and the family turned by 90°; other patterns have none."""
    if pattern == 'hatch':
        return hatch_segments(region, angle, spacing, phase)
    if pattern == 'crosshatch':
        return (hatch_segments(region, angle, spacing, phase)
                + hatch_segments(region, angle + math.pi / 2, spacing, phase))
    return []
