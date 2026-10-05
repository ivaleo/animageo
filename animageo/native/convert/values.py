"""Values of the import report and ``value_check`` (plan L5 §3.6).

Report form of a value (``ggb_value``, ``native_value``): ``{"kind": k,
"value": v}`` with

- ``point`` — ``[x, y]``; ``number`` — a float; ``angle`` — radians;
- ``line`` — normalized coefficients ``[a, b, c]`` of ``a·x + b·y + c = 0``
  (``a² + b² = 1``, the first non-zero of ``a``, ``b`` positive) — also the
  carrier of a segment or a ray in the XML;
- ``segment``, ``vector`` — ``[[x1, y1], [x2, y2]]``; ``ray`` —
  ``{"origin", "direction"}`` (unit); ``circle`` — ``{"center", "radius"}``;
  ``conic`` — the six GGB matrix entries; ``arc`` — ``{"center", "radius",
  "a0", "a1"}``; ``polygon`` — the vertices;
- ``text`` — ``{"kind": "text", "text", "anchor": [x, y] | null}``.

:func:`compare` measures a native value against an expected one by its
kind (distance of points, coefficients of lines, centre and radius, vertices,
the difference of numbers, angles on the circle) and returns ``(status,
delta)``: ``passed`` within ``tol``, ``failed`` otherwise, ``not_checked``
when the kinds do not meet. ``tol.import = 1e-6·S`` (``S`` — scene scale,
spike C2: GeoGebra writes doubles in full, the classic values agree to
≤ 1e-12·S).
"""
from __future__ import annotations

import math

__all__ = ['TOL_IMPORT', 'compare', 'native_report_value', 'line_coefficients', 'circle_from_matrix',
           'classic_report_value']

TOL_IMPORT = 1e-6          # · S


def _f(v) -> float:
    return float(v)


def line_coefficients(a: float, b: float, c: float):
    """Normalized ``[a, b, c]`` (``None`` for a degenerate line)."""
    n = math.hypot(a, b)
    if not (math.isfinite(n) and n > 0 and math.isfinite(c)):
        return None
    a, b, c = a / n, b / n, c / n
    if a < -1e-15 or (abs(a) <= 1e-15 and b < 0):
        a, b, c = -a, -b, -c
    return [a, b, c]


def _line_through(p, d):
    """Coefficients of the line through ``p`` along ``d``."""
    a, b = -float(d[1]), float(d[0])
    return line_coefficients(a, b, -(a * float(p[0]) + b * float(p[1])))


def circle_from_matrix(m):
    """``{"center", "radius"}`` of a GGB conic matrix ``A0…A5`` that is a
    circle (``A0 = A1``, ``A3 = 0``), else ``None``."""
    a0, a1, a2, a3, a4, a5 = (float(v) for v in m)
    if a0 == 0 or abs(a0 - a1) > 1e-9 * max(abs(a0), abs(a1)) or abs(a3) > 1e-9 * abs(a0):
        return None
    cx, cy = -a4 / a0, -a5 / a0
    r2 = cx * cx + cy * cy - a2 / a0
    if not (r2 >= 0 and math.isfinite(r2)):
        return None
    return {'center': [cx, cy], 'radius': math.sqrt(r2)}


def native_report_value(type_: str, value):
    """A kernel value of an element of ``type_`` in report form (``None`` when
    the kind has no report form)."""
    if value is None:
        return None
    try:
        if type_ == 'point':
            return {'kind': 'point', 'value': [_f(value['x']), _f(value['y'])]}
        if type_ in ('segment', 'vector'):
            return {'kind': type_, 'value': [[_f(v) for v in value['a']], [_f(v) for v in value['b']]]}
        if type_ == 'line':
            return {'kind': 'line', 'value': _line_through(value['p'], value['dir'])}
        if type_ == 'ray':
            d = value['dir']
            n = math.hypot(_f(d[0]), _f(d[1])) or 1.0
            return {'kind': 'ray', 'value': {'origin': [_f(v) for v in value['origin']],
                                             'direction': [_f(d[0]) / n, _f(d[1]) / n]}}
        if type_ == 'circle':
            return {'kind': 'circle', 'value': {'center': [_f(v) for v in value['c']], 'radius': _f(value['r'])}}
        if type_ in ('arc', 'sector'):
            return {'kind': 'arc', 'value': {'center': [_f(v) for v in value['c']], 'radius': _f(value['r']),
                                             'a0': _f(value['a0']), 'a1': _f(value['a1'])}}
        if type_ == 'polygon':
            return {'kind': 'polygon', 'value': [[_f(x), _f(y)] for x, y in value['vertices']]}
        if type_ == 'number':
            kind = 'angle' if value.get('unit') == 'angle' else 'number'
            return {'kind': kind, 'value': _f(value['value'])}
        if type_ == 'angle':
            return {'kind': 'angle', 'value': _f(value['size'])}
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    return None


