"""Dash patterns as a stroke property (manim-free).

A dashed stroke is the same single VMobject the solid case builds (``Line``,
the ``Arrow`` stem, ``Circle``, ``Arc``, ``Ellipse``, a sampled curve …) with a
:class:`DashPattern` attached. The pattern is fixed in scene units (MU) when the
mobject is built; whoever strokes the path (``svg_parser`` for SVG/PDF/EPS, the
scene camera for video) hands it to cairo, so the output is one ``<path>`` with
``stroke-dasharray`` instead of one path per dash.

Style contract (the web relies on these names):

- ``stroke_dash_ratio`` — share of the dash in one period; ``None``/``0`` or
  ``>= 1`` is solid.
- ``stroke_dash_period_px`` — dash + gap in style pixels (the unit of
  ``stroke_width_px``); becomes MU through ``/ ptUnit_style``, so it follows the
  style prominence and not the zoom of the geometry.
- ``rendering.dash_period_px`` — style-wide fallback period, default 10.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

__all__ = [
    'DEFAULT_DASH_PERIOD_PX',
    'DASH_ATTR',
    'DashPattern',
    'dash_ratio',
    'dash_period_px',
    'rendering_dash_period_px',
    'element_dash_px',
    'dash_pattern',
    'path_length',
    'set_dash',
    'get_dash',
    'apply_cairo_dash',
]

DEFAULT_DASH_PERIOD_PX = 10.0

# Attribute that carries the pattern on a mobject. manim's
# ``Mobject.__getattr__`` synthesises ``get_*``/``set_*`` names, so the pattern
# lives in a plain private attribute and is read with ``getattr(..., None)``.
DASH_ATTR = '_ag_dash'

# Smallest drawn dash when round/square caps eat the whole nominal dash.
_MIN_DRAWN = 1e-6

# Points sampled per cubic piece when measuring a path.
_LENGTH_SAMPLES = 16


@dataclass(frozen=True)
class DashPattern:
    """Final dash pattern of one stroke, in scene units (MU).

    ``offset`` is the position inside the pattern where the path starts
    (cairo ``set_dash`` offset / SVG ``stroke-dashoffset`` / TikZ
    ``dash phase``), normalised to ``[0, on + off)``.
    """
    on: float
    off: float
    offset: float = 0.0

    @property
    def period(self) -> float:
        return self.on + self.off


def _finite_number(value) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def dash_ratio(value) -> Optional[float]:
    """Normalise ``stroke_dash_ratio``: ``r`` in ``(0, 1)``, else ``None`` (solid)."""
    r = _finite_number(value)
    if r is None or r <= 0 or r >= 1:
        return None
    return r


def dash_period_px(value, fallback=None) -> float:
    """Dash period in style pixels.

    An invalid ``value`` (not a number, ``<= 0``) falls back to ``fallback``;
    an invalid ``fallback`` falls back to :data:`DEFAULT_DASH_PERIOD_PX`.
    """
    for candidate in (value, fallback):
        p = _finite_number(candidate)
        if p is not None and p > 0:
            return p
    return DEFAULT_DASH_PERIOD_PX


def rendering_dash_period_px(scene) -> float:
    """``rendering.dash_period_px`` of the scene's style, default 10.

    The user style's own ``rendering`` block wins over the merged
    builtin + user ``style_config.rendering``.
    """
    for rendering in (
        getattr(getattr(scene, 'style', None), 'rendering', None),
        getattr(getattr(scene, 'style_config', None), 'rendering', None),
    ):
        if isinstance(rendering, dict) and 'dash_period_px' in rendering:
            p = _finite_number(rendering.get('dash_period_px'))
            if p is not None and p > 0:
                return p
    return DEFAULT_DASH_PERIOD_PX


def element_dash_px(scene, elem, resolve=None) -> Optional[Tuple[float, float]]:
    """Nominal ``(dash_px, gap_px)`` of an element in style pixels, or ``None``.

    ``resolve(elem, key, default)`` defaults to the style resolver; exporters
    pass their own context's ``resolve`` (same chain).
    """
    if resolve is None:
        from .style.resolver import resolve as _resolve

        def resolve(e, key, default=None):
            return _resolve(scene, e, key, default=default)
    r = dash_ratio(resolve(elem, 'stroke_dash_ratio', None))
    if r is None:
        return None
    period = dash_period_px(
        resolve(elem, 'stroke_dash_period_px', None),
        rendering_dash_period_px(scene),
    )
    return r * period, (1.0 - r) * period


def dash_pattern(length_mu, dash_mu, gap_mu, *, closed=False, fit_ends=False,
                 cap_extent_mu=0.0, phase_mu=0.0) -> DashPattern:
    """Build the dash pattern of one path.

    Args:
        length_mu: path length (only used when fitting).
        dash_mu, gap_mu: nominal dash and gap.
        closed: closed path — a whole number of periods, no seam.
        fit_ends: open path of finite length — a dash on both ends
            (``n·dash + (n−1)·gap = length``).
        cap_extent_mu: how far round/square caps lengthen each dash (the line
            width); the drawn dash is shortened by it and centred on the
            nominal one, so the visible dash keeps the nominal length.
        phase_mu: pattern position at the path start, for unfitted paths
            (a ray clipped by the viewport keeps its dashes anchored at the
            vertex).
    """
    dash = float(dash_mu)
    gap = float(gap_mu)
    period = dash + gap
    length = float(length_mu or 0.0)
    scale = 1.0
    phase = float(phase_mu or 0.0)
    if period > 0 and length > 0:
        if closed:
            n = max(1, round(length / period))
            scale = length / (n * period)
            phase = 0.0
        elif fit_ends:
            n = max(1, round((length + gap) / period))
            scale = length / (n * dash + (n - 1) * gap)
            phase = 0.0
    on = dash * scale
    off = gap * scale

    cap = float(cap_extent_mu or 0.0)
    if cap > 0:
        on_draw = max(_MIN_DRAWN, on - cap)
        shrink = on - on_draw
        on, off = on_draw, off + shrink
        phase -= shrink / 2.0

    total = on + off
    offset = phase % total if total > 0 else 0.0
    if offset and math.isclose(offset, total, rel_tol=0.0, abs_tol=1e-12):
        offset = 0.0
    return DashPattern(on, off, offset)


def path_length(points) -> float:
    """Length of a manim cubic-Bézier point array (groups of 4 control points).

    Straight pieces are exact; curved pieces are measured by chords over
    :data:`_LENGTH_SAMPLES` samples each.
    """
    pts = np.asarray(points, dtype=float)
    if pts.ndim != 2 or len(pts) < 4:
        return 0.0
    n = (len(pts) // 4) * 4
    cubics = pts[:n].reshape(-1, 4, pts.shape[1])            # (N, 4, dim)
    t = np.linspace(0.0, 1.0, _LENGTH_SAMPLES + 1)
    mt = 1.0 - t
    bern = np.stack([mt ** 3, 3 * mt ** 2 * t, 3 * mt * t ** 2, t ** 3], axis=1)  # (S, 4)
    curves = np.einsum('sk,nkd->nsd', bern, cubics)          # (N, S, dim)
    return float(np.linalg.norm(np.diff(curves, axis=1), axis=2).sum())


def set_dash(mobject, pattern: Optional[DashPattern]):
    """Attach ``pattern`` to ``mobject`` (``None`` makes the stroke solid)."""
    if pattern is None:
        if DASH_ATTR in getattr(mobject, '__dict__', {}):
            delattr(mobject, DASH_ATTR)
    else:
        setattr(mobject, DASH_ATTR, pattern)
    return mobject


def get_dash(mobject) -> Optional[DashPattern]:
    """The mobject's own :class:`DashPattern`, or ``None`` for a solid stroke."""
    return getattr(mobject, '__dict__', {}).get(DASH_ATTR)


def apply_cairo_dash(ctx, mobject) -> bool:
    """Set the cairo dash for stroking ``mobject``; reset it for a solid one.

    Returns ``True`` when a dash was set.
    """
    pattern = get_dash(mobject)
    if pattern is None:
        ctx.set_dash([])
        return False
    ctx.set_dash([pattern.on, pattern.off], pattern.offset)
    return True
