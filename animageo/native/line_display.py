"""The visible part of a line or a ray (``line_display``, 1.12.0).

A line or a ray is drawn to the edge of the frame (``line_display:
"frame"``, the default). With ``line_display: "incident"`` it ends
``line_overhang_px`` style pixels past the outermost of the points that lie
on it by the construction graph; ``visible_range: [t0, t1]`` names the part
explicitly, in the path parameter of the carrier (``carrier/v1``,
docs/native/kernel.md §5.5). The frame still clips the part.

The points on a line are read from the graph only — a point that merely
happens to lie on it numerically does not count:

- the defining points of its producer (:data:`DEFINING_POINTS`) and the
  points the same operation puts on it (:data:`SIBLING_POINTS`);
- the point outputs of an operation that puts them on each of its linear
  arguments (:data:`ON_ARGUMENT`: ``point.on_path``, the intersections, the
  foot of a projection or an altitude) when the line is such an argument;
- a point of a condition ``{kind: "on", point: {ref: P}, object: …}`` whose
  object is the line (``{ref: id}``, or ``{pair: [A, B]}`` of a
  ``line.by_points(A, B)``), in any mode.

Rules (:func:`resolve_visible`), ``h = line_overhang_px / ptUnitStyle``
world units, ``d`` the unit direction of the carrier, ``s(P) = (P − o)·d``:

- ``visible_range`` (two finite numbers; swapped when ``t0 > t1``) wins: the
  part runs from ``P(t0)`` to ``P(t1)`` of the frame of the path, a ray
  clamping ``t`` to ``≥ 0``; no overhang;
- otherwise ``line_display`` other than ``incident`` → the frame (``None``);
- a ray: when a point other than the producer's origin argument is on it,
  from the origin to ``max(0, max s) + h``; otherwise the frame;
- a line with two or more defined points: ``[min s − h, max s + h]``;
- a line with one point whose producer is ``line.parallel`` or
  ``line.perpendicular`` (:data:`LENGTH_FROM`): the length ``L`` of the
  visible part of its ``base`` (a segment: its length; a line or a ray: its
  own visible part, or the part of it inside the frame when it is drawn to
  the frame), centred at the point: ``[s − L/2, s + L/2]``, no overhang;
- otherwise the frame.

The part runs ``[[x0, y0], [x1, y1]]`` along ``d`` (a ray from its origin;
an explicit range from ``P(t0)``); a dashed stroke starts its pattern at
``[x0, y0]``. Manim-free.
"""
from __future__ import annotations

import math
from typing import NamedTuple

__all__ = ['DEFAULT_LINE_DISPLAY', 'DEFAULT_OVERHANG_PX', 'DEFINING_POINTS', 'LENGTH_FROM', 'LINE_DISPLAYS',
           'LineSpec', 'ON_ARGUMENT', 'SIBLING_POINTS', 'STYLE_KEYS', 'classic_visible_part', 'clip_segment',
           'incident_points', 'line_spec', 'resolve_visible', 'visible_segment']

LINE_DISPLAYS = ('frame', 'incident')
DEFAULT_LINE_DISPLAY = 'frame'
DEFAULT_OVERHANG_PX = 12.0
STYLE_KEYS = ('line_display', 'line_overhang_px', 'visible_range')

# producer → its arguments that lie on the line it makes
DEFINING_POINTS = {
    'line.by_points': ('a', 'b'),
    'line.parallel': ('point',),
    'line.perpendicular': ('point',),
    'line.angle_bisector': ('vertex',),
    'line.external_bisector': ('vertex',),
    'line.tangent_at': ('point',),
    'line.tangents_from_point': ('point',),
    'ray.by_points': ('origin', 'through'),
    'ray.by_vector': ('origin',),
    'ray.at_angle': ('vertex',),
}
# producer → {slot of the line: the point outputs of the same operation on it}
SIBLING_POINTS = {
    'line.tangents_from_point': {'tangent.1': ('touch.1',), 'tangent.2': ('touch.2',)},
    'ray.at_angle': {'ray': ('point',)},
}
# operations whose point outputs lie on each of their linear arguments
ON_ARGUMENT = frozenset({
    'point.on_path', 'point.projection', 'point.closest', 'triangle.altitude',
    'intersect.line_line', 'intersect.line_circle', 'intersect.line_conic', 'intersect.line_sector',
    'intersect.function_line', 'intersect.nearest', 'intersect.other_than',
})
# a line through one point takes the length of the visible part of this argument
LENGTH_FROM = {'line.parallel': 'base', 'line.perpendicular': 'base'}
# a ray: the producer argument that is its origin
_RAY_ORIGIN = {'ray.by_points': 'origin', 'ray.by_vector': 'origin', 'ray.at_angle': 'vertex'}
_MAX_DEPTH = 32


