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
from .ops.intersect import carrier, distance_to_carrier
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
    """``results``: key → status; ``errors``: key → measured error."""

    results: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)

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
    if inp.type == 'circle':
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
