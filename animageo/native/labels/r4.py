"""R4: the client label solver, ported line for line (pure Python, no manim).

Source: the client solver ``frontend/src/canvas/render/labels/layout.ts`` and
``labels/geometry.ts`` at ``5d88ff083`` (the solver of ``c91527cc1`` plus the
origin of the view frame). The reference of that behaviour: constants, order
of candidates and operations, comparisons and roundings are the TypeScript's,
so a client checks its solver against fixtures made here (``k`` exactly,
centres within 0.01 px). Only the solver is ported, not when it is called,
the drag following or the transition.

Units: CSS px of the sheet, y down; a box is ``(l, t, r, b)``; ``edge`` — the
corner of the box standing at ``(x, y)``, axis y up.

Memory: ``{id: {'k': int, 'ax': float, 'ay': float}}`` — the chosen place and
the anchor it was chosen at. :func:`layout` takes the previous memory (or
``None``, the same as empty) and returns the new one without modifying the
argument.

JavaScript kept on purpose: ``%`` truncated and ``Math.atan2/cos/sin/hypot``
as V8 (``_jsmath.py``). Input is checked the same way as the JSON shape and
as dataclasses: a number that is not finite, a missing field or a value of
a wrong type raises ``ValueError`` (TypeScript would carry a NaN).

Ties — the one change to ``5d88ff083``, agreed with the client, which
repeats it: structural ties (a point in the middle of a segment or on a
line, crossings, regular figures, mirrored places) are decided by a rule,
not by the last bit of ``atan2``/``hypot`` (another libm, FMA):

* Gaps (``awayOctant``). An angle is normalised as ``n = ((a % 2π) + 2π) %
  2π``; an ``n > 2π − 1e-9`` is taken as ``n − 2π``. The angles are sorted
  ascending; gap ``i`` runs from ``n[i]`` to ``n[i + 1]``, the last one to
  ``n[0] + 2π``. ``W`` is the largest ``b − a`` (no tolerance); the
  bisector is ``(a + b) / 2`` of the first gap in this order with ``b − a
  >= W − 1e-9``. So the first equal gap counter-clockwise from east: a
  point on a horizontal line goes above it, on a vertical one to the left,
  at a crossing of the two to the north-east.
* Octants (``awayOctant`` and the side of an ``along`` place). A direction
  ``a`` (rad, y up) becomes the octant ``((Math.floor(x + 0.5 + 1e-9) % 8)
  + 8) % 8`` with ``x = a / (π / 4)``, added left to right: the nearest
  octant, a direction within 1e-9 octant of a half going up (to the next
  counter-clockwise). So the bisector at a 45° corner (337.5°) is east, the
  normal of a line at 22.5° (112.5°) is north-west.
* Costs (``best``). Places are tried in the order ``(penalty, index)``,
  ``index`` being the place in the list below. The best cost starts at the
  limit: +∞, or with a remembered place its cost (75 % of it if clean). A
  place replaces it only when ``cost < best · (1 − 1e-12)``; the search
  stops at the first place with ``1 + penalty >= best · (1 − 1e-12)``. So
  of equal costs the earlier place wins, and the remembered place wins
  over an equal one.
* The list of places (``k``). A point or line label without ``along``:
  0–7 at ``reach``, direction ``k·45°`` counter-clockwise from east (y up),
  8–15 the same at ``reach + max(w, h)``. With ``along``: 0–3 on the side
  ``+n`` at ``t = .5, .35, .65, .2``, 4–7 on the side ``−n`` (``n = (y1 −
  y2, x2 − x1) / length`` in screen axes), at the gap ``ALONG_GAP``; 8–15
  the same at ``ALONG_GAP + max(w, h)``. A measure: 0 its own box, 1–8 its
  box moved by ``0.6·h`` in the direction ``(k − 1)·45°``.

Why these sizes. An angle below 2π has an ulp of 8.9e-16 and libraries
differ by an ulp or two; an input moved by its ulp (coordinates below 1e5
px: under 1.5e-11 px) turns a direction seen from 1.5 px or more by under
1e-11 rad. 1e-9 rad is a hundred times that and still 1e-6 px at 1000 px:
real gaps are never that close. A cost is 1 + penalty + overlaps, between
1 and a few hundred, a sum of a few hundred terms at most, each rounded
once: noise under 1e-13 of it; real differences are steps of the
penalties (0.02 and up) or overlap fractions of a box (1e-12 of a 100 px²
box is 1e-10 px²). 1e-9 octant is 7.9e-10 rad, the size of the gap tie.
Every other comparison is the reference's.
"""
from __future__ import annotations

import functools
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ._jsmath import atan2 as _atan2
from ._jsmath import cos as _cos
from ._jsmath import hypot as _hypot
from ._jsmath import sin as _sin

__all__ = [
    'ANCHOR_EPS',
    'ALONG_GAP',
    'HYSTERESIS',
    'POINT_OBSTACLE_R',
    'Angle',
    'Arc',
    'Circle',
    'DisplayList',
    'Label',
    'LabelPlace',
    'LayoutView',
    'Linear',
    'Paint',
    'Point',
    'Polygon',
    'Polyline',
    'Ticks',
    'arc_hits_box',
    'circle_hits_box',
    'geometry_obstacles',
    'geometry_pairs',
    'layout',
    'segment_hits_box',
]