class LineSpec(NamedTuple):
    """What the graph says about a line or a ray, by element key (a document
    ID, or a classic name on a classic element).

    ``args`` — ``((slot, key, "point"), …)`` the point arguments of the
    producer (its path frame reads them); ``points`` — the keys of the points
    on it (sorted); ``origin`` — a ray: the key of its origin argument;
    ``length_from`` — ``(key, type)`` of the element whose visible length a
    line through one point takes, else ``None``."""

    id: str
    type: str
    producer: str | None
    args: tuple
    points: tuple
    origin: str | None
    length_from: tuple | None

    def rename(self, name_of) -> 'LineSpec':
        """The spec with every key passed through ``name_of``."""
        return LineSpec(name_of(self.id), self.type, self.producer,
                        tuple((slot, name_of(k), t) for slot, k, t in self.args),
                        tuple(name_of(p) for p in self.points),
                        None if self.origin is None else name_of(self.origin),
                        None if self.length_from is None else (name_of(self.length_from[0]), self.length_from[1]))


# ── the graph ────────────────────────────────────────────────────────────

def _doc(doc):
    from .document import as_document
    return as_document(doc)


def _single_ref(arg):
    from .document import iter_refs
    if not isinstance(arg, dict) or arg.get('kind') != 'ref':
        return None
    return next(iter_refs(arg), None)


def _is_point(doc, el_id) -> bool:
    el = doc.elements.get(el_id)
    return isinstance(el, dict) and el.get('type') == 'point'


def _pair_lines(doc, pair) -> list:
    """The ``line.by_points`` lines through the two points of ``pair``."""
    from .document import bound_producer
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        return []
    want = {pair[0], pair[1]}
    out = []
    for el_id, el in doc.elements.items():
        if not isinstance(el, dict) or el.get('type') != 'line':
            continue
        producer = bound_producer(doc, el_id)
        op = doc.operations.get(producer) if producer is not None else None
        if not isinstance(op, dict) or op.get('op') != 'line.by_points':
            continue
        args = op.get('args') or {}
        if {_single_ref(args.get('a')), _single_ref(args.get('b'))} == want:
            out.append(el_id)
    return out


def incident_points(doc, line_id) -> list:
    """The IDs of the points on the line or ray ``line_id`` by the graph of
    ``doc`` (sorted; the rules in the module docstring); ``[]`` for an
    element that is not a line or a ray."""
    from .document import bound_producer, iter_refs
    doc = _doc(doc)
    el = doc.elements.get(line_id)
    if not isinstance(el, dict) or el.get('type') not in ('line', 'ray'):
        return []
    found = set()
    producer = bound_producer(doc, line_id)
    if producer is not None:
        op = doc.operations[producer]
        name = op.get('op')
        args = op.get('args') or {}
        for slot in DEFINING_POINTS.get(name, ()):
            ref = _single_ref(args.get(slot))
            if ref is not None and _is_point(doc, ref):
                found.add(ref)
        siblings = SIBLING_POINTS.get(name, {}).get((el.get('producer') or {}).get('slot'), ())
        for out in op.get('outputs') or ():
            if out.get('slot') in siblings and _is_point(doc, out.get('elementId')):
                found.add(out['elementId'])
    for op_id, op in doc.operations.items():
        if not isinstance(op, dict) or op.get('op') not in ON_ARGUMENT:
            continue
        if not any(ref == line_id for arg in (op.get('args') or {}).values() for ref in iter_refs(arg)):
            continue
        for out in op.get('outputs') or ():
            el_id = out.get('elementId')
            if _is_point(doc, el_id) and bound_producer(doc, el_id) == op_id:
                found.add(el_id)
    for cond in doc.data.get('conditions') or ():
        statement = cond.get('statement') if isinstance(cond, dict) else None
        if not isinstance(statement, dict) or statement.get('kind') != 'on':
            continue
        point = (statement.get('point') or {}).get('ref')
        obj = statement.get('object') or {}
        on_it = obj.get('ref') == line_id or (el.get('type') == 'line' and line_id in _pair_lines(doc, obj.get('pair')))
        if on_it and _is_point(doc, point):
            found.add(point)
    return sorted(found)


