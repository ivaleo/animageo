"""The marker of an angle: its display mode, its extent and its fit to the
sides (manim-free).

The marker is the arcs of an angle or the square of a right angle. Its
*desired* size comes from the style (``arc_size_px``, ``tick_count``,
``arc_shift_px``, ``right_angle_size_px``, ``overlay.angle_radius``);
:func:`marker_extent` gives it as the renderer draws it, in style pixels.

``rendering.angle_marker_fit`` (off by default) bounds the drawn extent by
the sides the angle actually has in the drawing::

    e_max = side_fraction · L · ptUnit_style          (style px)
    arcs:    e' = min(e, e_max), every arc moves in by e − e' (the spacing stays)
    square:  s' = min(s, e_max)
    hidden:  e' < e and the innermost arc (the square's side) < hide_below_px

``L`` is the shorter finite support of the two sides in world units (see
:func:`side_support`); ``ptUnit_style`` turns it into the pixels of the
style, the unit of ``arc_size_px``. It equals the export ``ptUnit`` when
decorations have a fixed output size (a document's own view,
``content.decoration_scale_source: 'output'``): zooming in then lengthens
the sides in pixels and the desired radius comes back. The fit is stateless
and never writes the desired values back: an angle's label stands at the
effective extent ``e'`` (also while the marker is hidden).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

__all__ = ['RIGHT_ANGLE_ATOL', 'RIGHT_ANGLE_RTOL', 'FIT_KEY', 'FIT_DEFAULTS', 'FitSettings',
           'MarkerExtent', 'MarkerFit', 'is_right_angle', 'shown_angle', 'fit_settings',
           'fit_extent', 'side_support', 'marker_extent', 'marker_fit', 'max_desired_px']

# numpy.isclose(shown, π/2) of the renderer: |shown − π/2| ≤ atol + rtol·π/2
RIGHT_ANGLE_ATOL = 1e-8
RIGHT_ANGLE_RTOL = 1e-5

FIT_KEY = 'angle_marker_fit'
FIT_DEFAULTS = {'enabled': False, 'side_fraction': 0.5, 'hide_below_px': 3.0}


def is_right_angle(shown: float) -> bool:
    """Whether an angle drawn with ``shown`` radians gets the square in the
    automatic mode (``right_angle_marker`` ``null``)."""
    return abs(float(shown) - math.pi / 2) <= RIGHT_ANGLE_ATOL + RIGHT_ANGLE_RTOL * math.pi / 2


def shown_angle(size: float, angle_range: str) -> float:
    """The angle as drawn: ``minor`` shows the non-reflex one, ``reflex`` the reflex one."""
    size = float(size)
    if (angle_range == 'minor' and size > math.pi) or (angle_range == 'reflex' and size < math.pi):
        return 2 * math.pi - size
    return size


# ── settings ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FitSettings:
    side_fraction: float = FIT_DEFAULTS['side_fraction']
    hide_below_px: float = FIT_DEFAULTS['hide_below_px']


def _rendering_value(scene, key):
    for holder in (getattr(scene, 'style_config', None), getattr(scene, 'style', None)):
        rendering = getattr(holder, 'rendering', None)
        if isinstance(rendering, dict) and key in rendering:
            return rendering[key]
    return None


def _positive(value, default):
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) and number >= 0 else default


def fit_settings(scene) -> Optional[FitSettings]:
    """:class:`FitSettings` of ``rendering.angle_marker_fit``, ``None`` when it is off.

    ``true`` turns it on with the defaults; an object turns it on with
    ``enabled: true`` and takes ``side_fraction`` (> 0) and ``hide_below_px``
    (≥ 0), a bad value falling back to the default."""
    raw = _rendering_value(scene, FIT_KEY)
    if raw is True:
        return FitSettings()
    if not isinstance(raw, dict) or raw.get('enabled', FIT_DEFAULTS['enabled']) is not True:
        return None
    fraction = _positive(raw.get('side_fraction'), FIT_DEFAULTS['side_fraction'])
    if fraction == 0:
        fraction = FIT_DEFAULTS['side_fraction']
    return FitSettings(side_fraction=fraction,
                       hide_below_px=_positive(raw.get('hide_below_px'), FIT_DEFAULTS['hide_below_px']))


def _style_unit(scene) -> float:
    export = getattr(getattr(scene, 'style', None), 'export', None) or {}
    return float(export.get('ptUnit_style', export.get('ptUnit', 1)) or 1)


# ── the extent as drawn ──────────────────────────────────────────────────

@dataclass(frozen=True)
class MarkerExtent:
    """The marker of ``_render_angle`` in style pixels.

    ``outer_px`` — how far it reaches along the sides (the outer arc, the
    side of the square); ``inner_px`` — the innermost arc (the side of the
    square); ``label_px`` — the radius of the label before
    ``label_radial_offset_px``; ``right_size_px`` — the drawn
    ``right_angle_size_px`` (the diagonal of the square), ``None`` for arcs."""
    right: bool
    base_px: float
    count: int
    shift_px: float
    outer_px: float
    inner_px: float
    label_px: float
    right_size_px: Optional[float] = None


def marker_extent(scene, elem) -> MarkerExtent:
    """The marker of the angle ``elem`` as ``AnimaGeoScene._render_angle`` draws it."""
    from .label_placement import compute_effective_arc_size_px
    from .style.resolver import resolve

    data = elem.data
    angle_range = resolve(scene, elem, 'angle_range', default='minor') or 'minor'
    arc_size = resolve(scene, elem, 'arc_size_px', default=17.0)
    base = float(compute_effective_arc_size_px(elem, data, scene, base_px=arc_size, angle_range=angle_range,
                                               auto_radius=resolve(scene, elem, 'auto_radius', default=True)))
    count = int(resolve(scene, elem, 'tick_count', default=0) or 0)
    shift = float(resolve(scene, elem, 'arc_shift_px', default=0.0) or 0.0)
    explicit = bool(getattr(elem, '_native_mark_explicit', False))
    right = resolve(scene, elem, 'right_angle_marker', default=None)
    if explicit:
        right = False
    if right is None:
        right = is_right_angle(shown_angle(data.size, angle_range))
    if right:
        overlay = getattr(getattr(scene, 'style_config', None), 'overlay', None)
        auto = getattr(overlay, 'angle_radius', None) or {}
        if auto.get('enabled', False) and auto.get('apply_to_right', False):
            size = base
        else:
            size = float(resolve(scene, elem, 'right_angle_size_px', default=arc_size))
        side = size / math.sqrt(2)
        return MarkerExtent(True, base, count, shift, side, side, side, size)
    unit = _style_unit(scene)
    outer = base + ((max(1, count) if explicit else count) - 1) * shift
    if outer / unit < 0.001:            # the renderer's guard
        outer = 0.2 * unit
    inner = outer - (max(count, 1) - 1) * shift
    return MarkerExtent(False, base, count, shift, outer, inner, outer)


# ── the fit ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MarkerFit:
    """``support`` — ``(L1, L2)`` in world units, ``None`` for a side
    without a bound; ``limit_px`` — ``e_max`` (``None``: no bound);
    ``delta_px`` — how far every radius moves in; ``clamped``; ``hidden``."""
    support: tuple
    limit_px: Optional[float]
    delta_px: float
    clamped: bool
    hidden: bool


def fit_extent(outer_px: float, inner_px: float, limit_px: Optional[float], hide_below_px: float) -> tuple:
    """``(delta_px, clamped, hidden)`` of a marker reaching ``outer_px``
    with its innermost line at ``inner_px`` under the bound ``limit_px``."""
    if limit_px is None or not outer_px > limit_px:
        return 0.0, False, False
    delta = float(outer_px) - max(float(limit_px), 0.0)
    return delta, True, float(inner_px) - delta < float(hide_below_px)


def marker_fit(scene, elem, extent: Optional[MarkerExtent] = None) -> Optional[MarkerFit]:
    """:class:`MarkerFit` of the angle ``elem``, ``None`` when the fit is off."""
    settings = fit_settings(scene)
    if settings is None:
        return None
    extent = extent or marker_extent(scene, elem)
    support = side_support(scene, elem)
    finite = [length for length in support if length is not None]
    limit = settings.side_fraction * min(finite) * _style_unit(scene) if finite else None
    delta, clamped, hidden = fit_extent(extent.outer_px, extent.inner_px, limit, settings.hide_below_px)
    return MarkerFit(support, limit, delta, clamped, hidden)


def max_desired_px(scene, elem) -> Optional[dict]:
    """The largest desired sizes the fit leaves as they are, for dragging a
    handle: ``{'limitPx', 'arcSizePx', 'rightAngleSizePx'}`` (style px), or
    ``None`` when the fit is off or the sides do not bound the marker.

    ``arcSizePx`` bounds the base radius of the arcs (with
    ``overlay.angle_radius`` — the scaled one), the outer arc being
    ``(count − 1) · arc_shift_px`` further out; ``rightAngleSizePx`` bounds
    ``right_angle_size_px``."""
    extent = marker_extent(scene, elem)
    fit = marker_fit(scene, elem, extent)
    if fit is None or fit.limit_px is None:
        return None
    reach = 0.0 if extent.right else extent.outer_px - extent.base_px
    return {'limitPx': fit.limit_px, 'arcSizePx': fit.limit_px - reach,
            'rightAngleSizePx': math.sqrt(2) * fit.limit_px}


# ── the supports of the sides ────────────────────────────────────────────
#
# Incidence is read from the construction graph — arguments and producing
# operations — never from coordinates. A side from the vertex V towards its
# defining point P is unbounded (a) when a visible line through V and P, or
# a visible ray from V through P, is drawn; otherwise it is |VP| — (b) a
# segment or a polygon side VP, (c) any other case. (d) An angle between
# lines or vectors has unit sides and no bound.

_NATIVE_THROUGH = {
    'line.by_points': ('a', 'b'), 'line.parallel': ('point',), 'line.perpendicular': ('point',),
    'line.tangent_at': ('point',), 'line.tangents_from_point': ('point',),
    'line.angle_bisector': ('vertex',), 'line.external_bisector': ('vertex',),
    'ray.by_points': ('origin', 'through'), 'ray.by_vector': ('origin',), 'ray.at_angle': ('vertex',),
}
_NATIVE_ORIGIN = {'ray.by_points': 'origin', 'ray.by_vector': 'origin', 'ray.at_angle': 'vertex'}
_NATIVE_ON_PATH = {'point.on_path': 'path', 'point.closest': 'path', 'point.projection': 'base'}
_NATIVE_UNBOUNDED = ('angle.between_lines', 'angle.between_vectors')
_CLASSIC_FIRST_POINT = ('orthogonal_line', 'perpendicular_line', 'tangent')


def _name(obj):
    return obj if isinstance(obj, str) else getattr(obj, 'name', None)


def _native_slots(cmd) -> tuple:
    """``({input slot: [names]}, {output slot: name})`` of a native command."""
    runner = getattr(cmd, '_runner', None)
    layout = getattr(runner, 'layout', None) or ()
    names = [_name(x) for x in cmd.inputs]
    slots, i = {}, 0
    for slot, _is_list, types in layout:
        slots[slot] = names[i:i + len(types)]
        i += len(types)
    outs = dict(zip(getattr(runner, 'out_slots', None) or (), (_name(o) for o in cmd.outputs)))
    return slots, outs


def _is_native(cmd) -> bool:
    return hasattr(cmd, 'operation_id')


class _Graph:
    """Producers and the points each path carries, of one construction."""

    def __init__(self, construction):
        from .geo.lib_commands import strCommand
        self.construction = construction
        self.producer = {}
        self.on_path = {}
        for cmd in getattr(construction, 'commands', ()):
            outs = [_name(o) for o in cmd.outputs]
            for out in outs:
                self.producer.setdefault(out, cmd)
            if _is_native(cmd):
                slots, out_slots = _native_slots(cmd)
                if cmd.name.startswith('intersect.'):
                    paths = [n for slot, names in slots.items() if slot not in ('near', 'known') for n in names]
                elif cmd.name in _NATIVE_ON_PATH:
                    paths = slots.get(_NATIVE_ON_PATH[cmd.name], [])
                else:
                    continue
                for path in paths:
                    self.on_path.setdefault(path, set()).update(out_slots.values())
                continue
            name = strCommand(cmd.name) if cmd.name else ''
            if name == 'intersect':
                paths = [_name(x) for x in cmd.inputs]
            elif name in ('point', 'closest_point') and cmd.inputs:
                paths = [_name(cmd.inputs[0])]
            else:
                continue
            for path in paths:
                if path is not None:
                    self.on_path.setdefault(path, set()).update(o for o in outs if o is not None)

    def _is_point(self, name) -> bool:
        from .geo.lib_elements import Point
        elem = self.construction.element(name) if isinstance(name, str) else None
        return elem is not None and isinstance(elem.data, Point)

    def through(self, line) -> tuple:
        """``(points the producer puts on ``line``, the origin of a ray or None)``."""
        cmd = self.producer.get(line)
        if cmd is None:
            return set(), None
        if _is_native(cmd):
            slots, outs = _native_slots(cmd)
            points = {n for slot in _NATIVE_THROUGH.get(cmd.name, ()) for n in slots.get(slot, ())}
            if cmd.name == 'ray.at_angle' and outs.get('point'):
                points.add(outs['point'])
            if cmd.name == 'line.tangents_from_point':
                slot = next((s for s, n in outs.items() if n == line), '')
                touch = outs.get(slot.replace('tangent.', 'touch.')) if slot.startswith('tangent.') else None
                if touch:
                    points.add(touch)
            origin = slots.get(_NATIVE_ORIGIN.get(cmd.name, ''), [None])[0] if cmd.name in _NATIVE_ORIGIN else None
            return points, origin
        from .geo.lib_commands import strCommand
        name = strCommand(cmd.name) if cmd.name else ''
        inputs = [_name(x) for x in cmd.inputs]
        points = [n for n in inputs if self._is_point(n)]
        if name == 'line':
            through = points if len(points) == len(inputs) else inputs[:1] if inputs and inputs[0] in points else []
            return set(through), None
        if name == 'ray' and inputs and inputs[0] in points:
            return set(inputs[:2]) & set(points), inputs[0]
        if name in _CLASSIC_FIRST_POINT and inputs and inputs[0] in points:
            return {inputs[0]}, None
        return set(), None

    def unbounded(self, scene, vertex, point) -> bool:
        """Rule (a): a visible line through ``vertex`` and ``point`` or a
        visible ray from ``vertex`` through ``point``."""
        from .geo import construction as geo
        from .geo.lib_elements import Line, Ray, Segment
        from .style.resolver import resolve
        if vertex is None or point is None:
            return False
        for elem in self.construction.elements:
            data = elem.data
            if isinstance(data, Segment) or not isinstance(data, Line) or not geo.is_drawn(data):
                continue
            if not resolve(scene, elem, 'visible', default=getattr(elem, 'visible', True)):
                continue
            through, origin = self.through(elem.name)
            on = through | self.on_path.get(elem.name, set())
            if point not in on:
                continue
            if isinstance(data, Ray):
                if origin == vertex:
                    return True
            elif vertex in on:
                return True
        return False


def _coords(construction, name):
    from .geo.lib_elements import Point
    elem = construction.element(name) if isinstance(name, str) else None
    if elem is None or not isinstance(elem.data, Point):
        return None
    return float(elem.data.coords[0]), float(elem.data.coords[1])


def _match(side, vertex, candidates) -> tuple:
    """The candidate ``(name, (x, y))`` lying along the unit-sided ``side`` from ``vertex``."""
    sx, sy = float(side[0]), float(side[1])
    norm = math.hypot(sx, sy)
    best, best_cos = (None, None), 1 - 1e-9
    for name, xy in candidates:
        if xy is None:
            continue
        dx, dy = xy[0] - vertex[0], xy[1] - vertex[1]
        length = math.hypot(dx, dy)
        if norm == 0 or length == 0:
            continue
        cos = (dx * sx + dy * sy) / (length * norm)
        if cos > best_cos:
            best, best_cos = (name, xy), cos
    return best


def _defining(graph, elem) -> Optional[tuple]:
    """``(vertex name, [(point name, xy) for side 1 and side 2])`` or
    ``None`` for an angle whose sides have no bound (d); a name is ``None``
    where the point is no element."""
    data = elem.data
    vertex_xy = (float(data.vertex[0]), float(data.vertex[1]))
    cmd = graph.producer.get(elem.name)
    construction = graph.construction
    if cmd is not None and _is_native(cmd):
        slots, outs = _native_slots(cmd)
        if cmd.name in _NATIVE_UNBOUNDED:
            return None
        if cmd.name in ('angle.by_points', 'mark.right_angle'):
            a, v, b = (slots.get(s, [None])[0] for s in ('a', 'vertex', 'b'))
            return v, [(a, _coords(construction, a)), (b, _coords(construction, b))]
        candidates, vertex = [], None
        if cmd.name == 'angle.by_size':
            vertex = slots.get('vertex', [None])[0]
            candidates = [(n, _coords(construction, n)) for n in (slots.get('a', [None])[0], outs.get('point'))]
        elif cmd.name == 'measure.polygon_angles':
            slot = next((s for s, n in outs.items() if n == elem.name), '')
            k = int(slot.split('.')[1]) - 1 if slot.startswith('angle.') else -1
            polygon = slots.get('polygon', [None])[0]
            pcmd = graph.producer.get(polygon)
            names = _native_slots(pcmd)[0].get('vertices', []) if pcmd is not None and \
                pcmd.name == 'polygon.by_points' else []
            if names and 0 <= k < len(names):
                vertex = names[k]
                candidates = [(n, _coords(construction, n)) for n in (names[k - 1], names[(k + 1) % len(names)])]
            else:
                pelem = construction.element(polygon) if polygon else None
                vs = getattr(getattr(pelem, 'data', None), 'vertices', None)
                if vs is not None and 0 <= k < len(vs):
                    candidates = [(None, (float(vs[i][0]), float(vs[i][1]))) for i in (k - 1, (k + 1) % len(vs))]
        else:
            return None
        return vertex, [_match(data.side1, vertex_xy, candidates), _match(data.side2, vertex_xy, candidates)]
    if cmd is not None and len(cmd.inputs) == 3 and (cmd.name or '').lower() == 'angle':
        names = [_name(x) for x in cmd.inputs]
        coords = [_coords(construction, n) for n in names]
        if all(c is not None for c in coords):
            return names[1], [(names[0], coords[0]), (names[2], coords[2])]
    # (c) without a producer the graph reads: the sides as they are
    return None, [(None, (vertex_xy[0] + float(s[0]), vertex_xy[1] + float(s[1]))) for s in (data.side1, data.side2)]


def side_support(scene, elem) -> tuple:
    """``(L1, L2)``: the finite support of each side of the angle ``elem``
    in world units, ``None`` where the side has no bound."""
    construction = getattr(scene, 'geo', None)
    graph = _Graph(construction)
    defining = _defining(graph, elem)
    if defining is None:
        return None, None
    vertex, sides = defining
    data = elem.data
    vx, vy = float(data.vertex[0]), float(data.vertex[1])
    out = []
    for name, xy in sides:
        if xy is None:
            out.append(None)
        elif graph.unbounded(scene, vertex, name):
            out.append(None)
        else:
            out.append(math.hypot(xy[0] - vx, xy[1] - vy))
    return tuple(out)
