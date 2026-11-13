"""Kinds of marks: the shapes every output draws (manim-free).

One geometry for the renderer, the paint report, TikZ, JSXGraph and the
label placement. Sizes are style pixels; a world (scene) length is
``px / unit`` with ``unit`` the ``ptUnit_style`` of the drawing.

The style keys (none of them in ``style/builtin.json``: their defaults are
the constants below, and without them nothing is drawn differently):

- an angle — ``arc_style`` (``solid`` | ``dashed`` | ``wave``),
  ``arc_tick_count`` (0..3 ticks across the arcs, sized by
  ``tick_length_px`` / ``tick_shift_px``, by default those of a segment of
  the style), ``arrow_head`` (``none`` | ``end`` | ``start`` | ``both`` —
  ``end`` at the second side) sized by ``arrow_length_px`` /
  ``arrow_width_px`` (6 / 4). Any of them draws the arcs of a right angle
  in the automatic mode (``right_angle_marker`` ``null``): the square has no
  arcs to decorate;
- a segment — ``arrow_head`` (sized as the head of a vector of the style);
- a segment, a line, a ray, a vector — ``parallel_count`` (0..3 chevrons),
  ``parallel_size_px``, ``parallel_shift_px``, ``parallel_direction``;
- a point — ``point_fill`` (``solid`` | ``hollow``).

**Arcs.** The radii ``r_i = r_out − i·s`` (outer first), ``s`` the spacing
of the arcs, ``max(s, 2A + g)`` for two waves and more (``g`` = 2 px of
gap between them, :func:`arc_step_px`). The inner radius is the base radius,
grown (:func:`arc_base_px`) for several waves to ``3·λ_min / Δ`` (three
periods of at least ``λ_min`` = 4 px on the inner arc) and for a dashed
marker fitted to three dashes to hold them on every arc. An arc ``i`` drawn
over ``[a_i, a_i + Δ_i]`` (the outer arc stops at the base of an arrow
head):

- wave — ``N_i = max(N_min, round(r_out·Δ_i / λ))`` periods (``N_min`` 3
  for two waves and more, else 1), ``16·N_i + 1`` samples ``φ_k = a_i +
  Δ_i·k / (16·N_i)``, ``ρ_k = r_i + A·sin(2π·(k mod 16) / 16)``: both ends
  on the arc, the waves of arcs of the same span are radial shifts of each
  other. ``A`` = 1 px, ``λ`` = 6 px;
- dashed — ``on = off = p/2`` fitted to ``L_i = r_i·Δ_i`` with a dash at
  both ends (``dash.dash_pattern(…, fit_ends=True)``), ``p`` = 4 px; a
  marker with ticks, a head or several arcs fitted to fewer than three
  dashes on an arc takes ``p = max(3, min(4, L_i / 2.5))`` there
  (:func:`dash_period_px`); an explicit ``stroke_dash_pattern_px`` of the
  angle is drawn as it is;
- ticks across the arcs — radial lines from ``max(0, r_in − L/2)`` to
  ``r_out + L/2`` at ``θ_j = φ0 + Δ/2 + δ·((1 − k)/2 + j)``, ``δ =
  min(h / r_out, Δ / (k + 1))``;
- an arrow head on the outer arc — tip ``T`` at the end of the arc, base at
  the angle ``α = ℓ'/r_out`` inside, ``ℓ' = min(ℓ, r_out·Δ_e/2)`` (``Δ_e`` —
  ``Δ``, ``Δ/2`` for two heads), width ``w' = w·ℓ'/ℓ``; the outer arc stops
  at the base.

What reaches past the outer arc (:func:`angle_overhang_px`): the wave
``A``, half a tick ``L/2``, half a head ``w'/2``; a label on the bisector
clears the wave and the ticks (:func:`angle_label_overhang_px`). With
``rendering.angle_marker_fit`` the fit moves the grown arcs in: it wins
over the floors above.

**Hollow points.** The hole is the shape at half the size; a hollow point
is drawn at least so large that its hole holds a disc of
``HOLLOW_MIN_HOLE_PX`` output pixels (:func:`hollow_size_px`).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional

from .style.enums import ARC_STYLES, ARROW_HEADS, PARALLEL_DIRECTIONS, POINT_FILLS

__all__ = [
    'WAVE_AMPLITUDE_PX', 'WAVE_PERIOD_PX', 'WAVE_SAMPLES', 'ARC_DASH_PX', 'ANGLE_ARROW_PX', 'TICK_PX',
    'VECTOR_ARROW_PX', 'PARALLEL_SIZE_PX', 'PARALLEL_SHIFT_PX', 'MAX_COUNT', 'HOLLOW_INSCRIBED',
    'WAVE_GAP_PX', 'WAVE_MIN_PERIOD_PX', 'WAVE_MIN_PERIODS', 'ARC_DASH_MIN_PERIOD_PX', 'ARC_DASH_MIN_DASHES',
    'HOLLOW_MIN_HOLE_PX',
    'ArcDecor', 'ArcPath', 'AngleMarks', 'ParallelDecor', 'PointHole',
    'arc_decor', 'scene_arc_decor', 'arc_step_px', 'arc_base_px', 'wave_periods', 'dash_period_px',
    'arrow_fit', 'angle_overhang_px',
    'angle_label_overhang_px', 'angle_marks', 'segment_arrow', 'segment_arrow_px', 'parallel_decor',
    'scene_parallel_decor', 'chevron_center', 'chevrons', 'point_fill', 'point_hole', 'hole_outline',
    'hollow_size_px', 'export_scale', 'scene_point_size_px',
]

WAVE_AMPLITUDE_PX = 1.0
WAVE_PERIOD_PX = 6.0
WAVE_SAMPLES = 16                   # samples per period of a wave
ARC_DASH_PX = (2.0, 2.0)            # the nominal dash of a dashed arc
ANGLE_ARROW_PX = (6.0, 4.0)         # the head on an arc: length, width
TICK_PX = (9.0, 2.0)                # the ticks of the built-in segment: length, shift
VECTOR_ARROW_PX = (11.0, 7.5)       # the head of the built-in vector: length, width
PARALLEL_SIZE_PX = 8.0
PARALLEL_SHIFT_PX = 3.5
MAX_COUNT = 3
# The floors of legibility (the board of 13.11):
WAVE_GAP_PX = 2.0                   # the least gap between two wavy arcs (their crests)
WAVE_MIN_PERIOD_PX = 4.0            # the least wavelength on the inner of several waves
WAVE_MIN_PERIODS = 3                # the least periods of several waves
ARC_DASH_MIN_PERIOD_PX = 3.0        # the least period of a dashed arc fitted to three dashes
ARC_DASH_MIN_DASHES = 3
HOLLOW_MIN_HOLE_PX = 3.0            # the disc a hole holds, output px

# The inscribed radius of a point shape as a share of its circumradius.
HOLLOW_INSCRIBED = {'circle': 1.0, 'square': 1 / math.sqrt(2), 'diamond': 1 / math.sqrt(2),
                    'triangle_up': 0.5, 'triangle_down': 0.5, 'triangle_left': 0.5, 'triangle_right': 0.5}


def _num(value, default):
    if isinstance(value, bool) or value is None:
        return float(default)
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    return out if math.isfinite(out) else float(default)


def _positive(value, default):
    out = _num(value, default)
    return out if out > 0 else float(default)


def _count(value):
    if isinstance(value, bool):
        return 0
    try:
        out = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(MAX_COUNT, out))


def _enum(value, allowed, default):
    return value if isinstance(value, str) and value in allowed else default


def _scene_value(scene, elem):
    from .style.resolver import resolve

    def value(key, default=None):
        return resolve(scene, elem, key, default=default)
    return value


def _style_default(scene, type_name, key, fallback):
    cfg = getattr(scene, 'style_config', None)
    defaults = getattr(cfg, 'defaults', None)
    if defaults is None:
        return fallback
    try:
        out = defaults.get(type_name, key, fallback)
    except Exception:       # noqa: BLE001 — a foreign defaults object
        return fallback
    return fallback if out is None else out


# ── the arcs of an angle ─────────────────────────────────────────────────

@dataclass(frozen=True)
class ArcDecor:
    """The decoration of the arcs of an angle (style pixels)."""
    style: str = 'solid'
    ticks: int = 0
    tick_length_px: float = TICK_PX[0]
    tick_shift_px: float = TICK_PX[1]
    arrow: str = 'none'
    arrow_length_px: float = ANGLE_ARROW_PX[0]
    arrow_width_px: float = ANGLE_ARROW_PX[1]
    dash_px: Optional[tuple] = None        # explicit pattern of a dashed arc

    @property
    def plain(self) -> bool:
        """No decoration: the arcs as before (solid, no ticks, no head)."""
        return self.style == 'solid' and self.ticks == 0 and self.arrow == 'none'

    @property
    def forces_arcs(self) -> bool:
        """The automatic mode draws arcs (the square has none to decorate)."""
        return not self.plain


def arc_decor(value: Callable, *, tick_length_px=TICK_PX[0], tick_shift_px=TICK_PX[1]) -> ArcDecor:
    """:class:`ArcDecor` of an angle; ``value(key, default)`` reads its
    style. ``tick_length_px`` / ``tick_shift_px`` — the defaults of the
    ticks (a segment of the style)."""
    from .dash import explicit_dash_px
    style = _enum(value('arc_style', 'solid'), ARC_STYLES, 'solid')
    return ArcDecor(
        style=style,
        ticks=_count(value('arc_tick_count', 0)),
        tick_length_px=_positive(value('tick_length_px', tick_length_px), tick_length_px),
        tick_shift_px=max(0.0, _num(value('tick_shift_px', tick_shift_px), tick_shift_px)),
        arrow=_enum(value('arrow_head', 'none'), ARROW_HEADS, 'none'),
        arrow_length_px=max(0.0, _num(value('arrow_length_px', ANGLE_ARROW_PX[0]), ANGLE_ARROW_PX[0])),
        arrow_width_px=max(0.0, _num(value('arrow_width_px', ANGLE_ARROW_PX[1]), ANGLE_ARROW_PX[1])),
        dash_px=explicit_dash_px(value('stroke_dash_pattern_px', None)) if style == 'dashed' else None,
    )


def scene_arc_decor(scene, elem) -> ArcDecor:
    """:class:`ArcDecor` of the angle ``elem`` through the style resolver;
    the ticks default to those of a segment of the style."""
    return arc_decor(_scene_value(scene, elem),
                     tick_length_px=_positive(_style_default(scene, 'segment', 'tick_length_px', TICK_PX[0]),
                                              TICK_PX[0]),
                     tick_shift_px=_num(_style_default(scene, 'segment', 'tick_shift_px', TICK_PX[1]), TICK_PX[1]))


def arc_step_px(decor: ArcDecor, shift_px, count) -> float:
    """The spacing of ``count`` arcs: ``shift_px``; two waves and more at
    least ``2A + g`` apart (a gap of ``WAVE_GAP_PX`` between their crests)."""
    if decor.style == 'wave' and int(count or 0) >= 2:
        return max(float(shift_px), 2 * WAVE_AMPLITUDE_PX + WAVE_GAP_PX)
    return shift_px


def _three_dashes(decor: ArcDecor, count) -> bool:
    """A dashed marker fitted to three dashes an arc: with ticks, a head
    or several arcs, its dash not explicit (a plain single dashed arc keeps
    what it has)."""
    return decor.style == 'dashed' and decor.dash_px is None and \
        (decor.ticks > 0 or decor.arrow != 'none' or int(count or 0) >= 2)


def _fitted_dashes(length_px, period_px) -> int:
    """The dashes of ``dash.dash_pattern(…, fit_ends=True)`` with ``on = off = p/2``."""
    return max(1, int(round((length_px + period_px / 2) / period_px))) if length_px > 0 else 1


def wave_periods(r_out_px, span, count) -> int:
    """``N = max(N_min, round(r_out·span / λ))`` periods of a wavy arc of
    ``span`` rad, ``N_min`` 3 for ``count`` ≥ 2 arcs, else 1."""
    least = WAVE_MIN_PERIODS if int(count or 0) >= 2 else 1
    return max(least, int(round(float(r_out_px) * float(span) / WAVE_PERIOD_PX)))


def dash_period_px(decor: ArcDecor, count, length_px) -> float:
    """The period ``p`` (``on = off = p/2``) of the fitted dashes of an arc
    ``length_px`` long: 4 px; for a marker fitted to three dashes
    (:func:`_three_dashes`) with fewer at 4 px, ``max(3, min(4, L / 2.5))`` —
    three dashes exactly where ``L ≥ 7.5`` px."""
    period = ARC_DASH_PX[0] + ARC_DASH_PX[1]
    length_px = float(length_px)
    if not _three_dashes(decor, count) or length_px <= 0 or \
            _fitted_dashes(length_px, period) >= ARC_DASH_MIN_DASHES:
        return period
    return max(ARC_DASH_MIN_PERIOD_PX, min(period, length_px / (ARC_DASH_MIN_DASHES - 0.5)))


def arc_base_px(decor: ArcDecor, base_px, step_px, count, span) -> float:
    """The inner radius (px) of ``count`` decorated arcs ``step_px`` apart
    over ``span`` rad: ``base_px``, grown so that the inner of two waves and
    more holds ``WAVE_MIN_PERIODS`` periods of ``WAVE_MIN_PERIOD_PX`` (``r ≥
    3·4 / Δ``) and every arc of a dashed marker fitted to three dashes holds
    three of ``ARC_DASH_MIN_PERIOD_PX`` (``L ≥ T = 2.5·3``: the inner arcs
    ``r ≥ T / Δ``; the outer one past its ``h`` heads, ``L = max(r·Δ − h·ℓ,
    r·Δ/2)``, ``r_out ≥ min((T + h·ℓ) / Δ, 2T / Δ)``)."""
    base = float(base_px)
    n = int(count or 0)
    span = float(span)
    if n <= 0 or not span > 1e-12 or decor.plain:
        return base
    if decor.style == 'wave':
        return max(base, WAVE_MIN_PERIODS * WAVE_MIN_PERIOD_PX / span) if n >= 2 else base
    if not _three_dashes(decor, n):
        return base
    least = (ARC_DASH_MIN_DASHES - 0.5) * ARC_DASH_MIN_PERIOD_PX
    need = least / span
    if decor.arrow != 'none' and decor.arrow_length_px > 0:
        heads = 2 if decor.arrow == 'both' else 1
        outer = min((least + heads * decor.arrow_length_px) / span, 2 * least / span)
        need = max(need, outer - (n - 1) * float(step_px))
    return max(base, need)


def arrow_fit(length_px, width_px, radius_px, span, both=False) -> tuple:
    """``(ℓ', w')`` of a head on an arc of ``radius_px`` and ``span`` rad:
    at most half the arc (a quarter for two heads), the width scaled with it."""
    length_px, width_px = float(length_px), float(width_px)
    if length_px <= 0 or radius_px <= 0 or span <= 0:
        return 0.0, 0.0
    short = min(length_px, 0.5 * float(radius_px) * (span / 2 if both else span))
    return short, width_px * short / length_px


def angle_overhang_px(decor: ArcDecor, outer_px, span) -> float:
    """How far the decoration reaches past the outer arc (px): the wave
    ``A``, half a tick, half a head (``w'/2``); 0 without decoration."""
    out = 0.0
    if decor.style == 'wave':
        out = WAVE_AMPLITUDE_PX
    if decor.ticks > 0:
        out = max(out, decor.tick_length_px / 2)
    if decor.arrow != 'none':
        out = max(out, arrow_fit(decor.arrow_length_px, decor.arrow_width_px, outer_px, span,
                                 decor.arrow == 'both')[1] / 2)
    return out


def angle_label_overhang_px(decor: ArcDecor) -> float:
    """The overhang on the bisector a label clears: the wave and the ticks
    (the heads stand at the ends of the arc)."""
    out = WAVE_AMPLITUDE_PX if decor.style == 'wave' else 0.0
    if decor.ticks > 0:
        out = max(out, decor.tick_length_px / 2)
    return out


@dataclass
class ArcPath:
    """One drawn arc (world units): ``radius``, the drawn ``start`` and
    ``span`` (rad, counterclockwise), the samples of a wave (``points``,
    ``periods``) or the dash of a dashed arc (``dash``, ``dashes`` — the
    number of dashes of a fitted one, ``None`` for an explicit pattern)."""
    radius: float
    start: float
    span: float
    points: Optional[list] = None
    periods: int = 0
    dash: object = None
    dashes: Optional[int] = None
    period_px: Optional[float] = None       # the period fitted (``dash_period_px``)


@dataclass
class AngleMarks:
    """The decorated arcs of an angle (world units): ``arcs`` (outer
    first), the ``ticks`` across them ``[x1, y1, x2, y2]``, the ``tips`` of
    the heads ``[Tx, Ty, B1x, B1y, B2x, B2y]`` (tip, base corners) and
    ``heads`` — the ends that carry one (``start``/``end``)."""
    arcs: list = field(default_factory=list)
    ticks: list = field(default_factory=list)
    tips: list = field(default_factory=list)
    heads: list = field(default_factory=list)


def _wave(cx, cy, radius, start, span, periods, amplitude):
    n = WAVE_SAMPLES * periods
    pts = []
    for k in range(n + 1):
        phi = start + span * k / n
        rho = radius + amplitude * math.sin(2 * math.pi * (k % WAVE_SAMPLES) / WAVE_SAMPLES)
        pts.append([cx + rho * math.cos(phi), cy + rho * math.sin(phi)])
    return pts


def angle_marks(vertex, radii, start, span, flipped, decor: ArcDecor, unit) -> AngleMarks:
    """The arcs of ``radii`` (world, outer first) around ``vertex`` over
    ``[start, start + span]`` with ``decor``. ``flipped`` — the arc runs from
    the second side (``start`` is at side 2, as ``_render_angle`` draws a
    flipped angle). ``unit`` — style px per world unit."""
    from .dash import dash_pattern, explicit_pattern
    out = AngleMarks()
    radii = [float(r) for r in radii if r > 0]
    span = float(span)
    if not radii or not span > 1e-12:
        return out
    unit = float(unit)
    cx, cy = float(vertex[0]), float(vertex[1])
    r_out = radii[0]
    r_out_px = r_out * unit
    trim = [0.0, 0.0]                   # rad cut at the start / the end of the outer arc
    if decor.arrow != 'none':
        both = decor.arrow == 'both'
        length, width = arrow_fit(decor.arrow_length_px, decor.arrow_width_px, r_out_px, span, both)
        if length > 0:
            # 'end' — at the second side: the end of the arc, its start when flipped
            sides = ('start', 'end') if both else (decor.arrow,)
            for side in sides:
                at_end = (side == 'end') != bool(flipped)
                phi = start + span if at_end else start
                alpha = length / r_out_px
                base = phi - alpha if at_end else phi + alpha
                tx, ty = cx + r_out * math.cos(phi), cy + r_out * math.sin(phi)
                bx, by = cx + r_out * math.cos(base), cy + r_out * math.sin(base)
                dx, dy = tx - bx, ty - by
                norm = math.hypot(dx, dy) or 1.0
                nx, ny = -dy / norm * width / 2 / unit, dx / norm * width / 2 / unit
                out.tips.append([tx, ty, bx + nx, by + ny, bx - nx, by - ny])
                out.heads.append(side)
                trim[1 if at_end else 0] = alpha
    for i, radius in enumerate(radii):
        a = start + (trim[0] if i == 0 else 0.0)
        s = span - (trim[0] + trim[1] if i == 0 else 0.0)
        arc = ArcPath(radius, a, s)
        if decor.style == 'wave':
            arc.periods = wave_periods(r_out_px, s, len(radii))
            arc.points = _wave(cx, cy, radius, a, s, arc.periods, WAVE_AMPLITUDE_PX / unit)
        elif decor.style == 'dashed':
            if decor.dash_px is not None:
                arc.dash = explicit_pattern(decor.dash_px, unit)
            else:
                length = radius * s
                arc.period_px = dash_period_px(decor, len(radii), length * unit)
                k = arc.period_px / (ARC_DASH_PX[0] + ARC_DASH_PX[1])
                on, off = ARC_DASH_PX[0] * k / unit, ARC_DASH_PX[1] * k / unit
                arc.dash = dash_pattern(length, on, off, fit_ends=True)
                arc.dashes = max(1, round((length + off) / (on + off))) if length > 0 else 1
        out.arcs.append(arc)
    if decor.ticks > 0:
        k = decor.ticks
        half = decor.tick_length_px / 2
        r_in_px = radii[-1] * unit
        step = min(decor.tick_shift_px / r_out_px, span / (k + 1))
        lo, hi = max(0.0, r_in_px - half) / unit, (r_out_px + half) / unit
        for j in range(k):
            theta = start + span / 2 + step * ((1 - k) / 2 + j)
            c, s_ = math.cos(theta), math.sin(theta)
            out.ticks.append([cx + lo * c, cy + lo * s_, cx + hi * c, cy + hi * s_])
    return out


# ── the head of a segment ────────────────────────────────────────────────

def segment_arrow_px(value: Callable, *, length_px=VECTOR_ARROW_PX[0], width_px=VECTOR_ARROW_PX[1]) -> tuple:
    """``(head, length_px, width_px)`` of a segment: ``arrow_head`` and the
    sizes, by default those of a vector of the style."""
    return (_enum(value('arrow_head', 'none'), ARROW_HEADS, 'none'),
            max(0.0, _num(value('arrow_length_px', length_px), length_px)),
            max(0.0, _num(value('arrow_width_px', width_px), width_px)))


def scene_segment_arrow(scene, elem) -> tuple:
    """:func:`segment_arrow_px` through the style resolver, the sizes of a
    vector of the style by default."""
    return segment_arrow_px(
        _scene_value(scene, elem),
        length_px=_num(_style_default(scene, 'vector', 'arrow_length_px', VECTOR_ARROW_PX[0]), VECTOR_ARROW_PX[0]),
        width_px=_num(_style_default(scene, 'vector', 'arrow_width_px', VECTOR_ARROW_PX[1]), VECTOR_ARROW_PX[1]))


def segment_arrow(p1, p2, head, length_px, width_px, unit) -> Optional[tuple]:
    """``(stem_a, stem_b, tips)`` of a segment ``p1 p2`` with heads (world):
    the stem between the bases, each tip ``[Tx, Ty, B1x, B1y, B2x, B2y]``;
    ``None`` without a head or for a zero segment. A head is at most the
    segment long, half of it for two."""
    if head not in ('end', 'start', 'both'):
        return None
    ax, ay, bx, by = float(p1[0]), float(p1[1]), float(p2[0]), float(p2[1])
    d = math.hypot(bx - ax, by - ay)
    if d < 1e-12:
        return None
    vx, vy = (bx - ax) / d, (by - ay) / d
    length = min(float(length_px) / float(unit), d / 2 if head == 'both' else d)
    half = float(width_px) / 2 / float(unit)
    nx, ny = -vy * half, vx * half
    a, b, tips = [ax, ay], [bx, by], []
    if head in ('start', 'both'):
        cx, cy = ax + vx * length, ay + vy * length
        tips.append([ax, ay, cx + nx, cy + ny, cx - nx, cy - ny])
        a = [cx, cy]
    if head in ('end', 'both'):
        cx, cy = bx - vx * length, by - vy * length
        tips.append([bx, by, cx + nx, cy + ny, cx - nx, cy - ny])
        b = [cx, cy]
    return a, b, tips


# ── chevrons of parallel lines ───────────────────────────────────────────

@dataclass(frozen=True)
class ParallelDecor:
    count: int = 0
    size_px: float = PARALLEL_SIZE_PX
    shift_px: float = PARALLEL_SHIFT_PX
    direction: str = 'forward'


def parallel_decor(value: Callable) -> ParallelDecor:
    """:class:`ParallelDecor` of a line; ``value(key, default)`` reads its style."""
    return ParallelDecor(
        count=_count(value('parallel_count', 0)),
        size_px=_positive(value('parallel_size_px', PARALLEL_SIZE_PX), PARALLEL_SIZE_PX),
        shift_px=max(0.0, _num(value('parallel_shift_px', PARALLEL_SHIFT_PX), PARALLEL_SHIFT_PX)),
        direction=_enum(value('parallel_direction', 'forward'), PARALLEL_DIRECTIONS, 'forward'),
    )


def scene_parallel_decor(scene, elem) -> ParallelDecor:
    return parallel_decor(_scene_value(scene, elem))


def chevron_center(mid, direction, decor: ParallelDecor, unit, *, tick_count=0, tick_shift_px=0.0,
                   tick_width_px=0.0) -> list:
    """The centre of the chevrons: the middle of the drawn line, moved past
    the ticks ``c = m + v·(t + s/2 + (p·(k − 1) + d)/2)`` with ``t =
    tick_shift·(n − 1)/2 + tick_width/2`` when the line has ``tick_count``
    ticks (``direction`` — unit, the way the chevrons point)."""
    mx, my = float(mid[0]), float(mid[1])
    if int(tick_count or 0) <= 0:
        return [mx, my]
    t = float(tick_shift_px) * (int(tick_count) - 1) / 2 + float(tick_width_px) / 2
    s, p, k = decor.size_px, decor.shift_px, decor.count
    along = (t + s / 2 + (p * (k - 1) + s / 2) / 2) / float(unit)
    return [mx + direction[0] * along, my + direction[1] * along]


def chevrons(center, direction, decor: ParallelDecor, unit) -> list:
    """The chevrons ``[x0, y0, Tx, Ty, x1, y1]`` (world) of ``decor`` around
    ``center`` pointing along the unit ``direction`` (already turned by
    ``parallel_direction``): tips ``T_j = c + v·(d/2 + p·((1 − k)/2 + j))``,
    depth ``d = s/2``, arms to ``T_j − v·d ± n·s/2``."""
    k = decor.count
    vx, vy = float(direction[0]), float(direction[1])
    norm = math.hypot(vx, vy)
    if k <= 0 or norm < 1e-12:
        return []
    vx, vy = vx / norm, vy / norm
    nx, ny = -vy, vx
    unit = float(unit)
    s, p = decor.size_px / unit, decor.shift_px / unit
    d = s / 2
    cx, cy = float(center[0]), float(center[1])
    out = []
    for j in range(k):
        along = d / 2 + p * ((1 - k) / 2 + j)
        tx, ty = cx + vx * along, cy + vy * along
        bx, by = tx - vx * d, ty - vy * d
        out.append([bx + nx * s / 2, by + ny * s / 2, tx, ty, bx - nx * s / 2, by - ny * s / 2])
    return out


def scene_chevrons(scene, elem, mid, direction, unit, *, ticks=True) -> list:
    """The chevrons (:func:`chevrons`) the renderer draws on the parallel
    line ``elem``: around ``mid`` — the middle of a segment or a vector,
    moved past its ``tick_count`` ticks (``ticks``), or of the drawn part
    of a line or a ray — pointing along ``direction`` turned by
    ``parallel_direction``; ``[]`` without them or for a line of no length."""
    decor = scene_parallel_decor(scene, elem)
    vx, vy = float(direction[0]), float(direction[1])
    norm = math.hypot(vx, vy)
    if decor.count <= 0 or norm < 1e-12:
        return []
    sign = -1.0 if decor.direction == 'backward' else 1.0
    v = (sign * vx / norm, sign * vy / norm)
    value = _scene_value(scene, elem)
    center = chevron_center((float(mid[0]), float(mid[1])), v, decor, unit,
                            tick_count=int(_num(value('tick_count', 0), 0)) if ticks else 0,
                            tick_shift_px=_num(value('tick_shift_px', 0.0), 0.0),
                            tick_width_px=_num(value('tick_width_px', 0.0), 0.0))
    return chevrons(center, v, decor, unit)


# ── a hollow point ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class PointHole:
    """The hole of a hollow point: the shape of the point, half its size —
    circumradius ``radius_px`` (``size_px / 4``) — and the width of the ring
    left, ``ring_px`` (half the inscribed radius of the shape)."""
    shape: str
    radius_px: float
    ring_px: float


def point_fill(value) -> str:
    return _enum(value, POINT_FILLS, 'solid')


def point_hole(shape, size_px, fill) -> Optional[PointHole]:
    """:class:`PointHole` of a ``hollow`` point, ``None`` for a solid one,
    a cross, a plus or a point of no size."""
    shape = shape or 'circle'
    if point_fill(fill) != 'hollow' or shape not in HOLLOW_INSCRIBED:
        return None
    radius = _num(size_px, 0.0) / 2
    if radius <= 0:
        return None
    return PointHole(shape, radius / 2, radius * HOLLOW_INSCRIBED[shape] / 2)


def hollow_size_px(shape, size_px, fill, scale=1.0) -> float:
    """The drawn size of a point (style px): a hollow one at least
    ``2·H / (k·S)`` — its hole (circumradius ``size/4``) then holds a disc
    of ``H = HOLLOW_MIN_HOLE_PX`` output px (``k`` — ``HOLLOW_INSCRIBED`` of
    the shape, ``S = scale`` output px per style px); a solid point, a
    cross, a plus and a point of no size as given (``size_px`` itself)."""
    shape = shape or 'circle'
    if point_fill(fill) != 'hollow' or shape not in HOLLOW_INSCRIBED:
        return size_px
    size = _num(size_px, 0.0)
    if size <= 0:
        return size_px
    return max(size, 2 * HOLLOW_MIN_HOLE_PX / (HOLLOW_INSCRIBED[shape] * _positive(scale, 1.0)))


def export_scale(scene) -> float:
    """``S`` — output px per style px of ``scene`` (``ptUnit / ptUnit_style``)."""
    export = getattr(getattr(scene, 'style', None), 'export', None) or {}
    unit = _positive(export.get('ptUnit', 1.0), 1.0)
    return unit / _positive(export.get('ptUnit_style', unit), unit)


def scene_point_size_px(scene, elem, size_px) -> float:
    """:func:`hollow_size_px` of the point ``elem`` of ``scene`` whose
    ``size_px`` is given (resolved by the caller)."""
    value = _scene_value(scene, elem)
    return hollow_size_px(value('point_shape', 'circle'), size_px, value('point_fill', 'solid'),
                          export_scale(scene))


def hole_outline(shape, center, radius) -> list:
    """The corners of a polygonal point shape of circumradius ``radius``
    around ``center`` (as the renderer draws it), ``[]`` for a circle."""
    cx, cy = float(center[0]), float(center[1])
    if shape == 'square':
        h = radius / math.sqrt(2)
        return [[cx - h, cy - h], [cx + h, cy - h], [cx + h, cy + h], [cx - h, cy + h]]
    if shape == 'diamond':
        return [[cx, cy + radius], [cx + radius, cy], [cx, cy - radius], [cx - radius, cy]]
    base = {'triangle_up': 90, 'triangle_down': -90, 'triangle_left': 180, 'triangle_right': 0}.get(shape)
    if base is None:
        return []
    return [[cx + radius * math.cos(math.radians(base + 120 * k)),
             cy + radius * math.sin(math.radians(base + 120 * k))] for k in range(3)]