def line_spec(doc, line_id) -> LineSpec | None:
    """The :class:`LineSpec` of a line or a ray of ``doc`` by document ID,
    ``None`` for another element."""
    from .document import bound_producer
    doc = _doc(doc)
    el = doc.elements.get(line_id)
    if not isinstance(el, dict) or el.get('type') not in ('line', 'ray'):
        return None
    producer = bound_producer(doc, line_id)
    name, args = None, ()
    origin = length_from = None
    if producer is not None:
        op = doc.operations[producer]
        name = op.get('op')
        by_slot = {}
        for slot, arg in sorted((op.get('args') or {}).items()):
            ref = _single_ref(arg)
            if ref is not None and isinstance(doc.elements.get(ref), dict):
                by_slot[slot] = (ref, doc.elements[ref].get('type'))
        args = tuple((slot, ref, type_) for slot, (ref, type_) in by_slot.items() if type_ == 'point')
        if el['type'] == 'ray' and _RAY_ORIGIN.get(name) in by_slot:
            origin = by_slot[_RAY_ORIGIN[name]][0]
        if name in LENGTH_FROM and LENGTH_FROM[name] in by_slot:
            length_from = by_slot[LENGTH_FROM[name]]
    return LineSpec(line_id, el['type'], name, args, tuple(incident_points(doc, line_id)), origin, length_from)


# ── the geometry ─────────────────────────────────────────────────────────

def _finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _range(value):
    """``(t0, t1)`` of a valid ``visible_range`` (sorted), else ``None``."""
    if not isinstance(value, (list, tuple)) or len(value) != 2 or not all(_finite(v) for v in value):
        return None
    t0, t1 = float(value[0]), float(value[1])
    return (t0, t1) if t0 <= t1 else (t1, t0)


def _overhang(value) -> float:
    return max(0.0, float(value)) if _finite(value) else DEFAULT_OVERHANG_PX


def _carrier(type_, value):
    """``(origin, unit direction)`` of a line or ray value, ``None`` when degenerate."""
    if type_ == 'ray':
        ox, oy = value['origin']
    else:
        ox, oy = value['p']
    dx, dy = value['dir']
    n = math.hypot(dx, dy)
    if not (n > 0 and math.isfinite(n)):
        return None
    return (float(ox), float(oy)), (dx / n, dy / n)


def _clip_range(o, d, lo, hi, frame):
    """``(s0, s1)`` of ``o + s·d`` for ``s`` in ``[lo, hi]`` inside the frame
    ``(left, bottom, right, top)`` (Liang–Barsky), ``None`` when outside or
    of zero length."""
    left, bottom, right, top = (float(v) for v in frame)
    for p, q in ((-d[0], o[0] - left), (d[0], right - o[0]), (-d[1], o[1] - bottom), (d[1], top - o[1])):
        if p == 0:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            lo = max(lo, r)
        else:
            hi = min(hi, r)
    if not lo < hi:
        return None
    return lo, hi


def clip_segment(segment, frame):
    """``(start, end, offset)`` of the part of ``segment`` ``((x0, y0), (x1,
    y1))`` inside ``frame`` ``(left, bottom, right, top)`` — ``offset`` is
    the distance from ``(x0, y0)`` to ``start`` (the phase of a dash
    pattern) — or ``None`` when nothing of it is inside."""
    (x0, y0), (x1, y1) = segment
    o, d = (float(x0), float(y0)), (float(x1) - float(x0), float(y1) - float(y0))
    if d == (0.0, 0.0):
        return None
    s = _clip_range(o, d, 0.0, 1.0, frame)
    if s is None:
        return None
    s0, s1 = s
    start = (o[0] + s0 * d[0], o[1] + s0 * d[1])
    end = (o[0] + s1 * d[0], o[1] + s1 * d[1])
    return start, end, s0 * math.hypot(*d)