# Constants, TypeScript (layout.ts, geometry.ts) → Python:
#   BASE = 1                       _BASE
#   HYSTERESIS = 0.75              HYSTERESIS        (a new place: 25 % cheaper)
#   ANCHOR_EPS = 0.5               ANCHOR_EPS        (the anchor did not move)
#   POINT_OBSTACLE_R = 5           POINT_OBSTACLE_R
#   ALONG_GAP = 4                  ALONG_GAP
#   LABEL_STYLE_DX, _DY = 1, −1    _LABEL_STYLE_DX, _LABEL_STYLE_DY
#   ALONG_T = [.5, .35, .65, .2]   _ALONG_T
#   MEASURE_SHIFT = 0.6            _MEASURE_SHIFT
#   W_LABEL, W_POINT = 3, 3        _W_LABEL, _W_POINT
#   W_LINE, W_EDGE = 20, 2         _W_LINE, _W_EDGE
#   W_DIR = 0.15                   _W_DIR
#   DIR_X, DIR_Y                   _DIR_X, _DIR_Y    (k·45°, counter-clockwise, y up)
#   EDGE_X, EDGE_Y                 _EDGE_X, _EDGE_Y
#   PRIORITY                       _PRIORITY         (point 0, line 1, measure 2)
#   0.02 (not the style side)      _NOT_HOME
#   0.8 (outer ring, far offset)   _OUTER
#   0.08·i, 0.05 (along)           _ALONG_STEP, _ALONG_OTHER_SIDE
#   0.3 (measure shift)            _MEASURE_PENALTY
#   eps = 1.5 (awayOctant)         _AWAY_EPS
#   64 links, 16 chords            _POLYLINE_LINKS, _ARC_CHORDS
#   strokeWidth ?? 2 (pad)         _DEFAULT_STROKE   (pad = 1 + width / 2)
#   (after 5d88ff083) GAP_TIE      _GAP_TIE = 1e-9   (rad, equal gaps)
#   (after 5d88ff083) OCTANT_TIE   _OCTANT_TIE = 1e-9 (octants, a half octant)
#   (after 5d88ff083) COST_TIE     _COST_TIE = 1e-12 (relative, equal costs)
_BASE = 1.0
HYSTERESIS = 0.75
ANCHOR_EPS = 0.5
POINT_OBSTACLE_R = 5.0
ALONG_GAP = 4.0
_LABEL_STYLE_DX = 1
_LABEL_STYLE_DY = -1
_ALONG_T = (0.5, 0.35, 0.65, 0.2)
_MEASURE_SHIFT = 0.6

_W_LABEL = 3
_W_POINT = 3
_W_LINE = 20
_W_EDGE = 2
_W_DIR = 0.15

_NOT_HOME = 0.02
_OUTER = 0.8
_ALONG_STEP = 0.08
_ALONG_OTHER_SIDE = 0.05
_MEASURE_PENALTY = 0.3
_AWAY_EPS = 1.5
_POLYLINE_LINKS = 64
_ARC_CHORDS = 16
_DEFAULT_STROKE = 2

_SQRT1_2 = math.sqrt(0.5)  # Math.SQRT1_2
_DIR_X = (1, _SQRT1_2, 0, -_SQRT1_2, -1, -_SQRT1_2, 0, _SQRT1_2)
_DIR_Y = (0, _SQRT1_2, 1, _SQRT1_2, 0, -_SQRT1_2, -1, -_SQRT1_2)
# The corner of the box facing the anchor for the direction k (y up).
_EDGE_X = (-1, -1, 0, 1, 1, 1, 0, -1)
_EDGE_Y = (0, -1, -1, -1, 0, 1, 1, 1)

_PRIORITY = {'point': 0, 'line': 1, 'measure': 2}
_TAU = 2 * math.pi
_INF = math.inf
# Margin of the (exact) culling of geometry far from every candidate of a
# label, CSS px: far above any rounding of the hit tests.
_CULL_MARGIN = 1.0
# Ties (after 5d88ff083, agreed with the client; the rule is in the module
# docstring): gaps of awayOctant equal within _GAP_TIE rad, a direction at a
# half octant within _OCTANT_TIE octants, costs equal within the relative
# _COST_TIE.
_GAP_TIE = 1e-9
_OCTANT_TIE = 1e-9
_COST_TIE = 1e-12
_COST_BAR = 1 - _COST_TIE


# ---------------------------------------------------------------- input


# A missing field or a value of a wrong type in the input: a ValueError.
_SHAPE_ERRORS = (AttributeError, IndexError, KeyError, OverflowError, TypeError)


