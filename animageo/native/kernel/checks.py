"""Mandatory checks of operations: three-valued result by ``tol.check``.

For every operation whose outputs are all defined, each check of its
registry record measures an error ``e >= 0`` (a length) from the resolved
inputs and the full op result; ``e <= check.passed * S`` is ``passed``,
``e >= check.failed * S`` is ``failed``, anything between (or a non-finite
``e``) is ``inconclusive``. Report keys are ``"<operationId>:<checkId>"``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..registry import registry
from .ops.angle import angle_size, convex_measure, unit_sides, wrap_angle
from .ops.intersect import carrier, distance_to_carrier
from .paths import distance_to_path
from .values import Undefined

__all__ = ['CHECKS', 'CheckReport', 'classify', 'register_check', 'run_checks']

CHECKS: dict = {}


def register_check(op: str, check_id: str):
    def register(fn):
        CHECKS[(op, check_id)] = fn
        return fn
    return register


def classify(error: float, tol) -> str:
    if not math.isfinite(error):
        return 'inconclusive'
    if error <= tol.check_passed:
        return 'passed'
    if error >= tol.check_failed:
        return 'failed'
    return 'inconclusive'


@dataclass
class CheckReport:
    """``results``: key → status; ``errors``: key → measured error;
    ``details``: key → reason or ``general_position`` trial summary."""

    results: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)
    # key → why a relation is ``inconclusive``/``unsupported``; trial counts
    details: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(status == 'passed' for status in self.results.values())

    def to_dict(self) -> dict:
        return dict(self.results)


def _xy(point: dict):
    return point['x'], point['y']


def _distance_to_line(x, y, line):
    px, py = line['p']
    dx, dy = line['dir']
    return abs((x - px) * dy - (y - py) * dx)


@register_check('segment.by_points', 'ends')
def _ends(args, result, tol):
    ax, ay = _xy(args['a'].value)
    bx, by = _xy(args['b'].value)
    seg = result['segment']
    return max(math.hypot(seg['a'][0] - ax, seg['a'][1] - ay),
               math.hypot(seg['b'][0] - bx, seg['b'][1] - by))


@register_check('line.by_points', 'through_a')
def _through_a(args, result, tol):
    return _distance_to_line(*_xy(args['a'].value), result['line'])


@register_check('line.by_points', 'through_b')
def _through_b(args, result, tol):
    return _distance_to_line(*_xy(args['b'].value), result['line'])


@register_check('circle.center_point', 'through_on_circle')
def _through_on_circle(args, result, tol):
    tx, ty = _xy(args['through'].value)
    circle = result['circle']
    cx, cy = circle['c']
    return abs(math.hypot(tx - cx, ty - cy) - circle['r'])


@register_check('point.midpoint', 'equidistant')
def _equidistant(args, result, tol):
    ax, ay = _xy(args['a'].value)
    bx, by = _xy(args['b'].value)
    mx, my = _xy(result['point'])
    return abs(math.hypot(ax - mx, ay - my) - math.hypot(mx - bx, my - by))


@register_check('point.midpoint', 'collinear')
def _collinear(args, result, tol):
    ax, ay = _xy(args['a'].value)
    bx, by = _xy(args['b'].value)
    mx, my = _xy(result['point'])
    length = math.hypot(bx - ax, by - ay)
    if length <= tol.decide_length:
        return math.hypot(mx - ax, my - ay)
    return abs((mx - ax) * (by - ay) - (my - ay) * (bx - ax)) / length


@register_check('ray.by_points', 'origin')
def _ray_origin(args, result, tol):
    ox, oy = _xy(args['origin'].value)
    ray = result['ray']
    return math.hypot(ray['origin'][0] - ox, ray['origin'][1] - oy)


@register_check('ray.by_points', 'through')
def _ray_through(args, result, tol):
    x, y = _xy(args['through'].value)
    ray = result['ray']
    return abs((x - ray['origin'][0]) * ray['dir'][1] - (y - ray['origin'][1]) * ray['dir'][0])


class _QuietContext:
    __slots__ = ('tol',)

    def __init__(self, tol):
        self.tol = tol

    def decide(self, name, value, tol):
        pass


@register_check('intersect.line_line', 'incident_both')
def _incident_both(args, result, tol):
    x, y = _xy(result['point'])
    ctx = _QuietContext(tol)
    error = 0.0
    for slot in ('first', 'second'):
        c = carrier(args[slot], ctx)
        if isinstance(c, Undefined):
            return math.inf
        error = max(error, distance_to_carrier(x, y, c))
    return error


def _distance_to_input(x, y, inp, ctx):
    """Distance from ``(x, y)`` to a circle or to the carrier line of a linear input."""
    if inp.type in ('circle', 'arc'):
        v = inp.value
        return abs(math.hypot(x - v['c'][0], y - v['c'][1]) - v['r'])
    c = carrier(inp, ctx)
    if isinstance(c, Undefined):
        return math.inf
    return distance_to_carrier(x, y, c)


def _on_both(points, first, second, tol):
    ctx = _QuietContext(tol)
    error = 0.0
    for point in points:
        x, y = _xy(point)
        error = max(error, _distance_to_input(x, y, first, ctx), _distance_to_input(x, y, second, ctx))
    return error


@register_check('intersect.line_circle', 'on_both')
def _line_circle_on_both(args, result, tol):
    return _on_both((result['first'], result['second']), args['line'], args['circle'], tol)


@register_check('intersect.circle_circle', 'on_both')
def _circle_circle_on_both(args, result, tol):
    return _on_both((result['first'], result['second']), args['first'], args['second'], tol)


@register_check('intersect.other_than', 'on_both')
def _other_than_on_both(args, result, tol):
    return _on_both((result['point'],), args['first'], args['second'], tol)


@register_check('point.on_path', 'on_path')
def _on_path(args, result, tol):
    x, y = _xy(result['point'])
    return distance_to_path(x, y, args['path'].type, args['path'].value)


@register_check('polygon.by_points', 'sides_match')
def _sides_match(args, result, tol):
    pts = [_xy(v.value) for v in args['vertices']]
    n = len(pts)
    error = 0.0
    for i in range(n):
        side = result[f'side.{i + 1}']
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        error = max(error,
                    math.hypot(side['a'][0] - ax, side['a'][1] - ay),
                    math.hypot(side['b'][0] - bx, side['b'][1] - by))
    return error


# ── registry 1.2 ──

def _line_of(result_line):
    return result_line['p'], result_line['dir']


def _base_carrier(args, tol):
    return carrier(args['base'], _QuietContext(tol))


@register_check('point.projection', 'on_carrier')
def _projection_on_carrier(args, result, tol):
    c = _base_carrier(args, tol)
    if isinstance(c, Undefined):
        return math.inf
    return distance_to_carrier(*_xy(result['foot']), c)


@register_check('point.projection', 'perpendicular')
def _projection_perpendicular(args, result, tol):
    c = _base_carrier(args, tol)
    if isinstance(c, Undefined):
        return math.inf
    px, py = _xy(args['point'].value)
    fx, fy = _xy(result['foot'])
    return abs((px - fx) * c.dx + (py - fy) * c.dy)


def _through_point(args, result, tol):
    return _distance_to_line(*_xy(args['point'].value), result['line'])


register_check('line.parallel', 'through_point')(_through_point)
register_check('line.perpendicular', 'through_point')(_through_point)


@register_check('line.parallel', 'parallel')
def _parallel(args, result, tol):
    c = _base_carrier(args, tol)
    if isinstance(c, Undefined):
        return math.inf
    dx, dy = result['line']['dir']
    return abs(dx * c.dy - dy * c.dx) * tol.scale


@register_check('line.perpendicular', 'perpendicular')
def _perpendicular(args, result, tol):
    c = _base_carrier(args, tol)
    if isinstance(c, Undefined):
        return math.inf
    dx, dy = result['line']['dir']
    return abs(dx * c.dx + dy * c.dy) * tol.scale


@register_check('line.perpendicular_bisector', 'through_midpoint')
def _bisector_midpoint(args, result, tol):
    ax, ay = _xy(args['a'].value)
    bx, by = _xy(args['b'].value)
    return _distance_to_line((ax + bx) / 2, (ay + by) / 2, result['line'])


@register_check('line.perpendicular_bisector', 'perpendicular')
def _bisector_perpendicular(args, result, tol):
    ax, ay = _xy(args['a'].value)
    bx, by = _xy(args['b'].value)
    dx, dy = result['line']['dir']
    return abs(dx * (bx - ax) + dy * (by - ay))


@register_check('line.angle_bisector', 'through_vertex')
def _angle_bisector_vertex(args, result, tol):
    return _distance_to_line(*_xy(args['vertex'].value), result['line'])


@register_check('line.angle_bisector', 'equal_angles')
def _angle_bisector_equal(args, result, tol):
    vx, vy = _xy(args['vertex'].value)
    dx, dy = result['line']['dir']
    cosines = []
    for slot in ('a', 'b'):
        x, y = _xy(args[slot].value)
        length = math.hypot(x - vx, y - vy)
        if length <= tol.decide_length:
            return math.inf
        cosines.append(((x - vx) * dx + (y - vy) * dy) / length)
    return abs(cosines[0] - cosines[1]) * tol.scale


@register_check('vector.by_points', 'ends')
def _vector_ends(args, result, tol):
    ax, ay = _xy(args['a'].value)
    bx, by = _xy(args['b'].value)
    vec = result['vector']
    return max(math.hypot(vec['a'][0] - ax, vec['a'][1] - ay),
               math.hypot(vec['b'][0] - bx, vec['b'][1] - by),
               abs(vec['length'] - math.hypot(bx - ax, by - ay)))


@register_check('circle.center_radius', 'matches')
def _center_radius_matches(args, result, tol):
    ox, oy = _xy(args['center'].value)
    circle = result['circle']
    return max(math.hypot(circle['c'][0] - ox, circle['c'][1] - oy),
               abs(circle['r'] - args['radius'].value['value']))


@register_check('circle.three_points', 'through_all')
def _three_points_through_all(args, result, tol):
    circle = result['circle']
    cx, cy = circle['c']
    error = 0.0
    for slot in ('a', 'b', 'c'):
        x, y = _xy(args[slot].value)
        error = max(error, abs(math.hypot(x - cx, y - cy) - circle['r']))
    if 'center' in result:
        ox, oy = _xy(result['center'])
        error = max(error, math.hypot(ox - cx, oy - cy))
    return error


# ── registry 1.3 ──

@register_check('angle.by_points', 'sides')
def _angle_sides(args, result, tol):
    vx, vy = _xy(args['vertex'].value)
    ang = result['angle']
    error = math.hypot(ang['vertex'][0] - vx, ang['vertex'][1] - vy)
    for slot, field_ in (('a', 'a0'), ('b', 'a1')):
        x, y = _xy(args[slot].value)
        if math.hypot(x - vx, y - vy) <= tol.decide_length:
            return math.inf
        theta = math.atan2(y - vy, x - vx)
        error = max(error, abs(wrap_angle(ang[field_] - theta)) * tol.scale)
    return error


@register_check('mark.equal_segments', 'equal')
def _equal_segments(args, result, tol):
    lengths = [inp.value['length'] for inp in args['segments']]
    return max(abs(length - lengths[0]) for length in lengths)


@register_check('mark.equal_angles', 'equal')
def _equal_angles(args, result, tol):
    measures = [convex_measure(inp.value['size']) for inp in args['angles']]
    return max(abs(m - measures[0]) for m in measures) * tol.scale


@register_check('mark.right_angle', 'right')
def _right_angle(args, result, tol):
    sides = unit_sides(args['a'].value, args['vertex'].value, args['b'].value, _QuietContext(tol))
    if isinstance(sides, Undefined):
        return math.inf
    return abs(convex_measure(angle_size(*sides)) - math.pi / 2) * tol.scale


@register_check('circle.incircle', 'tangent_sides')
def _incircle_tangent_sides(args, result, tol):
    circle = result['circle']
    cx, cy = circle['c']
    r = circle['r']
    error = 0.0
    for p_slot, q_slot, touch_slot in (('b', 'c', 'touch_a'), ('c', 'a', 'touch_b'), ('a', 'b', 'touch_c')):
        px, py = _xy(args[p_slot].value)
        qx, qy = _xy(args[q_slot].value)
        length = math.hypot(qx - px, qy - py)
        if length <= tol.decide_length:
            return math.inf
        tx, ty = _xy(result[touch_slot])

        def dist(x, y):
            return abs((x - px) * (qy - py) - (y - py) * (qx - px)) / length

        error = max(error, abs(dist(cx, cy) - r), dist(tx, ty), abs(math.hypot(tx - cx, ty - cy) - r))
    ox, oy = _xy(result['center'])
    return max(error, math.hypot(ox - cx, oy - cy))


# ---- registry 1.4 -------------------------------------------------------------


def _pt(value):
    """``(x, y)`` of an encoded point ``{x, y}`` or a pair ``[x, y]``."""
    if isinstance(value, dict):
        return value['x'], value['y']
    return value[0], value[1]


def _dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _number(inp):
    return inp.value['value']


@register_check('point.divide', 'ratio')
def _divide_ratio(args, result, tol):
    m = _number(args['m'])
    n = _number(args['n'])
    a = _pt(args['a'].value)
    b = _pt(args['b'].value)
    p = _pt(result['point'])
    ex = n * (p[0] - a[0]) - m * (b[0] - p[0])
    ey = n * (p[1] - a[1]) - m * (b[1] - p[1])
    return math.hypot(ex, ey) / (m + n)


@register_check('point.center', 'matches')
def _center_matches(args, result, tol):
    return _dist(_pt(result['center']), args['of'].value['c'])


@register_check('point.closest', 'on_path')
def _closest_on_path(args, result, tol):
    x, y = _pt(result['foot'])
    return distance_to_path(x, y, args['path'].type, args['path'].value)


@register_check('point.at_distance', 'distance')
def _at_distance(args, result, tol):
    a = _pt(args['a'].value)
    b = _pt(args['b'].value)
    p = _pt(result['point'])
    error = abs(_dist(p, a) - abs(_number(args['distance'])))
    length = _dist(a, b)
    off = abs((p[0] - a[0]) * (b[1] - a[1]) - (p[1] - a[1]) * (b[0] - a[0])) / length
    return max(error, off)


@register_check('polygon.vertex', 'matches')
def _vertex_matches(args, result, tol):
    of = args['of']
    vertices = [of.value['a'], of.value['b']] if of.type == 'segment' else of.value['vertices']
    return _dist(_pt(result['vertex']), vertices[int(round(args['k'])) - 1])


def _regular_error(result, center, radius):
    pts = result['polygon']['vertices']
    n = len(pts)
    side = _dist(pts[0], pts[1])
    error = 0.0
    for i in range(n):
        error = max(error, abs(_dist(pts[i], pts[(i + 1) % n]) - side), abs(_dist(pts[i], center) - radius))
        seg = result[f'side.{i + 1}']
        error = max(error, _dist(seg['a'], pts[i]), _dist(seg['b'], pts[(i + 1) % n]))
        error = max(error, _dist(_pt(result[f'vertex.{i + 1}']), pts[i]))
    return error


@register_check('polygon.regular', 'regular')
def _regular_regular(args, result, tol):
    pts = result['polygon']['vertices']
    n = len(pts)
    a = _pt(args['a'].value)
    b = _pt(args['b'].value)
    # the centre from the vertices (mean of a regular polygon's vertices)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    error = _regular_error(result, (cx, cy), _dist(a, (cx, cy)))
    return max(error, _dist(pts[0], a), _dist(pts[1], b))


@register_check('polygon.regular_center', 'regular')
def _regular_center_regular(args, result, tol):
    o = _pt(args['center'].value)
    a = _pt(args['a'].value)
    return max(_regular_error(result, o, _dist(a, o)), _dist(result['polygon']['vertices'][0], a))


@register_check('polygon.parallelogram', 'parallel_sides')
def _parallelogram_sides(args, result, tol):
    a, b, c, d = result['polygon']['vertices']
    ab = (b[0] - a[0], b[1] - a[1])
    dc = (c[0] - d[0], c[1] - d[1])
    bc = (c[0] - b[0], c[1] - b[1])
    ad = (d[0] - a[0], d[1] - a[1])
    scale = max(math.hypot(*ab), math.hypot(*bc))
    if scale <= tol.decide_length:
        return 0.0
    return max(abs(ab[0] * dc[1] - ab[1] * dc[0]), abs(bc[0] * ad[1] - bc[1] * ad[0])) / scale


@register_check('polygon.centroid', 'balance')
def _centroid_balance(args, result, tol):
    vs = args['polygon'].value['vertices']
    gx, gy = _pt(result['centroid'])
    x0, y0 = vs[0]
    a2 = 0.0
    ex = 0.0
    ey = 0.0
    for i in range(1, len(vs) - 1):
        ux, uy = vs[i][0] - x0, vs[i][1] - y0
        wx, wy = vs[i + 1][0] - x0, vs[i + 1][1] - y0
        cr = ux * wy - uy * wx
        a2 += cr
        ex += cr * (x0 + (ux + wx) / 3 - gx)
        ey += cr * (y0 + (uy + wy) / 3 - gy)
    return math.hypot(ex, ey) / abs(a2)


@register_check('polyline.by_points', 'vertices')
def _polyline_vertices(args, result, tol):
    vs = result['polyline']['vertices']
    return max(_dist(_pt(p.value), v) for p, v in zip(args['points'], vs))


@register_check('line.angle_bisectors_of_lines', 'equal_angles')
def _bisectors_equal(args, result, tol):
    ctx = _QuietContext(tol)
    c1 = carrier(args['first'], ctx)
    c2 = carrier(args['second'], ctx)
    i = result['internal']['dir']
    e = result['external']['dir']
    return max(abs((c1.dx - c2.dx) * i[0] + (c1.dy - c2.dy) * i[1]),
               abs((c1.dx + c2.dx) * e[0] + (c1.dy + c2.dy) * e[1])) * tol.scale


@register_check('line.external_bisector', 'through_vertex')
def _external_vertex(args, result, tol):
    return _distance_to_line(*_xy(args['vertex'].value), result['line'])


@register_check('line.external_bisector', 'equal_angles')
def _external_equal(args, result, tol):
    vx, vy = _xy(args['vertex'].value)
    dx, dy = result['line']['dir']
    total = 0.0
    for slot in ('a', 'b'):
        x, y = _xy(args[slot].value)
        length = math.hypot(x - vx, y - vy)
        if length <= tol.decide_length:
            return math.inf
        total += ((x - vx) * dx + (y - vy) * dy) / length
    return abs(total) * tol.scale


@register_check('ray.at_angle', 'angle')
def _ray_at_angle(args, result, tol):
    v = _pt(args['vertex'].value)
    a = _pt(args['a'].value)
    p = _pt(result['point'])
    d = math.atan2(p[1] - v[1], p[0] - v[0]) - math.atan2(a[1] - v[1], a[0] - v[0]) - _number(args['size'])
    return max(abs(wrap_angle(d)) * tol.scale, abs(_dist(p, v) - _dist(a, v)))


@register_check('ray.by_vector', 'parallel')
def _ray_by_vector(args, result, tol):
    vec = args['vector'].value
    vx = vec['b'][0] - vec['a'][0]
    vy = vec['b'][1] - vec['a'][1]
    dx, dy = result['ray']['dir']
    return abs(dx * vy - dy * vx) / math.hypot(vx, vy) * tol.scale


def _tangent_error(line, circle):
    return abs(_distance_to_line(circle['c'][0], circle['c'][1], line) - circle['r'])


@register_check('line.tangents_from_point', 'tangent')
def _tangents_tangent(args, result, tol):
    circle = args['circle'].value
    error = 0.0
    for i in (1, 2):
        error = max(error, _tangent_error(result[f'tangent.{i}'], circle),
                    abs(_dist(_pt(result[f'touch.{i}']), circle['c']) - circle['r']))
    return error


@register_check('line.tangents_from_point', 'through_point')
def _tangents_through(args, result, tol):
    x, y = _xy(args['point'].value)
    return max(_distance_to_line(x, y, result['tangent.1']), _distance_to_line(x, y, result['tangent.2']))


@register_check('line.tangent_at', 'tangent')
def _tangent_at(args, result, tol):
    x, y = _xy(args['point'].value)
    return max(_tangent_error(result['line'], args['circle'].value), _distance_to_line(x, y, result['line']))


@register_check('segment.from_point_length', 'length')
def _from_point_length(args, result, tol):
    a = _pt(args['start'].value)
    seg = result['segment']
    length = max(_number(args['length']), 0.0)
    return max(abs(_dist(_pt(result['end']), a) - length), _dist(seg['a'], a))


@register_check('segment.midline', 'midpoints')
def _midline(args, result, tol):
    s1 = args['first'].value
    s2 = args['second'].value
    m1 = ((s1['a'][0] + s1['b'][0]) / 2, (s1['a'][1] + s1['b'][1]) / 2)
    m2 = ((s2['a'][0] + s2['b'][0]) / 2, (s2['a'][1] + s2['b'][1]) / 2)
    seg = result['segment']
    return max(_dist(seg['a'], m1), _dist(seg['b'], m2), _dist(_pt(result['mid.1']), m1),
               _dist(_pt(result['mid.2']), m2))


@register_check('circle.diameter', 'through_ends')
def _diameter_ends(args, result, tol):
    circle = result['circle']
    return max(abs(_dist(_pt(args[s].value), circle['c']) - circle['r']) for s in ('a', 'b'))


@register_check('circle.center_segment', 'matches')
def _center_segment(args, result, tol):
    circle = result['circle']
    return max(_dist(circle['c'], _pt(args['center'].value)), abs(circle['r'] - args['radius'].value['length']))


def _line_distance(p, a, b):
    length = _dist(a, b)
    return abs((p[0] - a[0]) * (b[1] - a[1]) - (p[1] - a[1]) * (b[0] - a[0])) / length


@register_check('circle.excircle', 'tangent_sides')
def _excircle_sides(args, result, tol):
    a = _pt(args['a'].value)
    b = _pt(args['b'].value)
    c = _pt(args['c'].value)
    circle = result['circle']
    o = circle['c']
    r = circle['r']
    t = _pt(result['touch'])
    error = max(abs(_line_distance(o, p, q) - r) for p, q in ((b, c), (c, a), (a, b)))
    return max(error, _line_distance(t, b, c), abs(_dist(t, o) - r), _dist(_pt(result['center']), o))


def _arc_ends(value):
    c = value['c']
    r = value['r']
    return ((c[0] + r * math.cos(value['a0']), c[1] + r * math.sin(value['a0'])),
            (c[0] + r * math.cos(value['a1']), c[1] + r * math.sin(value['a1'])))


def _ray_distance(p, origin, through):
    """Distance from ``p`` to the ray from ``origin`` through ``through``."""
    dx = through[0] - origin[0]
    dy = through[1] - origin[1]
    length = math.hypot(dx, dy)
    s = ((p[0] - origin[0]) * dx + (p[1] - origin[1]) * dy) / length
    if s < 0:
        return _dist(p, origin)
    return abs((p[0] - origin[0]) * dy - (p[1] - origin[1]) * dx) / length


def _center_two_points_ends(args, value):
    o = _pt(args['center'].value)
    start, end = _arc_ends(value)
    return max(_dist(start, _pt(args['a'].value)), _ray_distance(end, o, _pt(args['b'].value)),
               _dist(value['c'], o))


def _on_circle_ends(args, value):
    circle = args['circle'].value
    o = circle['c']
    start, end = _arc_ends(value)
    return max(_ray_distance(start, o, _pt(args['a'].value)), _ray_distance(end, o, _pt(args['b'].value)),
               _dist(value['c'], o), abs(value['r'] - circle['r']))


def _through_three(args, value):
    return max(paths_distance(_pt(args[s].value), 'arc', value) for s in ('a', 'b', 'c'))


def paths_distance(p, type_, value):
    return distance_to_path(p[0], p[1], type_, value)


@register_check('arc.center_two_points', 'ends')
def _arc_ctp(args, result, tol):
    return _center_two_points_ends(args, result['arc'])


@register_check('sector.center_two_points', 'ends')
def _sector_ctp(args, result, tol):
    return _center_two_points_ends(args, result['sector'])


@register_check('arc.on_circle', 'ends')
def _arc_on_circle(args, result, tol):
    return _on_circle_ends(args, result['arc'])


@register_check('sector.on_circle', 'ends')
def _sector_on_circle(args, result, tol):
    return _on_circle_ends(args, result['sector'])


@register_check('arc.three_points', 'through_all')
def _arc_three(args, result, tol):
    return max(_through_three(args, result['arc']), _dist(_pt(result['center']), result['arc']['c']))


@register_check('sector.three_points', 'through_all')
def _sector_three(args, result, tol):
    return max(_through_three(args, result['sector']), _dist(_pt(result['center']), result['sector']['c']))


@register_check('arc.semicircle', 'ends')
def _semicircle(args, result, tol):
    a = _pt(args['a'].value)
    b = _pt(args['b'].value)
    value = result['arc']
    start, end = _arc_ends(value)
    return max(_dist(end, a), _dist(start, b), abs(value['r'] - _dist(a, b) / 2))


@register_check('sector.from_angle', 'ends')
def _sector_from_angle(args, result, tol):
    value = result['sector']
    o = _pt(args['center'].value)
    a = _pt(args['a'].value)
    alpha = _number(args['size'])
    sweep = min(abs(alpha), 2 * math.pi)
    start, end = _arc_ends(value)
    on = end if alpha < 0 else start
    return max(_dist(on, a), abs(value['r'] - _dist(a, o)), abs((value['a1'] - value['a0']) - sweep) * tol.scale)


@register_check('intersect.line_sector', 'incident_both')
def _line_sector(args, result, tol):
    ctx = _QuietContext(tol)
    error = 0.0
    for slot in ('arc.1', 'arc.2', 'side.1', 'side.2'):
        x, y = _pt(result[slot])
        error = max(error, _distance_to_input(x, y, args['line'], ctx),
                    distance_to_path(x, y, 'sector', args['sector'].value))
    return error


def run_checks(evaluated, keys=None) -> CheckReport:
    """Run the registry checks over an :class:`~.evaluate.Evaluated` result.

    ``keys`` limits the report to ``"<operationId>:<checkId>"`` keys or bare
    check IDs (every operation with that check).
    """
    reg = registry()
    wanted = set(keys) if keys is not None else None
    report = CheckReport()
    tol = evaluated.tolerances
    for op_id in sorted(evaluated.computed):
        op_name, args, result = evaluated.computed[op_id]
        for item in reg.get(op_name).get('checks', []):
            key = f"{op_id}:{item['id']}"
            if wanted is not None and key not in wanted and item['id'] not in wanted:
                continue
            fn = CHECKS[(op_name, item['id'])]
            error = float(fn(args, result, tol))
            report.errors[key] = error
            report.results[key] = classify(error, tol)
    return report