def _ends(o, d, s0, s1):
    return ((o[0] + s0 * d[0], o[1] + s0 * d[1]), (o[0] + s1 * d[0], o[1] + s1 * d[1]))


def resolve_visible(key, *, spec, value, style, unit, frame=None, _depth=0):
    """The visible part ``((x0, y0), (x1, y1))`` of the line or ray ``key``
    before the frame clips it, or ``None`` — drawn to the frame (also an
    element without a :class:`LineSpec` or without a value).

    ``spec(key)`` → :class:`LineSpec` or ``None``; ``value(key, type)`` → the
    kernel value of an element (``None`` when undefined); ``style(key)`` → a
    mapping of :data:`STYLE_KEYS`; ``unit`` — style pixels per world unit
    (``ptUnitStyle``); ``frame`` — ``(left, bottom, right, top)``, the length
    of a base drawn to the frame (``None``: such a base gives the frame)."""
    s = spec(key)
    if s is None or _depth > _MAX_DEPTH:
        return None
    own = value(key, s.type)
    if own is None:
        return None
    keys = style(key) or {}
    rng = _range(keys.get('visible_range'))
    if rng is not None:
        return _explicit(s, own, rng, value)
    if keys.get('line_display') != 'incident':
        return None
    carrier = _carrier(s.type, own)
    if carrier is None:
        return None
    o, d = carrier
    h = _overhang(keys.get('line_overhang_px', DEFAULT_OVERHANG_PX)) / float(unit)
    params = []
    for p in s.points:
        v = value(p, 'point')
        if v is not None:
            params.append(((float(v['x']) - o[0]) * d[0] + (float(v['y']) - o[1]) * d[1], p))
    if s.type == 'ray':
        if not any(p != s.origin for _s, p in params):
            return None
        return _ends(o, d, 0.0, max(0.0, max(t for t, _p in params)) + h)
    if len(params) >= 2:
        ts = [t for t, _p in params]
        return _ends(o, d, min(ts) - h, max(ts) + h)
    if len(params) == 1 and s.length_from is not None:
        length = _base_length(s.length_from, spec=spec, value=value, style=style, unit=unit, frame=frame,
                              depth=_depth + 1)
        if length is None:
            return None
        t = params[0][0]
        return _ends(o, d, t - length / 2, t + length / 2)
    return None


def _explicit(s, own, rng, value):
    from .kernel import paths
    args = {}
    for slot, key, type_ in s.args:
        v = value(key, type_)
        if v is None:
            return None
        args[slot] = v
    try:
        f = paths.frame(s.type, own, s.producer, args)
    except (KeyError, ValueError, TypeError):
        f = paths.frame(s.type, own)
    p0, p1 = paths.point_at(f, rng[0]), paths.point_at(f, rng[1])
    return (float(p0['x']), float(p0['y'])), (float(p1['x']), float(p1['y']))


def _base_length(base, *, spec, value, style, unit, frame, depth):
    key, type_ = base
    v = value(key, type_)
    if v is None:
        return None
    if type_ == 'segment':
        (ax, ay), (bx, by) = v['a'], v['b']
        return math.hypot(bx - ax, by - ay)
    if type_ not in ('line', 'ray'):
        return None
    part = None
    if spec(key) is not None:
        part = resolve_visible(key, spec=spec, value=value, style=style, unit=unit, frame=frame, _depth=depth)
    if part is not None:
        (x0, y0), (x1, y1) = part
        return math.hypot(x1 - x0, y1 - y0)
    if frame is None:
        return None
    carrier = _carrier(type_, v)
    if carrier is None:
        return None
    o, d = carrier
    s = _clip_range(o, d, 0.0 if type_ == 'ray' else -math.inf, math.inf, frame)
    return None if s is None else s[1] - s[0]