def _input(what: str):
    """Errors of the input's shape (a missing field, a wrong type) as ``ValueError``."""

    def wrap(fn):
        @functools.wraps(fn)
        def checked(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except _SHAPE_ERRORS as e:
                raise ValueError(f'{what}: malformed input ({type(e).__name__}: {e})') from e

        return checked

    return wrap


def _num(v: Any, what: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(f'{what}: number expected, got {v!r}')
    f = float(v)
    if not math.isfinite(f):
        raise ValueError(f'{what}: finite number expected, got {v!r}')
    return f


def _nums(v: Any, what: str, size: int | None = None, multiple: int = 1) -> tuple[float, ...]:
    if isinstance(v, (str, bytes)) or not isinstance(v, Sequence):
        raise ValueError(f'{what}: list of numbers expected')
    out = tuple(_num(x, what) for x in v)
    if size is not None and len(out) != size:
        raise ValueError(f'{what}: {size} numbers expected, got {len(out)}')
    if len(out) % multiple:
        raise ValueError(f'{what}: a multiple of {multiple} numbers expected, got {len(out)}')
    return out


def _truthy(v: Any) -> bool:
    """Truthiness of a JavaScript value read from JSON."""
    if v is None or v is False:
        return False
    if isinstance(v, (int, float)):
        return v == v and v != 0
    if isinstance(v, str):
        return v != ''
    return True


@dataclass(frozen=True, slots=True)
class LabelPlace:
    """How a label is laid out (``LabelPlace`` of ``layout.ts``)."""

    kind: str  # 'point' | 'line' | 'measure'
    pinned: bool = False
    #: Gap of the box from the anchor, CSS px (a point: radius of its dot + gap).
    reach: float = 0.0
    #: Visible ends of the label's line (segment, line, ray), CSS px.
    along: tuple[float, float, float, float] | None = None


@dataclass(frozen=True, slots=True)
class Label:
    """A label of the display list: the fields the solver reads (``DlLabel``)."""

    id: str
    ax: float
    ay: float
    box: tuple[float, float, float, float]
    edge: tuple[float, float]
    place: LabelPlace | None = None
    x: float | None = None
    y: float | None = None


@dataclass(frozen=True, slots=True)
class Point:
    id: str
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Linear:
    id: str
    x1: float
    y1: float
    x2: float
    y2: float
    kind: str = 'segment'


@dataclass(frozen=True, slots=True)
class Circle:
    id: str
    cx: float
    cy: float
    r: float


@dataclass(frozen=True, slots=True)
class Polygon:
    id: str
    pts: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class Polyline:
    id: str
    pts: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class Arc:
    """Arc, sector or circle segment: screen start angle (y down) and signed sweep."""

    id: str
    cx: float
    cy: float
    r: float
    start: float
    sweep: float
    kind: str = 'arc'  # 'arc' | 'sector' | 'circlesegment'


@dataclass(frozen=True, slots=True)
class Angle:
    """Angle decoration: arcs ``radii`` around ``(x, y)`` or the right-angle mark ``square``."""

    id: str
    x: float
    y: float
    start: float
    sweep: float
    radii: tuple[float, ...] = ()
    square: tuple[float, ...] | None = None
    owner: str | None = None


@dataclass(frozen=True, slots=True)
class Ticks:
    """Tick marks: lines ``x1, y1, x2, y2`` in a row, stroke width ``width``."""

    id: str
    pts: tuple[float, ...]
    width: float
    owner: str | None = None


@dataclass(frozen=True, slots=True)
class DisplayList:
    """The parts of the client's display list that the solver reads."""

    points: tuple[Point, ...] = ()
    linears: tuple[Linear, ...] = ()
    circles: tuple[Circle, ...] = ()
    polygons: tuple[Polygon, ...] = ()
    arcs: tuple[Arc, ...] = ()
    polylines: tuple[Polyline, ...] = ()
    angles: tuple[Angle, ...] = ()
    ticks: tuple[Ticks, ...] = ()
    labels: tuple[Label, ...] = ()

    @classmethod
    @_input('display list')
    def from_dict(cls, d: Mapping[str, Any]) -> 'DisplayList':
        """From the JSON shape of the client's display list (its field names)."""

        def items(key):
            v = d.get(key) or ()
            if isinstance(v, (str, bytes, Mapping)) or not isinstance(v, Sequence):
                raise ValueError(f'{key}: list expected')
            return v

        def place(p):
            if p is None:
                return None
            kind = p.get('kind')
            if kind not in _PRIORITY:
                raise ValueError(f'label place kind: point, line or measure expected, got {kind!r}')
            along = p.get('along')
            return LabelPlace(
                kind=kind,
                pinned=_truthy(p.get('pinned')),
                reach=_num(p.get('reach', 0), 'reach'),
                along=_nums(along, 'along', 4) if along is not None else None,
            )

        return cls(
            points=tuple(Point(str(p['id']), _num(p['x'], 'point'), _num(p['y'], 'point')) for p in items('points')),
            linears=tuple(
                Linear(str(s['id']), *_nums([s['x1'], s['y1'], s['x2'], s['y2']], 'linear'), kind=s.get('kind', 'segment'))
                for s in items('linears')
            ),
            circles=tuple(Circle(str(c['id']), *_nums([c['cx'], c['cy'], c['r']], 'circle')) for c in items('circles')),
            polygons=tuple(Polygon(str(p['id']), _nums(p['pts'], 'polygon', multiple=2)) for p in items('polygons')),
            arcs=tuple(
                Arc(str(a['id']), *_nums([a['cx'], a['cy'], a['r'], a['start'], a['sweep']], 'arc'), kind=a.get('kind', 'arc'))
                for a in items('arcs')
            ),
            polylines=tuple(Polyline(str(p['id']), _nums(p['pts'], 'polyline', multiple=2)) for p in items('polylines')),
            angles=tuple(
                Angle(
                    str(a['id']),
                    *_nums([a['x'], a['y'], a['start'], a['sweep']], 'angle'),
                    radii=_nums(a.get('radii') or (), 'angle radii'),
                    square=_nums(a['square'], 'angle square', multiple=2) if a.get('square') is not None else None,
                    owner=a.get('owner'),
                )
                for a in items('angles')
            ),
            ticks=tuple(
                Ticks(str(t['id']), _nums(t['pts'], 'ticks', multiple=4), _num(t['width'], 'ticks width'), owner=t.get('owner'))
                for t in items('ticks')
            ),
            labels=tuple(
                Label(
                    id=str(lb['id']),
                    ax=_num(lb['ax'], 'label anchor'),
                    ay=_num(lb['ay'], 'label anchor'),
                    box=_nums(lb['box'], 'label box', 4),
                    edge=_nums(lb['edge'], 'label edge', 2),
                    place=place(lb.get('place')),
                    x=_num(lb['x'], 'label x') if lb.get('x') is not None else None,
                    y=_num(lb['y'], 'label y') if lb.get('y') is not None else None,
                )
                for lb in items('labels')
            ),
        )


@dataclass(frozen=True, slots=True)
class LayoutView:
    """Frame of the solver, CSS px: origin ``x``, ``y`` (none — 0) and size."""

    width: float
    height: float
    x: float | None = None
    y: float | None = None


@dataclass(frozen=True, slots=True)
class Paint:
    """What the solver reads of the canvas paint: per element stroke width and sector sides."""

    stroke_width: Mapping[str, float]
    sector_sides: frozenset[str] = frozenset()

    @classmethod
    @_input('paint')
    def from_dict(cls, d: Mapping[str, Any]) -> 'Paint':
        """From ``{'byId': {id: {'strokeWidth': w, 'sectorSides': bool}}}`` (the client's ``CanvasPaint``)."""
        by_id = d.get('byId') or {}
        widths = {}
        sides = set()
        for key, entry in by_id.items():
            entry = entry or {}
            if entry.get('strokeWidth') is not None:
                widths[str(key)] = _num(entry['strokeWidth'], 'strokeWidth')
            if _truthy(entry.get('sectorSides')):
                sides.add(str(key))
        return cls(widths, frozenset(sides))


def _list_dict(dl: DisplayList) -> dict[str, Any]:
    """The JSON shape of a :class:`DisplayList`, to check it as :meth:`DisplayList.from_dict` does."""

    def place(p):
        if p is None:
            return None
        return {'kind': p.kind, 'pinned': p.pinned, 'reach': p.reach, 'along': p.along}

    return {
        'points': [{'id': p.id, 'x': p.x, 'y': p.y} for p in dl.points],
        'linears': [{'id': s.id, 'x1': s.x1, 'y1': s.y1, 'x2': s.x2, 'y2': s.y2, 'kind': s.kind} for s in dl.linears],
        'circles': [{'id': c.id, 'cx': c.cx, 'cy': c.cy, 'r': c.r} for c in dl.circles],
        'polygons': [{'id': p.id, 'pts': p.pts} for p in dl.polygons],
        'arcs': [
            {'id': a.id, 'cx': a.cx, 'cy': a.cy, 'r': a.r, 'start': a.start, 'sweep': a.sweep, 'kind': a.kind}
            for a in dl.arcs
        ],
        'polylines': [{'id': p.id, 'pts': p.pts} for p in dl.polylines],
        'angles': [
            {'id': a.id, 'x': a.x, 'y': a.y, 'start': a.start, 'sweep': a.sweep, 'radii': a.radii,
             'square': a.square, 'owner': a.owner}
            for a in dl.angles
        ],
        'ticks': [{'id': k.id, 'pts': k.pts, 'width': k.width, 'owner': k.owner} for k in dl.ticks],
        'labels': [
            {'id': lb.id, 'ax': lb.ax, 'ay': lb.ay, 'box': lb.box, 'edge': lb.edge, 'place': place(lb.place),
             'x': lb.x, 'y': lb.y}
            for lb in dl.labels
        ],
    }


@_input('display list')
def _as_list(display_list) -> DisplayList:
    if isinstance(display_list, DisplayList):
        # The same checks as the JSON shape: finite numbers, sizes, kinds.
        return DisplayList.from_dict(_list_dict(display_list))
    if isinstance(display_list, Mapping):
        return DisplayList.from_dict(display_list)
    raise ValueError('display_list: DisplayList or mapping expected')


@_input('paint')
def _as_paint(paint) -> Paint | None:
    if paint is None:
        return None
    if isinstance(paint, Paint):
        return Paint(
            {str(key): _num(w, 'strokeWidth') for key, w in paint.stroke_width.items()},
            frozenset(str(key) for key in paint.sector_sides),
        )
    if isinstance(paint, Mapping):
        return Paint.from_dict(paint)
    raise ValueError('paint: Paint, mapping or None expected')


@_input('view')
def _as_view(view) -> tuple[float, float, float, float]:
    if isinstance(view, Mapping):
        view = LayoutView(view['width'], view['height'], view.get('x'), view.get('y'))
    if not isinstance(view, LayoutView):
        raise ValueError('view: LayoutView or mapping expected')
    x0 = 0.0 if view.x is None else _num(view.x, 'view x')
    y0 = 0.0 if view.y is None else _num(view.y, 'view y')
    return (x0, y0, x0 + _num(view.width, 'view width'), y0 + _num(view.height, 'view height'))


@_input('memory')
def _as_memory(memory) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if memory is None:
        return out
    if not isinstance(memory, Mapping):
        raise ValueError('memory: mapping or None expected')
    for key, entry in memory.items():
        k = entry['k']
        if isinstance(k, bool) or not isinstance(k, (int, float)) or not math.isfinite(k) or k != int(k):
            raise ValueError(f'memory {key!r}: integer k expected, got {k!r}')
        out[str(key)] = {'k': int(k), 'ax': _num(entry['ax'], 'memory ax'), 'ay': _num(entry['ay'], 'memory ay')}
    return out


# ------------------------------------------------------- geometry.ts


def _seg_hit(x1: float, y1: float, x2: float, y2: float, l: float, t: float, r: float, b: float) -> bool:
    """``segmentHitsBox`` (Liang–Barsky on the closed box)."""
    lo = 0.0
    hi = 1.0
    d = x2 - x1
    if d == 0:
        if x1 < l or x1 > r:
            return False
    else:
        a = (l - x1) / d
        z = (r - x1) / d
        if a < z:
            mn, mx = a, z
        else:
            mn, mx = z, a
        if mn > lo:
            lo = mn
        if mx < hi:
            hi = mx
        if lo > hi:
            return False
    d = y2 - y1
    if d == 0:
        if y1 < t or y1 > b:
            return False
    else:
        a = (t - y1) / d
        z = (b - y1) / d
        if a < z:
            mn, mx = a, z
        else:
            mn, mx = z, a
        if mn > lo:
            lo = mn
        if mx < hi:
            hi = mx
        if lo > hi:
            return False
    return True


def _circle_hit(cx: float, cy: float, r: float, l: float, t: float, rr: float, b: float) -> bool:
    """``circleHitsBox``: the circle line crosses the box (nearest ≤ r ≤ farthest)."""
    nx = (cx if cx < rr else rr)
    nx = (l if l > nx else nx) - cx
    ny = (cy if cy < b else b)
    ny = (t if t > ny else ny) - cy
    fx1 = abs(l - cx)
    fx2 = abs(rr - cx)
    fx = fx1 if fx1 > fx2 else fx2
    fy1 = abs(t - cy)
    fy2 = abs(b - cy)
    fy = fy1 if fy1 > fy2 else fy2
    r2 = r * r
    return nx * nx + ny * ny <= r2 and fx * fx + fy * fy >= r2


def _in_sweep(a: float, start: float, sweep: float) -> bool:
    d = start - a if sweep < 0 else a - start
    s = abs(sweep)
    return s >= _TAU - 1e-9 or math.fmod(math.fmod(d, _TAU) + _TAU, _TAU) <= s + 1e-9


def _arc_hit(cx, cy, r, start, sweep, e1x, e1y, e2x, e2y, l, t, rr, b) -> bool:
    """``arcHitsBox`` with the two ends ``cx + r·cos(start)``… computed once."""
    if not _circle_hit(cx, cy, r, l, t, rr, b):
        return False
    if e1x >= l and e1x <= rr and e1y >= t and e1y <= b:
        return True
    if e2x >= l and e2x <= rr and e2y >= t and e2y <= b:
        return True
    r2 = r * r
    for x in (l, rr):
        dx = x - cx
        q = r2 - dx * dx
        if q >= 0:
            s = math.sqrt(q)
            y = cy + s
            if y >= t and y <= b and _in_sweep(_atan2(y - cy, x - cx), start, sweep):
                return True
            y = cy - s
            if y >= t and y <= b and _in_sweep(_atan2(y - cy, x - cx), start, sweep):
                return True
    for y in (t, b):
        dy = y - cy
        q = r2 - dy * dy
        if q >= 0:
            s = math.sqrt(q)
            x = cx + s
            if x >= l and x <= rr and _in_sweep(_atan2(y - cy, x - cx), start, sweep):
                return True
            x = cx - s
            if x >= l and x <= rr and _in_sweep(_atan2(y - cy, x - cx), start, sweep):
                return True
    return False


def segment_hits_box(x1: float, y1: float, x2: float, y2: float, box: Sequence[float]) -> bool:
    """The segment meets the closed box ``(l, t, r, b)`` (``segmentHitsBox``)."""
    l, t, r, b = box
    return _seg_hit(x1, y1, x2, y2, l, t, r, b)


def circle_hits_box(cx: float, cy: float, r: float, box: Sequence[float]) -> bool:
    """The circle line meets the box (``circleHitsBox``)."""
    l, t, rr, b = box
    return _circle_hit(cx, cy, r, l, t, rr, b)


def arc_hits_box(cx: float, cy: float, r: float, start: float, sweep: float, box: Sequence[float]) -> bool:
    """The arc meets the box (``arcHitsBox``); angles on the screen, y down."""
    l, t, rr, b = box
    e1x = cx + r * _cos(start)
    e1y = cy + r * _sin(start)
    a2 = start + sweep
    return _arc_hit(cx, cy, r, start, sweep, e1x, e1y, cx + r * _cos(a2), cy + r * _sin(a2), l, t, rr, b)


# Obstacle tuples: (kind, id, pad, gl, gt, gr, gb, *shape), where g* is the
# box of the shape grown by pad + _CULL_MARGIN (only for culling).
_SEG = 0
_CIRCLE = 1
_ARC = 2


def _geometry(dl: DisplayList, paint: Paint | None) -> list[tuple]:
    """``geometryObstacles``: the same order and paddings as the client."""
    out: list[tuple] = []
    widths = paint.stroke_width if paint is not None else {}
    m = _CULL_MARGIN

    def pad(oid: str) -> float:
        w = widths.get(oid)
        return 1 + (_DEFAULT_STROKE if w is None else w) / 2

    def segment(oid, x1, y1, x2, y2, padding=None):
        p = pad(oid) if padding is None else padding
        g = p + m
        out.append((
            _SEG, oid, p,
            (x1 if x1 < x2 else x2) - g, (y1 if y1 < y2 else y2) - g,
            (x1 if x1 > x2 else x2) + g, (y1 if y1 > y2 else y2) + g,
            x1, y1, x2, y2,
        ))

    def chain(oid, pts, closed=False):
        for i in range(2, len(pts), 2):
            segment(oid, pts[i - 2], pts[i - 1], pts[i], pts[i + 1])
        if closed and len(pts) >= 4:
            segment(oid, pts[-2], pts[-1], pts[0], pts[1])

    def arc(oid, cx, cy, r, start, sweep):
        p = pad(oid)
        g = abs(r) + p + m
        a2 = start + sweep
        out.append((
            _ARC, oid, p, cx - g, cy - g, cx + g, cy + g,
            cx, cy, r, start, sweep,
            cx + r * _cos(start), cy + r * _sin(start), cx + r * _cos(a2), cy + r * _sin(a2),
        ))

    for s in dl.linears:
        segment(s.id, s.x1, s.y1, s.x2, s.y2)
    for pg in dl.polygons:
        chain(pg.id, pg.pts, True)
    for pl in dl.polylines:
        chain(pl.id, pl.pts)
    for c in dl.circles:
        p = pad(c.id)
        g = abs(c.r) + p + m
        out.append((_CIRCLE, c.id, p, c.cx - g, c.cy - g, c.cx + g, c.cy + g, c.cx, c.cy, c.r))
    sides = paint.sector_sides if paint is not None else frozenset()
    for a in dl.arcs:
        arc(a.id, a.cx, a.cy, a.r, a.start, a.sweep)
        x1 = a.cx + a.r * _cos(a.start)
        y1 = a.cy + a.r * _sin(a.start)
        x2 = a.cx + a.r * _cos(a.start + a.sweep)
        y2 = a.cy + a.r * _sin(a.start + a.sweep)
        if a.kind == 'circlesegment':
            segment(a.id, x1, y1, x2, y2)
        if a.kind == 'sector' and a.id in sides:
            segment(a.id, a.cx, a.cy, x1, y1)
            segment(a.id, a.cx, a.cy, x2, y2)
    for a in dl.angles:
        oid = a.owner if a.owner is not None else a.id
        if a.square is not None:
            chain(oid, a.square)
        for r in a.radii:
            arc(oid, a.x, a.y, r, a.start, a.sweep)
    for tk in dl.ticks:
        oid = tk.owner if tk.owner is not None else tk.id
        pts = tk.pts
        for i in range(0, len(pts), 4):
            segment(oid, pts[i], pts[i + 1], pts[i + 2], pts[i + 3], 1 + tk.width / 2)
    return out


def _hit(o: tuple, l: float, t: float, r: float, b: float) -> bool:
    """``obstacle.hit(box)``: the shape against the box grown by the obstacle's pad."""
    p = o[2]
    kind = o[0]
    if kind == _SEG:
        return _seg_hit(o[7], o[8], o[9], o[10], l - p, t - p, r + p, b + p)
    if kind == _CIRCLE:
        return _circle_hit(o[7], o[8], o[9], l - p, t - p, r + p, b + p)
    return _arc_hit(o[7], o[8], o[9], o[10], o[11], o[12], o[13], o[14], o[15], l - p, t - p, r + p, b + p)


def geometry_obstacles(display_list, paint=None) -> list[tuple[str, Any]]:
    """``geometryObstacles``: ``[(id, hit)]`` in the client's order; ``hit(box)`` takes ``(l, t, r, b)``."""
    dl = _as_list(display_list)
    obstacles = _geometry(dl, _as_paint(paint))
    return [(o[1], (lambda box, o=o: _hit(o, *box))) for o in obstacles]


def geometry_pairs(display_list, paint=None) -> list[tuple[str, str]]:
    """``geometryPairs``: (label, element) whose drawn outline crosses the label box, sorted as the client sorts."""
    dl = _as_list(display_list)
    obstacles = _geometry(dl, _as_paint(paint))
    pairs: dict[str, tuple[str, str]] = {}
    for lb in dl.labels:
        l, t, r, b = lb.box
        for o in obstacles:
            if _hit(o, l, t, r, b):
                key = json.dumps([lb.id, o[1]], ensure_ascii=False, separators=(',', ':'))
                pairs[key] = (lb.id, o[1])
    # Array.prototype.sort of strings: by UTF-16 code units.
    return [pairs[k] for k in sorted(pairs, key=lambda s: s.encode('utf-16-be', 'surrogatepass'))]


# ---------------------------------------------------------- layout.ts


def _octant(x: float) -> int:
    """Octant of ``x`` = angle / 45°: the nearest, a half (within the tie) up."""
    return ((math.floor(x + 0.5 + _OCTANT_TIE) % 8) + 8) % 8


def _octant_dist(a: int, b: int) -> int:
    d = abs(a - b) % 8
    return d if d < 8 - d else 8 - d


def _octant_of(dx: float, dy_down: float) -> int:
    """Direction (screen y down) → the nearest of the eight."""
    a = _atan2(-dy_down, dx)
    return _octant(a / (math.pi / 4))


def _box_at(x, y, w, h, ex, ey) -> tuple[float, float, float, float]:
    """Box whose corner ``edge`` (y up) stands at the screen point ``(x, y)``."""
    left = x - ((ex + 1) / 2) * w
    top = y - ((1 - ey) / 2) * h
    return (left, top, left + w, top + h)


def _overlap_area(al, at, ar, ab, bl, bt, br, bb) -> float:
    w = (ar if ar < br else br) - (al if al > bl else bl)
    h = (ab if ab < bb else bb) - (at if at > bt else bt)
    return w * h if (w > 0 and h > 0) else 0


def _collect(dl: DisplayList) -> tuple[list[float], list[float]]:
    """Points and lines of ``collectObstacles`` (polygon sides, ≤ 64 links of a polyline, ≤ 16 chords of an arc)."""
    points: list[float] = []
    segs: list[float] = []
    for p in dl.points:
        points += (p.x, p.y)
    for s in dl.linears:
        segs += (s.x1, s.y1, s.x2, s.y2)
    for pg in dl.polygons:
        pts = pg.pts
        n = len(pts) // 2
        for i in range(n):
            j = (i + 1) % n
            segs += (pts[2 * i], pts[2 * i + 1], pts[2 * j], pts[2 * j + 1])
    for pl in dl.polylines:
        pts = pl.pts
        n = len(pts) // 2
        step = max(1, math.ceil((n - 1) / _POLYLINE_LINKS))
        i = 0
        while i + step < n:
            segs += (pts[2 * i], pts[2 * i + 1], pts[2 * (i + step)], pts[2 * (i + step) + 1])
            i += step
    for a in dl.arcs:
        n = max(2, min(_ARC_CHORDS, math.ceil(abs(a.sweep) / (math.pi / 8))))
        px = a.cx + a.r * _cos(a.start)
        py = a.cy + a.r * _sin(a.start)
        for i in range(1, n + 1):
            ang = a.start + (a.sweep * i) / n
            qx = a.cx + a.r * _cos(ang)
            qy = a.cy + a.r * _sin(ang)
            segs += (px, py, qx, qy)
            px = qx
            py = qy
    return points, segs


def _near(points: list[float], segs: list[float], rl, rt, rr, rb) -> tuple[list[tuple[float, float]], list[float]]:
    """``near``: points and lines around the region of one label."""
    pr = POINT_OBSTACLE_R
    near_points = []
    for i in range(0, len(points), 2):
        x = points[i]
        y = points[i + 1]
        if x + pr >= rl and x - pr <= rr and y + pr >= rt and y - pr <= rb:
            near_points.append((x, y))
    near_segs: list[float] = []
    for i in range(0, len(segs), 4):
        x1 = segs[i]
        y1 = segs[i + 1]
        x2 = segs[i + 2]
        y2 = segs[i + 3]
        if (
            (x1 if x1 > x2 else x2) < rl
            or (x1 if x1 < x2 else x2) > rr
            or (y1 if y1 > y2 else y2) < rt
            or (y1 if y1 < y2 else y2) > rb
        ):
            continue
        near_segs += (x1, y1, x2, y2)
    return near_points, near_segs


def _overlap_cost(box, points, geometry, placed, view, limit=_INF) -> float:
    """``overlapCost``: overlaps of the box without the direction penalty; stops above ``limit``."""
    l, t, r, b = box
    cost = 0.0
    area = (r - l) * (b - t)
    if not area > 1:
        area = 1
    vl, vt, vr, vb = view
    if l < vl or t < vt or r > vr or b > vb:
        inside = _overlap_area(l, t, r, b, vl, vt, vr, vb)
        cost += _W_EDGE * (1 + (area - inside) / area)
        if cost > limit:
            return cost
    for pl, pt, prr, pb in placed:
        a = _overlap_area(l, t, r, b, pl, pt, prr, pb)
        if a > 0:
            cost += _W_LABEL * (1 + a / area)
            if cost > limit:
                return cost
    pr = POINT_OBSTACLE_R
    for x, y in points:
        if x + pr > l and x - pr < r and y + pr > t and y - pr < b:
            cost += _W_POINT
            if cost > limit:
                return cost
    for o in geometry:
        if _hit(o, l, t, r, b):
            cost += _W_LINE
            if cost > limit:
                return cost
    return cost


def _away_octant(ax: float, ay: float, segs: list[float]) -> int | None:
    """``awayOctant``: the bisector of the largest gap between the lines meeting at the anchor."""
    angles: list[float] = []
    eps = _AWAY_EPS
    for i in range(0, len(segs), 4):
        x1 = segs[i]
        y1 = segs[i + 1]
        x2 = segs[i + 2]
        y2 = segs[i + 3]
        d1 = _hypot(x1 - ax, y1 - ay)
        d2 = _hypot(x2 - ax, y2 - ay)
        if d1 < eps and d2 > eps:
            angles.append(_atan2(-(y2 - ay), x2 - ax))
        elif d2 < eps and d1 > eps:
            angles.append(_atan2(-(y1 - ay), x1 - ax))
        elif d1 > eps and d2 > eps:
            # The anchor inside the segment (a point on a line): the line goes both ways.
            length = _hypot(x2 - x1, y2 - y1)
            if length > 0:
                cross = abs((x2 - x1) * (y1 - ay) - (x1 - ax) * (y2 - y1)) / length
                dot = ((ax - x1) * (x2 - x1) + (ay - y1) * (y2 - y1)) / (length * length)
                if cross < eps and dot > 0 and dot < 1:
                    a = _atan2(-(y2 - y1), x2 - x1)
                    angles.append(a)
                    angles.append(a + math.pi)
    if not angles:
        return None
    norm = []
    for a in angles:
        n = math.fmod(math.fmod(a, _TAU) + _TAU, _TAU)
        # A hair below 2π is the direction 0: the order starts there (a tie).
        norm.append(n - _TAU if n > _TAU - _GAP_TIE else n)
    norm.sort()
    count = len(norm)
    widest = -1.0
    for i in range(count):
        a = norm[i]
        b = norm[i + 1] if i + 1 < count else norm[0] + _TAU
        if b - a > widest:
            widest = b - a
    # Of the gaps as wide as the widest (a tie), the first in this order.
    best_mid = 0.0
    for i in range(count):
        a = norm[i]
        b = norm[i + 1] if i + 1 < count else norm[0] + _TAU
        if b - a >= widest - _GAP_TIE:
            best_mid = (a + b) / 2
            break
    return _octant(best_mid / (math.pi / 4))


def _around(ax, ay, reach, w, h, pref, home, extra, boxes, penalties) -> None:
    """``aroundCandidates``: eight places at ``reach`` around the anchor."""
    for k in range(8):
        x = ax + _DIR_X[k] * reach
        y = ay - _DIR_Y[k] * reach
        boxes.append(_box_at(x, y, w, h, _EDGE_X[k], _EDGE_Y[k]))
        penalty = _W_DIR * _octant_dist(k, pref) + (0 if k == home else _NOT_HOME)
        penalties.append(penalty if extra is None else penalty + extra)


def _along(along, w, h, gap, extra, boxes, penalties) -> bool:
    """``alongCandidates``: four fractions of the line on both sides; False for a line of no length."""
    x1, y1, x2, y2 = along
    length = _hypot(x2 - x1, y2 - y1)
    if not length > 0:
        return False
    nx = -(y2 - y1) / length
    ny = (x2 - x1) / length
    own = 0 if nx * _LABEL_STYLE_DX + ny * _LABEL_STYLE_DY >= 0 else 1
    for side in (0, 1):
        sx = -nx if side else nx
        sy = -ny if side else ny
        k = _octant_of(sx, sy)
        for i, t in enumerate(_ALONG_T):
            x = x1 + (x2 - x1) * t + sx * gap
            y = y1 + (y2 - y1) * t + sy * gap
            boxes.append(_box_at(x, y, w, h, _EDGE_X[k], _EDGE_Y[k]))
            penalty = _ALONG_STEP * i + (0 if side == own else _ALONG_OTHER_SIDE)
            penalties.append(penalty if extra is None else penalty + extra)
    return True


def _sign(v: float) -> int:
    return 1 if v > 0 else (-1 if v < 0 else 0)


def _candidates(label: Label, segs: list[float]) -> tuple[list, list]:
    """``candidatesOf``: boxes and direction penalties of a label's places, in the client's order."""
    place = label.place
    bl, bt, br, bb = label.box
    w = br - bl
    h = bb - bt
    boxes: list[tuple[float, float, float, float]] = []
    penalties: list[float] = []
    if place.kind == 'measure':
        # measureCandidates: its own place and eight shifts.
        boxes.append((bl, bt, br, bb))
        penalties.append(0)
        d = h * _MEASURE_SHIFT
        for k in range(8):
            dx = _DIR_X[k] * d
            dy = -_DIR_Y[k] * d
            boxes.append((bl + dx, bt + dy, br + dx, bb + dy))
            penalties.append(_MEASURE_PENALTY)
        return boxes, penalties
    if place.along is not None:
        if _along(place.along, w, h, ALONG_GAP, None, boxes, penalties):
            _along(place.along, w, h, ALONG_GAP + (w if w > h else h), _OUTER, boxes, penalties)
            return boxes, penalties
    # The style direction: the corner at the anchor → the opposite direction.
    sx = _sign(label.edge[0])
    sy = _sign(label.edge[1])
    home = 1
    for k in range(8):
        if _EDGE_X[k] == sx and _EDGE_Y[k] == sy:
            home = k
    away = _away_octant(label.ax, label.ay, segs) if place.kind == 'point' else None
    pref = home if away is None else away
    _around(label.ax, label.ay, place.reach, w, h, pref, home, None, boxes, penalties)
    _around(label.ax, label.ay, place.reach + (w if w > h else h), w, h, pref, home, _OUTER, boxes, penalties)
    return boxes, penalties


def layout(display_list, view, memory=None, paint=None):
    """Lay the labels out without overlaps (``layoutLabels``).

    ``display_list`` — :class:`DisplayList` or its JSON shape; ``view`` —
    :class:`LayoutView` or ``{'width', 'height', 'x'?, 'y'?}``; ``memory`` —
    the previous ``{id: {'k', 'ax', 'ay'}}`` or ``None``; ``paint`` —
    :class:`Paint`, ``{'byId': …}`` or ``None``.

    Returns ``(placements, memory, stats)``: ``placements`` — ``{id: {'k',
    'center', 'box', 'x', 'y'}}`` for every label the solver placed (not
    pinned, with ``place``), in document order; ``(x, y)`` is the corner
    ``edge`` of the new box. ``memory`` — the new memory; ``stats`` —
    ``{'evaluated': labels whose place was searched, 'moved': labels that
    left their remembered place}``.
    """
    dl = _as_list(display_list)
    view_box = _as_view(view)
    paint = _as_paint(paint)
    mem = _as_memory(memory)
    stats = {'evaluated': 0, 'moved': 0}
    labels = dl.labels
    if not labels:
        return {}, mem, stats
    all_points, all_segs = _collect(dl)
    geometry = _geometry(dl, paint)
    placed: list[tuple[float, float, float, float]] = []
    order: list[Label] = []
    for lb in labels:
        if lb.place is None or lb.place.pinned:
            placed.append(lb.box)
        else:
            order.append(lb)
    # Stable order: the kind's priority, then the document order.
    order = [lb for _, _, lb in sorted((_PRIORITY[lb.place.kind], i, lb) for i, lb in enumerate(order))]
    # A pinned label keeps its former automatic place in the memory.
    seen = {lb.id for lb in labels if lb.place is not None and lb.place.pinned}
    chosen_by_id: dict[str, tuple[int, tuple[float, float, float, float], Label]] = {}

    for label in order:
        seen.add(label.id)
        bl, bt, br, bb = label.box
        w = br - bl
        h = bb - bt
        place = label.place
        pad = place.reach + 2 * (w if w > h else h) + ALONG_GAP + 2
        rl = label.ax - pad
        rt = label.ay - pad
        rr = label.ax + pad
        rb = label.ay + pad
        along = place.along
        if along is not None:
            rl = min(rl, min(along[0], along[2]) - pad)
            rt = min(rt, min(along[1], along[3]) - pad)
            rr = max(rr, max(along[0], along[2]) + pad)
            rb = max(rb, max(along[1], along[3]) + pad)
        points, segs = _near(all_points, all_segs, rl, rt, rr, rb)
        local = [p for p in placed if p[2] >= rl and p[0] <= rr and p[3] >= rt and p[1] <= rb]
        boxes, penalties = _candidates(label, segs)
        if not boxes:
            placed.append(label.box)
            continue
        # Geometry that no candidate box can touch is left out (the hits it
        # would add are all false, so the costs are the client's).
        ul = min(bx[0] for bx in boxes)
        ut = min(bx[1] for bx in boxes)
        ur = max(bx[2] for bx in boxes)
        ub = max(bx[3] for bx in boxes)
        geo = [o for o in geometry if not (o[5] < ul or o[3] > ur or o[6] < ut or o[4] > ub)]
        by_penalty = sorted(range(len(boxes)), key=lambda i: (penalties[i], i))

        def best(skip: int, limit: float) -> tuple[int, float]:
            """The cheapest place but ``skip`` below ``limit``; a clean place ends the search.

            A place is cheaper only by more than the tie (``_COST_TIE``): of
            equal costs the earlier in ``by_penalty`` (or the limit) wins.
            """
            best_k = -1
            best_cost = limit
            for k in by_penalty:
                if k == skip:
                    continue
                floor = _BASE + penalties[k]
                bar = best_cost * _COST_BAR
                if floor >= bar:
                    break
                c = floor + _overlap_cost(boxes[k], points, geo, local, view_box, best_cost - floor)
                if c < bar:
                    best_k = k
                    best_cost = c
            return best_k, best_cost

        prev = mem.get(label.id)
        prev_k = prev['k'] if prev is not None and prev['k'] < len(boxes) else -1
        if prev_k >= 0:
            prev_overlap = _overlap_cost(boxes[prev_k], points, geo, local, view_box)
            prev_cost = _BASE + penalties[prev_k] + prev_overlap
            prev_clean = prev_overlap == 0
            still = abs(prev['ax'] - label.ax) < ANCHOR_EPS and abs(prev['ay'] - label.ay) < ANCHOR_EPS
            if still and prev_clean:
                chosen = prev_k
            else:
                stats['evaluated'] += 1
                # Hysteresis: a clean former place gives way only to a place 25 % cheaper.
                k, c = best(prev_k, HYSTERESIS * prev_cost if prev_clean else prev_cost)
                chosen = k if k >= 0 and c < prev_cost else prev_k
        else:
            stats['evaluated'] += 1
            chosen = best(-1, _INF)[0]
            if chosen < 0:
                chosen = 0
        if prev is not None and chosen != prev_k:
            stats['moved'] += 1
        placed.append(boxes[chosen])
        chosen_by_id[label.id] = (chosen, boxes[chosen], label)
        mem[label.id] = {'k': chosen, 'ax': label.ax, 'ay': label.ay}
    # Labels that are gone keep no memory.
    for key in [key for key in mem if key not in seen]:
        del mem[key]

    placements: dict[str, dict[str, Any]] = {}
    for lb in labels:
        hit = chosen_by_id.get(lb.id)
        if hit is None or hit[2] is not lb:
            continue
        k, (l, t, r, b), _ = hit
        # moveTo: (x, y) is the corner ``edge`` of the new box.
        bw = r - l
        bh = b - t
        placements[lb.id] = {
            'k': k,
            'center': ((l + r) / 2, (t + b) / 2),
            'box': (l, t, r, b),
            'x': l + ((lb.edge[0] + 1) / 2) * bw,
            'y': t + ((1 - lb.edge[1]) / 2) * bh,
        }
    return placements, mem, stats