_KIND_OF_TYPE = {'point': 'point', 'segment': 'segment', 'vector': 'vector', 'line': 'line', 'ray': 'ray',
                 'circle': 'circle', 'arc': 'arc', 'sector': 'arc', 'polygon': 'polygon', 'number': 'number',
                 'angle': 'angle'}


def classic_report_value(type_: str, data):
    """The value of a classic data object in report form (through the bridge's
    ``from_classic``); ``{"kind", "value": None}`` — undefined in the classic
    (an intersection that does not exist, a number that is ``nan`` or
    infinite); ``None`` when the kind has no form."""
    if data is None:
        kind = _KIND_OF_TYPE.get(type_)
        return {'kind': kind, 'value': None} if kind else None
    try:
        from ..kernel.bridge import from_classic
        out = native_report_value(type_, from_classic(type_, data))
    except Exception:       # noqa: BLE001 — a classic object of another kind: no value
        return None
    if out is not None and out['kind'] in ('number', 'angle') and not math.isfinite(out['value']):
        return {'kind': out['kind'], 'value': None}      # nan, inf: no value, as an undefined one of the kernel
    return out


def _dist(p, q) -> float:
    return math.hypot(_f(p[0]) - _f(q[0]), _f(p[1]) - _f(q[1]))


def _angle_diff(a: float, b: float) -> float:
    d = (a - b) % (2 * math.pi)
    return min(d, 2 * math.pi - d)


def _delta(expected: dict, actual: dict, scale: float):
    """The discrepancy in world units (``None`` — the kinds do not compare)."""
    ek, ak = expected.get('kind'), actual.get('kind')
    ev, av = expected.get('value'), actual.get('value')
    if ev is None or av is None:
        return None
    if ek == 'point' and ak == 'point':
        return _dist(ev, av)
    if ek in ('number',) and ak in ('number', 'angle'):
        return abs(_f(ev) - _f(av)) * scale / max(1.0, scale, abs(_f(ev)))
    if ek == 'angle' and ak in ('angle', 'number'):
        a = _f(av)
        d = _angle_diff(_f(ev), a)
        if expected.get('range') in ('minor', 'reflex'):
            # <angleStyle val="1|2"> (not reflex / reflex): GGB files hold either the ccw size native keeps
            # or the size shown within 0–180° / 180–360°; the same angle either way
            a %= 2 * math.pi
            shown = min(a, 2 * math.pi - a) if expected['range'] == 'minor' else max(a, 2 * math.pi - a)
            d = min(d, _angle_diff(_f(ev), shown))
        return d * scale
    if ek == 'line':
        if ak == 'line':
            other = av
        elif ak in ('segment', 'vector'):
            other = _line_through(av[0], [av[1][0] - av[0][0], av[1][1] - av[0][1]])
        elif ak == 'ray':
            other = _line_through(av['origin'], av['direction'])
        else:
            return None
        if other is None:
            return math.inf
        return max(abs(ev[0] - other[0]) * scale, abs(ev[1] - other[1]) * scale, abs(ev[2] - other[2]))
    if ek in ('segment', 'vector') and ak == ek:
        return max(_dist(ev[0], av[0]), _dist(ev[1], av[1]))
    if ek == 'ray' and ak == 'ray':
        return max(_dist(ev['origin'], av['origin']), _dist(ev['direction'], av['direction']) * scale)
    if ek == 'circle' and ak in ('circle', 'arc'):
        return max(_dist(ev['center'], av['center']), abs(_f(ev['radius']) - _f(av['radius'])))
    if ek == 'arc' and ak == 'arc':
        r = max(_f(ev['radius']), 0.0)
        return max(_dist(ev['center'], av['center']), abs(_f(ev['radius']) - _f(av['radius'])),
                   _angle_diff(_f(ev['a0']), _f(av['a0'])) * r,
                   abs((_f(ev['a1']) - _f(ev['a0'])) - (_f(av['a1']) - _f(av['a0']))) * r)
    if ek == 'polygon' and ak == 'polygon':
        if len(ev) != len(av):
            return math.inf
        return max((_dist(p, q) for p, q in zip(ev, av)), default=0.0)
    return None


def compare(expected, actual, scale: float, *, tol: float = TOL_IMPORT):
    """``(status, delta)`` of ``actual`` (native, report form or ``None`` —
    undefined) against ``expected`` (report form; ``{"kind": k, "value":
    None}`` — undefined in GeoGebra)."""
    if expected is None:
        return 'not_checked', None
    if expected.get('value') is None:
        return ('passed', 0.0) if actual is None else ('failed', None)
    if actual is None:
        return 'failed', None
    delta = _delta(expected, actual, scale)
    if delta is None:
        return 'not_checked', None
    if not math.isfinite(delta):
        return 'failed', None
    return ('passed' if delta <= tol * scale else 'failed'), delta