# ── front ends ───────────────────────────────────────────────────────────

def _style_of(doc, style):
    if callable(style):
        return style
    if isinstance(style, dict):
        return lambda key: style.get(key) or {}

    def overrides(key):
        entry = (doc.data.get('appearance') or {}).get(key)
        out = entry.get('overrides') if isinstance(entry, dict) else None
        return out if isinstance(out, dict) else {}
    return overrides


def visible_segment(doc, line_id, style=None, *, inputs=None, evaluated=None, pt_unit_style=None, frame=None):
    """The visible part ``((x0, y0), (x1, y1))`` of the line or ray
    ``line_id`` of ``doc`` before the frame clips it, or ``None`` — drawn to
    the frame (``line_display: "frame"``, an undefined element, another
    type). Manim-free.

    ``style`` — the keys :data:`STYLE_KEYS` of an element: ``None`` reads
    ``appearance.<id>.overrides`` of the document; a mapping ``{id: {key:
    value}}``; or a callable ``id → mapping`` (``resolve_paint`` passes the
    resolved style of the renderer). The keys of the base of a
    ``line.parallel``/``line.perpendicular`` through one point are read the
    same way. ``evaluated`` — :func:`~animageo.native.kernel.evaluate.evaluate`
    of ``doc`` (default: evaluated with ``inputs``); ``pt_unit_style`` —
    style pixels per world unit (default: ``ptUnit`` of the source view,
    ``ptUnitStyle`` of ``resolve_paint`` without an export layout);
    ``frame`` — ``(left, bottom, right, top)`` of the frame in world units
    (default: ``viewDefaults.bounds``), read only for the length of a base
    drawn to the frame."""
    doc = _doc(doc)
    if evaluated is None:
        from .kernel.evaluate import evaluate
        evaluated = evaluate(doc, inputs=inputs)
    if pt_unit_style is None:
        from .rendering import source_view
        pt_unit_style = source_view(doc)['ptUnit']
    if frame is None and doc.bounds is not None:
        frame = tuple(float(v) for v in doc.bounds)
    specs = {}

    def spec(key):
        if key not in specs:
            specs[key] = line_spec(doc, key)
        return specs[key]

    def value(key, _type):
        record = evaluated.elements.get(key)
        if not isinstance(record, dict) or record.get('state') != 'defined':
            return None
        return record.get('value')

    return resolve_visible(line_id, spec=spec, value=value, style=_style_of(doc, style), unit=float(pt_unit_style),
                           frame=frame)


def classic_visible_part(scene, elem):
    """:func:`resolve_visible` of a classic element built from a document
    (``bridge.build_construction`` puts its :class:`LineSpec` with classic
    names on it as ``_native_line``): the values are those of the classic
    construction now (a moved point moves the part), the keys those of the
    style resolver, the frame ``scene._get_scene_bounds()``. ``None`` for an
    element without a spec (a GGB or DSL scene): it is drawn to the frame."""
    if getattr(elem, '_native_line', None) is None:
        return None
    from ..label_placement import _style_ptUnit
    from ..style.resolver import resolve
    from .kernel.bridge import from_classic

    geo = scene.geo

    def spec(name):
        e = geo.objectByName(name)
        return getattr(e, '_native_line', None)

    def value(name, type_):
        e = geo.objectByName(name)
        data = getattr(e, 'data', None)
        if data is None:
            return None
        try:
            return from_classic(type_, data)
        except (AttributeError, TypeError, ValueError):
            return None

    def style(name):
        e = elem if name == elem.name else geo.objectByName(name)
        return {key: resolve(scene, e, key, default=None) for key in STYLE_KEYS}

    if resolve(scene, elem, 'visible_range', default=None) is None and \
            resolve(scene, elem, 'line_display', default=None) != 'incident':
        return None             # drawn to the frame: nothing else is read
    try:
        frame = tuple(scene._get_scene_bounds())
    except Exception:           # a scene without a camera frame
        frame = None
    return resolve_visible(elem.name, spec=spec, value=value, style=style, unit=float(_style_ptUnit(scene.style)),
                           frame=frame)
