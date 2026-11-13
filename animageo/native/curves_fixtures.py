"""Parity fixtures of graphs and conics (registry 1.6): ``animageo-parity/v1``
files in ``animageo/native/parity/v1/curves`` (docs/native/kernel.md §14).

The documents are built here; expectations are what this library gives.
Numbers are rounded as in the 2D fixtures: inputs to 6 decimals (as the
documents of the conditions), expectations to 9 decimals (as the paint
fixtures), so that a fresh build is byte-identical on another machine; they
compare with ``tol.parity``. A fixture has the shape of ``parity/v1/expected``
(``fixtures verify`` reads it); a case of a document with graphs also has
``samples`` — ``{elementId: [[x, y | null], …]}``, ``function_samples`` of
each defined graph over the x-range of the bounds (33 points): what the web
compares its own evaluation of the expression with.

``python -m animageo.native fixtures curves [-o DIR] [--check]``.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .registry import REGISTRY_VERSION

__all__ = ['DEFAULT_DIR', 'build_fixtures', 'write_fixtures', 'check_fixtures', 'verify_fixtures',
           'verify_fixture', 'case_samples']

DEFAULT_DIR = Path(__file__).resolve().parent / 'parity' / 'v1' / 'curves'
DIGITS = 9


# ── expressions ──────────────────────────────────────────────────────────

X = {'var': 'x'}
Y = {'var': 'y'}


def n(v):
    return {'num': v}


def o(name, *args):
    return {'op': name, 'args': list(args)}


def call(name, *args):
    return {'fn': name, 'args': list(args)}


def r(i):
    return {'ref': i}


def sq(a):
    return o('^', a, n(2))


# ── documents ────────────────────────────────────────────────────────────

def _ref(el_id):
    return {'kind': 'ref', 'elementId': el_id}


def _num(v):
    return {'kind': 'number', 'value': v}


def _arg(v):
    return _ref(v) if isinstance(v, str) else _num(v)


def P(x, y):
    """A point input, rounded as the documents of the conditions."""
    return {'kind': 'point', 'value': [round(x, 6) + 0.0, round(y, 6) + 0.0]}


def N(v):
    return {'kind': 'number', 'value': round(v, 6) + 0.0}


def T(t, **extra):
    """A path parameter input; ``extra``: ``branch``, ``pathKind`` (registry 1.9)."""
    return dict({'kind': 'pathParameter', 'value': round(t, 6) + 0.0}, **extra)


class _Doc:
    def __init__(self, doc_id, bounds=(-10, -10, 10, 10)):
        self.doc = {'format': 'animageo-construction/v1', 'documentId': doc_id,
                    'operationRegistryVersion': REGISTRY_VERSION, 'operations': {}, 'elements': {}, 'inputs': {},
                    'viewDefaults': {'bounds': list(bounds)}}

    def op(self, op_id, name, args, outputs):
        self.doc['operations'][op_id] = {'id': op_id, 'op': name, 'args': args,
                                         'outputs': [{'slot': s, 'elementId': e} for s, e, _t in outputs]}
        for slot, el_id, type_ in outputs:
            self.doc['elements'][el_id] = {'id': el_id, 'type': type_, 'displayName': el_id,
                                           'producer': {'operationId': op_id, 'slot': slot}}
        return self

    def free(self, el_id, x, y):
        self.op('op_' + el_id, 'point.free', {}, [('point', el_id, 'point')])
        self.doc['inputs'][el_id] = P(x, y)
        return self

    def number(self, el_id, v):
        self.op('op_' + el_id, 'number.free', {}, [('number', el_id, 'number')])
        self.doc['inputs'][el_id] = N(v)
        return self

    def _two(self, name, el_id, a, b, type_, slots=('a', 'b')):
        return self.op('op_' + el_id, name, {slots[0]: _ref(a), slots[1]: _ref(b)}, [(type_, el_id, type_)])

    def line(self, el_id, a, b):
        return self._two('line.by_points', el_id, a, b, 'line')

    def segment(self, el_id, a, b):
        return self._two('segment.by_points', el_id, a, b, 'segment')

    def ray(self, el_id, origin, through):
        return self._two('ray.by_points', el_id, origin, through, 'ray', slots=('origin', 'through'))

    # graphs
    def function(self, el_id, ast, *refs, lo=None, hi=None):
        args = {'expr': {'kind': 'expr', 'ast': ast}, 'refs': {'kind': 'list', 'items': [_ref(i) for i in refs]}}
        if lo is not None:
            args['min'] = _num(lo)
        if hi is not None:
            args['max'] = _num(hi)
        return self.op('op_' + el_id, 'function.expr', args, [('function', el_id, 'function')])

    def _search(self, prefix, name, base, args, count):
        if count != 1:
            args = dict(args, count=_num(count))
        return self.op('op_' + prefix, name, args,
                       [(f'{base}.{k}', f'{prefix}{k}', 'point') for k in range(1, count + 1)])

    def roots(self, prefix, fn, a, b, count=1):
        return self._search(prefix, 'function.root', 'root', {'function': _ref(fn), 'a': _arg(a), 'b': _arg(b)},
                            count)

    def extrema(self, prefix, fn, a, b, count=1):
        return self._search(prefix, 'function.extremum', 'extremum',
                            {'function': _ref(fn), 'a': _arg(a), 'b': _arg(b)}, count)

    def graphs(self, prefix, first, second, count=2):
        return self._search(prefix, 'intersect.function_function', 'point',
                            {'first': _ref(first), 'second': _ref(second)}, count)

    def graph_line(self, prefix, fn, line, count=2):
        return self._search(prefix, 'intersect.function_line', 'point', {'function': _ref(fn), 'line': _ref(line)},
                            count)

    def on_graph(self, el_id, fn, x):
        self.op('op_' + el_id, 'point.on_function', {'function': _ref(fn)}, [('point', el_id, 'point')])
        self.doc['inputs'][el_id] = T(x)
        return self

    def closest(self, el_id, path, point):
        return self.op('op_' + el_id, 'point.closest', {'path': _ref(path), 'point': _ref(point)},
                       [('foot', el_id, 'point')])

    def on_path(self, el_id, path, t, **extra):
        """Registry 1.9: ``point.on_path`` on a conic or a graph too."""
        self.op('op_' + el_id, 'point.on_path', {'path': _ref(path)}, [('point', el_id, 'point')])
        self.doc['inputs'][el_id] = T(t, **extra)
        return self

    # conics
    def conic(self, el_id, name, **slots):
        return self.op('op_' + el_id, name, {k: _ref(v) for k, v in slots.items()}, [('conic', el_id, 'conic')])

    def ellipse(self, el_id, f1, f2, through):
        return self.conic(el_id, 'conic.ellipse_foci_point', f1=f1, f2=f2, through=through)

    def hyperbola(self, el_id, f1, f2, through):
        return self.conic(el_id, 'conic.hyperbola_foci_point', f1=f1, f2=f2, through=through)

    def parabola(self, el_id, focus, directrix):
        return self.conic(el_id, 'conic.parabola_focus_directrix', focus=focus, directrix=directrix)

    def five(self, el_id, *points):
        return self.conic(el_id, 'conic.five_points', **dict(zip('abcde', points)))

    def equation(self, el_id, ast, *refs):
        args = {'expr': {'kind': 'expr', 'ast': ast}, 'refs': {'kind': 'list', 'items': [_ref(i) for i in refs]}}
        return self.op('op_' + el_id, 'conic.equation', args, [('conic', el_id, 'conic')])

    def center(self, el_id, conic):
        return self.op('op_' + el_id, 'conic.center', {'conic': _ref(conic)}, [('center', el_id, 'point')])

    def foci(self, prefix, conic):
        return self.op('op_' + prefix, 'conic.foci', {'conic': _ref(conic)},
                       [('first', prefix + '1', 'point'), ('second', prefix + '2', 'point')])

    def vertices(self, prefix, conic):
        slots = ('first', 'second', 'third', 'fourth')
        return self.op('op_' + prefix, 'conic.vertices', {'conic': _ref(conic)},
                       [(s, f'{prefix}{k}', 'point') for k, s in enumerate(slots, 1)])

    def axes(self, prefix, conic):
        return self.op('op_' + prefix, 'conic.axes', {'conic': _ref(conic)},
                       [('focal', prefix + '_focal', 'line'), ('conjugate', prefix + '_conj', 'line')])

    def line_conic(self, prefix, line, conic):
        return self.op('op_' + prefix, 'intersect.line_conic', {'line': _ref(line), 'conic': _ref(conic)},
                       [('first', prefix + '1', 'point'), ('second', prefix + '2', 'point')])

    # registry 1.8: common points of conics
    def circle(self, el_id, center, through):
        return self.op('op_' + el_id, 'circle.center_point', {'center': _ref(center), 'through': _ref(through)},
                       [('circle', el_id, 'circle')])

    def arc(self, el_id, center, a, b):
        return self.op('op_' + el_id, 'arc.center_two_points', {'center': _ref(center), 'a': _ref(a), 'b': _ref(b)},
                       [('arc', el_id, 'arc')])

    def meet(self, prefix, first, second):
        slots = ('first', 'second', 'third', 'fourth')
        return self.op('op_' + prefix, 'intersect.conic_conic', {'first': _ref(first), 'second': _ref(second)},
                       [(s, f'{prefix}{k}', 'point') for k, s in enumerate(slots, 1)])

    def graph_conic(self, prefix, fn, conic, count=4):
        return self._search(prefix, 'intersect.function_conic', 'point', {'function': _ref(fn), 'conic': _ref(conic)},
                            count)

    def circles(self, prefix, first, second):
        return self.op('op_' + prefix, 'intersect.circle_circle', {'first': _ref(first), 'second': _ref(second)},
                       [('first', prefix + '1', 'point'), ('second', prefix + '2', 'point')])

    def nearest(self, el_id, first, second, near):
        return self.op('op_' + el_id, 'intersect.nearest',
                       {'first': _ref(first), 'second': _ref(second), 'near': _ref(near)}, [('point', el_id, 'point')])

    def other_than(self, el_id, first, second, known):
        return self.op('op_' + el_id, 'intersect.other_than',
                       {'first': _ref(first), 'second': _ref(second), 'known': _ref(known)}, [('point', el_id, 'point')])

    # registry 1.9: the area between graphs
    def area(self, el_id, first, second=None, a=None, b=None, lobe=None):
        args = {'first': _ref(first)}
        if second is not None:
            args['second'] = _ref(second)
        if a is not None:
            args['a'], args['b'] = _arg(a), _arg(b)
        if lobe is not None:
            args['lobe'] = _num(lobe)
        return self.op('op_' + el_id, 'function.area_between', args, [('region', el_id, 'region')])

    def meet_lines(self, el_id, first, second):
        return self.op('op_' + el_id, 'intersect.line_line', {'first': _ref(first), 'second': _ref(second)},
                       [('point', el_id, 'point')])

    def line_circle(self, prefix, line, circle):
        return self.op('op_' + prefix, 'intersect.line_circle', {'line': _ref(line), 'circle': _ref(circle)},
                       [('first', prefix + '1', 'point'), ('second', prefix + '2', 'point')])

    def polygon(self, el_id, *vertices):
        return self.op('op_' + el_id, 'polygon.by_points', {'vertices': {'kind': 'list', 'items': [_ref(v) for v in vertices]}},
                       [('polygon', el_id, 'polygon')])

    def boundary(self, el_id, curves=(), froms=(), tos=(), inside=(), outside=()):
        """Registry 1.9: ``region.by_boundary`` over lists of element IDs."""
        def refs(ids):
            return {'kind': 'list', 'items': [_ref(i) for i in ids]}
        args = {'curves': refs(curves), 'from': refs(froms), 'to': refs(tos), 'inside': refs(inside),
                'outside': refs(outside)}
        return self.op('op_' + el_id, 'region.by_boundary', args, [('region', el_id, 'region')])

    def measures(self, *regions):
        """``measure.area`` (``<id>_area``) and ``measure.perimeter`` (``<id>_len``) of each region."""
        for el_id in regions:
            self.op(f'op_{el_id}_area', 'measure.area', {'of': _ref(el_id)}, [('number', el_id + '_area', 'number')])
            self.op(f'op_{el_id}_len', 'measure.perimeter', {'of': _ref(el_id)}, [('number', el_id + '_len', 'number')])
        return self


def _cases(*rows):
    """``(name, {elementId: input})`` → parity scene cases."""
    out = []
    for name, inputs in rows:
        case = {'name': name}
        if inputs:
            case['inputs'] = inputs
        out.append(case)
    return out


# ── graphs ───────────────────────────────────────────────────────────────

def _function_scenes():
    out = []
    # 1. k·x² − 1: roots and the vertex as k changes
    d = _Doc('fn_parabola_k', (-4, -3, 4, 3)).number('k', 1)
    d.function('f', o('-', o('*', r(0), sq(X)), n(1)), 'k').roots('r', 'f', -3, 3, 3).extrema('m', 'f', -3, 3)
    out.append((d, _cases(('k1', None), ('k_quarter', {'k': N(0.25)}), ('k_negative', {'k': N(-1)}),
                          ('k_steep', {'k': N(4)}))))
    # 2. sin x: roots in a window of number inputs
    d = _Doc('fn_sine_window', (-8, -2, 8, 2)).number('a', -4).number('b', 4)
    d.function('f', call('sin', X)).roots('r', 'f', 'a', 'b', 3)
    out.append((d, _cases(('symmetric', None), ('right', {'a': N(0.5), 'b': N(7)}),
                          ('between', {'a': N(0.5), 'b': N(2.5)}), ('reversed', {'a': N(2), 'b': N(1)}))))
    # 3. √(x − c), a point on it and a graph cut by a domain
    d = _Doc('fn_domain', (-3, -1, 9, 4)).number('c', 0)
    d.function('f', call('sqrt', o('-', X, r(0))), 'c').on_graph('P', 'f', 4)
    d.function('g', call('sqrt', X), lo=1, hi=4).on_graph('Q', 'g', 9)
    out.append((d, _cases(('origin', None), ('shifted', {'c': N(-2), 'P': T(2), 'Q': T(-1)}),
                          ('outside', {'c': N(1), 'P': T(0.5), 'Q': T(2.25)}))))
    # 4. empty domains
    d = _Doc('fn_empty_domain', (-4, -4, 4, 4)).function('f', X, lo=2, hi=2).roots('r', 'f', -1, 1)
    d.function('g', X, lo=5, hi=6).roots('s', 'g', 0, 1).extrema('m', 'g', 0, 1)
    out.append((d, _cases(('default', None))))
    # 5. what is not a root: a pole, a jump, the zero function; a double root
    d = _Doc('fn_root_kinds', (-2, -3, 3, 3))
    d.function('pole', o('/', n(1), o('-', X, n(0.3)))).roots('rp', 'pole', -1, 2)
    d.function('jump', {'if': [{'cmp': '<', 'args': [X, n(0.3)]}, n(-1), n(1)]}).roots('rj', 'jump', -1, 2)
    d.function('zero', o('*', n(0), X)).roots('rz', 'zero', -1, 2)
    d.function('square', sq(o('-', X, n(1.3)))).roots('rs', 'square', -1, 2, 2)
    out.append((d, _cases(('default', None))))
    # 6. x³ − 3x: extrema in a window of number inputs
    d = _Doc('fn_cubic_extrema', (-3, -4, 3, 4)).number('a', -3).number('b', 3)
    d.function('f', o('-', o('^', X, n(3)), o('*', n(3), X))).extrema('m', 'f', 'a', 'b', 3)
    out.append((d, _cases(('both', None), ('right', {'a': N(0)}), ('monotone', {'a': N(2)}),
                          ('reversed', {'a': N(3), 'b': N(2)}))))
    # 7. |x − s| + t: a kink as an extremum, roots on both sides
    d = _Doc('fn_abs_kink', (-4, -2, 4, 4)).number('s', 0.25).number('t', -1)
    d.function('f', o('+', call('abs', o('-', X, r(0))), r(1)), 's', 't')
    d.extrema('m', 'f', -2, 2).roots('r', 'f', -3, 3, 2)
    out.append((d, _cases(('below', None), ('left', {'s': N(-0.5), 't': N(-0.5)}),
                          ('above', {'s': N(1), 't': N(0.5)}))))
    # 8. x² and x + k
    d = _Doc('fn_graph_graph', (-4, -2, 4, 8)).number('k', 2)
    d.function('f', sq(X)).function('g', o('+', X, r(0)), 'k').graphs('p', 'f', 'g', 3)
    out.append((d, _cases(('two', None), ('wide', {'k': N(6)}), ('tangent', {'k': N(-0.25)}),
                          ('apart', {'k': N(-2)}))))
    # 9. coincident graphs; sin and cos in the search window
    d = _Doc('fn_graph_graph_kinds', (-5, -2, 5, 2))
    d.function('f', X).function('g', o('*', n(1), X)).graphs('p', 'f', 'g')
    d.function('s', call('sin', X)).function('c', call('cos', X)).graphs('q', 's', 'c', 3)
    out.append((d, _cases(('default', None))))
    # 10. x² − 1 and a line
    d = _Doc('fn_graph_line', (-4, -4, 4, 6)).free('A', 0, 1).free('B', 1, 1).line('l', 'A', 'B')
    d.function('f', o('-', sq(X), n(1))).graph_line('p', 'f', 'l')
    out.append((d, _cases(('across', None), ('tangent', {'A': P(0, -2), 'B': P(1, 0)}),
                          ('vertical', {'A': P(2, 0), 'B': P(2, 1)}), ('below', {'A': P(0, -3), 'B': P(1, -3)}),
                          ('oblique', {'A': P(-1, 0), 'B': P(0, 1)}))))
    # 11. x² and a segment, a ray
    d = _Doc('fn_graph_parts', (-4, -1, 6, 6)).free('A', 0, 1).free('B', 5, 1).segment('s', 'A', 'B')
    d.free('C', 0, 4).free('D', 1, 4).ray('h', 'C', 'D')
    d.function('f', sq(X)).graph_line('p', 'f', 's').graph_line('q', 'f', 'h')
    out.append((d, _cases(('half', None), ('whole', {'A': P(-3, 4), 'B': P(3, 4), 'D': P(-1, 4)}),
                          ('point', {'A': P(0.5, 2), 'B': P(0.5, 2)}))))
    # 12. a constant graph on a line (binary-exact: the line is horizontal)
    d = _Doc('fn_graph_line_kinds', (-4, -2, 4, 4)).free('A', 0, 1).free('B', 2, 1).line('l', 'A', 'B')
    d.function('f', n(1)).graph_line('p', 'f', 'l')
    out.append((d, _cases(('on_line', None), ('crossing', {'B': P(2, 3)}),
                          ('parallel', {'A': P(0, 2), 'B': P(2, 2)}))))
    # 13. a point on a cubic in a domain
    d = _Doc('fn_point_on', (-4, -3, 4, 3))
    d.function('f', o('-', o('/', o('^', X, n(3)), n(4)), X), lo=-3, hi=3).on_graph('P', 'f', 1)
    out.append((d, _cases(('inside', None), ('left', {'P': T(-2.5)}), ('clamped', {'P': T(5)}))))
    # 14. a piecewise graph: roots and extrema over the joint
    d = _Doc('fn_piecewise', (-3, -2, 4, 3))
    d.function('f', {'if': [{'cmp': '<', 'args': [X, n(1)]}, o('-', sq(X), n(0.5)), o('-', n(1.5), X)]})
    d.roots('r', 'f', -3, 4, 3).extrema('m', 'f', -3, 4, 2)
    out.append((d, _cases(('default', None))))
    return out


# ── conics ───────────────────────────────────────────────────────────────

def _conic_scenes():
    out = []
    # 1. ellipse by its foci and a point
    d = _Doc('conic_ellipse').free('F1', -3, 0).free('F2', 3, 0).free('P', 0, 4).ellipse('e', 'F1', 'F2', 'P')
    out.append((d, _cases(('axes', None), ('turned', {'F1': P(1, 1), 'F2': P(3, 3), 'P': P(0, 4)}),
                          ('circle', {'F1': P(1, 1), 'F2': P(1, 1), 'P': P(4, 5)}),
                          ('between', {'P': P(0, 0)}))))
    # 2. hyperbola by its foci and a point
    d = _Doc('conic_hyperbola').free('F1', -5, 0).free('F2', 5, 0).free('P', 3, 0)
    d.hyperbola('h', 'F1', 'F2', 'P')
    out.append((d, _cases(('axes', None), ('turned', {'F1': P(0, 0), 'F2': P(2, 2), 'P': P(3, 0)}),
                          ('off_axis', {'P': P(6, 6.928203)}),
                          ('one_focus', {'F1': P(1, 1), 'F2': P(1, 1)}), ('bisector', {'P': P(0, 3)}),
                          ('beyond', {'P': P(7, 0)}))))
    # 3. parabola by its focus and directrix (a line)
    d = _Doc('conic_parabola').free('F', 0, 1).free('C', -1, -1).free('D', 1, -1).line('dl', 'C', 'D')
    d.parabola('p', 'F', 'dl')
    out.append((d, _cases(('up', None), ('right', {'F': P(2, 0), 'C': P(0, 0), 'D': P(0, 1)}),
                          ('turned', {'F': P(1, 1), 'C': P(0, -2), 'D': P(-2, 0)}),
                          ('on_directrix', {'F': P(0, -1)}))))
    # 4. parabola with a segment as its directrix
    d = _Doc('conic_parabola_segment').free('F', 0, 1).free('C', -1, -1).free('D', 1, -1).segment('dl', 'C', 'D')
    d.parabola('p', 'F', 'dl')
    out.append((d, _cases(('short', None), ('far', {'C': P(-2, 0), 'D': P(0, -2)}),
                          ('down', {'F': P(0, -3), 'C': P(3, 0), 'D': P(4, 0)}),
                          ('point', {'C': P(0, -1), 'D': P(0, -1)}))))
    # 5. five points
    d = _Doc('conic_five_points')
    for name, (x, y) in zip('ABCDE', ((3, 0), (-3, 0), (0, 2), (0, -2), (1.8, 1.6))):
        d.free(name, x, y)
    d.five('c', *'ABCDE')

    def five(*pts):
        return {name: P(x, y) for name, (x, y) in zip('ABCDE', pts)}
    out.append((d, _cases(('ellipse', None), ('circle', five((5, 0), (0, 5), (-5, 0), (3, 4), (-4, -3))),
                          ('hyperbola', five((1, 1), (2, 0.5), (-1, -1), (-2, -0.5), (4, 0.25))),
                          ('parabola', five((0, 0), (1, 1), (-1, 1), (2, 4), (-2, 4))),
                          ('repeated', five((3, 0), (3, 0), (0, 2), (0, -2), (1.8, 1.6))),
                          ('one_place', five((1, 1), (1, 1), (1, 1), (1, 1), (1, 1))),
                          ('four_on_a_line', five((-2, 0), (-1, 0), (1, 0), (2, 0), (0, 1))),
                          ('two_lines', five((-1, 0), (0, 0), (1, 0), (0, 1), (0, 2))))))
    # 6. central conics by an equation: x²/a² + s·y²/b² − 1 = 0; x² + y² + k = 0
    d = _Doc('conic_equation_central').number('a', 3).number('b', 2).number('s', 1).number('k', -4)
    d.equation('q', o('-', o('+', o('/', sq(X), sq(r(0))), o('/', o('*', r(2), sq(Y)), sq(r(1)))), n(1)),
               'a', 'b', 's')
    d.equation('o', o('+', o('+', sq(X), sq(Y)), r(0)), 'k')
    out.append((d, _cases(('ellipse', None), ('circle', {'a': N(2), 'k': N(-9)}),
                          ('hyperbola', {'s': N(-1)}), ('tall_hyperbola', {'a': N(2), 'b': N(4), 's': N(-1)}),
                          ('lines', {'s': N(0), 'k': N(4)}))))
    # 7. parabolas by an equation: y − k·x² − c·x = 0; (x − y)² − 4(x + y) = 0
    d = _Doc('conic_equation_parabola').number('k', 1).number('c', 0)
    d.equation('q', o('-', o('-', Y, o('*', r(0), sq(X))), o('*', r(1), X)), 'k', 'c')
    d.equation('t', o('-', sq(o('-', X, Y)), o('*', n(4), o('+', X, Y))))
    out.append((d, _cases(('unit', None), ('shifted', {'k': N(0.5), 'c': N(2)}), ('downwards', {'k': N(-0.25)}),
                          ('line', {'k': N(0), 'c': N(1)}))))
    # 8. equations that are not of a conic; x·y − t = 0
    d = _Doc('conic_equation_kinds').number('t', 1)
    d.equation('cubic', o('+', o('^', X, n(3)), Y)).equation('wave', o('+', call('sin', X), Y))
    d.equation('root', o('+', call('sqrt', X), Y)).equation('xy', o('-', o('*', X, Y), r(0)), 't')
    out.append((d, _cases(('unit', None), ('wide', {'t': N(4)}), ('negative', {'t': N(-2)}),
                          ('cross', {'t': N(0)}))))
    # 9. parts of an ellipse (a circle when the foci meet)
    d = _Doc('conic_parts_ellipse').free('F1', -3, 0).free('F2', 3, 0).free('P', 0, 4).ellipse('e', 'F1', 'F2', 'P')
    d.center('O', 'e').foci('f', 'e').vertices('v', 'e').axes('x', 'e')
    out.append((d, _cases(('axes', None), ('turned', {'F1': P(-1, -2), 'F2': P(2, 2), 'P': P(4, -1)}),
                          ('circle', {'F1': P(1, 1), 'F2': P(1, 1), 'P': P(4, 5)}))))
    # 10. parts of a hyperbola
    d = _Doc('conic_parts_hyperbola').free('F1', -5, 0).free('F2', 5, 0).free('P', 3, 0)
    d.hyperbola('h', 'F1', 'F2', 'P').center('O', 'h').foci('f', 'h').vertices('v', 'h').axes('x', 'h')
    out.append((d, _cases(('axes', None), ('turned', {'F1': P(0, 0), 'F2': P(2, 2), 'P': P(3, 0)}),
                          ('vertical', {'F1': P(0, -4), 'F2': P(0, 4), 'P': P(1, 3)}))))
    # 11. parts of a parabola
    d = _Doc('conic_parts_parabola').free('F', 0, 1).free('C', -1, -1).free('D', 1, -1).line('dl', 'C', 'D')
    d.parabola('p', 'F', 'dl').center('O', 'p').foci('f', 'p').vertices('v', 'p').axes('x', 'p')
    out.append((d, _cases(('up', None), ('right', {'F': P(2, 0), 'C': P(0, 0), 'D': P(0, 1)}),
                          ('turned', {'F': P(1, 1), 'C': P(0, -2), 'D': P(-2, 0)}))))
    # 12. an ellipse and a line
    d = _Doc('conic_line_ellipse').free('F1', -3, 0).free('F2', 3, 0).free('P', 0, 4).ellipse('e', 'F1', 'F2', 'P')
    d.free('A', -6, 0).free('B', 6, 0).line('l', 'A', 'B').line_conic('s', 'l', 'e')
    out.append((d, _cases(('major', None), ('tangent', {'A': P(-1, 4), 'B': P(1, 4)}),
                          ('miss', {'A': P(0, 6), 'B': P(1, 6)}), ('oblique', {'A': P(0, 0), 'B': P(1, 1)}))))
    # 13. a hyperbola and a line
    d = _Doc('conic_line_hyperbola').free('F1', -5, 0).free('F2', 5, 0).free('P', 3, 0)
    d.hyperbola('h', 'F1', 'F2', 'P').free('A', -6, 0).free('B', 6, 0).line('l', 'A', 'B').line_conic('s', 'l', 'h')
    out.append((d, _cases(('transverse', None), ('vertical', {'A': P(5, 0), 'B': P(5, 1)}),
                          ('both_branches', {'A': P(0, 1), 'B': P(4, 2)}), ('gap', {'A': P(1, 0), 'B': P(1, 1)}))))
    # 13a. x² − y² − 1 = 0 and a line along an asymptote (binary-exact: the
    # direction (1, 1)/√2 has equal components, the semi-axes are 1)
    d = _Doc('conic_line_rectangular').equation('h', o('-', o('-', sq(X), sq(Y)), n(1)))
    d.free('A', 0, 1).free('B', 1, 2).line('l', 'A', 'B').line_conic('s', 'l', 'h')
    out.append((d, _cases(('along_asymptote', None), ('asymptote', {'A': P(0, 0), 'B': P(1, 1)}),
                          ('transverse', {'A': P(-2, 0), 'B': P(2, 0)}), ('vertical', {'A': P(2, 0), 'B': P(2, 1)}))))
    # 14. a parabola and a line
    d = _Doc('conic_line_parabola').free('F', 0, 1).free('C', -1, -1).free('D', 1, -1).line('dl', 'C', 'D')
    d.parabola('p', 'F', 'dl').free('A', -6, 4).free('B', 6, 4).line('l', 'A', 'B').line_conic('s', 'l', 'p')
    out.append((d, _cases(('chord', None), ('along_axis', {'A': P(2, 0), 'B': P(2, 1)}),
                          ('tangent', {'A': P(0, -1), 'B': P(1, 0)}), ('miss', {'A': P(0, -2), 'B': P(1, -2)}))))
    # 15. a conic and a segment, a ray
    d = _Doc('conic_line_parts').free('F1', -3, 0).free('F2', 3, 0).free('P', 0, 4).ellipse('e', 'F1', 'F2', 'P')
    d.free('A', 0, 0).free('B', 7, 0).segment('g', 'A', 'B').line_conic('s', 'g', 'e')
    d.free('C', 0, 1).free('D', 1, 1).ray('h', 'C', 'D').line_conic('t', 'h', 'e')
    out.append((d, _cases(('from_inside', None), ('through', {'A': P(-7, 0), 'D': P(0, 2)}),
                          ('short', {'B': P(1, 0), 'C': P(-7, 1)}), ('point', {'A': P(2, 2), 'B': P(2, 2)}))))
    # 16. a chain: five points → centre and foci → the focal line → its points on the conic
    d = _Doc('conic_chain')
    for name, (x, y) in zip('ABCDE', ((3, 0), (-3, 0), (0, 2), (0, -2), (1.8, 1.6))):
        d.free(name, x, y)
    d.five('c', *'ABCDE').center('O', 'c').foci('f', 'c').line('fl', 'f1', 'f2').line_conic('s', 'fl', 'c')
    out.append((d, _cases(('ellipse', None), ('hyperbola', five((1, 1), (2, 0.5), (-1, -1), (-2, -0.5), (4, 0.25))),
                          ('parabola', five((0, 0), (1, 1), (-1, 1), (2, 4), (-2, 4))))))
    return out


def _turned(phi_deg, centre=(1.0, 0.0), a=3.0, b=1.5, names=('F1', 'F2', 'P')):
    """Inputs of an ellipse by its foci and its vertex: the axis at ``phi_deg``."""
    phi = math.radians(phi_deg)
    u = (math.cos(phi), math.sin(phi))
    e = math.sqrt(a * a - b * b)
    return {name: P(centre[0] + k * u[0], centre[1] + k * u[1]) for name, k in zip(names, (-e, e, a))}


def _meet_scenes():
    """Registry 1.8: ``intersect.conic_conic`` (docs/native/ops/intersect.conic_conic.md)."""
    out = []
    # 1. an ellipse (a = 5, b = 4) and a circle, both orders
    d = _Doc('meet_ellipse_circle').free('F1', -3, 0).free('F2', 3, 0).free('P', 0, 4).ellipse('e', 'F1', 'F2', 'P')
    d.free('K', 0, 0).free('Q', 4.5, 0).circle('k', 'K', 'Q').meet('m', 'e', 'k').meet('n', 'k', 'e')
    out.append((d, _cases(('four', None), ('tangent', {'Q': P(4, 0)}), ('close', {'Q': P(4.0001, 0)}),
                          ('two', {'K': P(5, 0), 'Q': P(6, 0)}), ('inside', {'Q': P(2, 0)}),
                          ('back', {'K': P(0.5, 0.25), 'Q': P(5, 0.25)}), ('turned', _turned(30, (0, 0), 5, 4)),
                          ('no_ellipse', {'P': P(1, 0)}))))
    # 2. the seam: the circle first, an ellipse turning about (1, 0); the
    # lower point crosses the ray +x near 40.2° and the slots swap
    d = _Doc('meet_seam').free('O', 0, 0).free('Q', 3, 0).circle('k', 'O', 'Q')
    for name, value in _turned(30).items():
        d.free(name, value['value'][0], value['value'][1])
    d.ellipse('f', 'F1', 'F2', 'P').meet('m', 'k', 'f')
    out.append((d, _cases(('before', None), ('near_before', _turned(38)), ('after', _turned(42)),
                          ('later', _turned(50)))))
    # 3. two ellipses by five points: four points, one point of each kind, the same conic
    d = _Doc('meet_two_ellipses')
    for name, (x, y) in zip('ABCDE', ((4, 0), (-4, 0), (0, 2), (0, -2), (2.4, 1.6))):
        d.free(name, x, y)
    for name, (x, y) in zip('GHIJL', ((2, 0), (-2, 0), (0, 4), (0, -4), (1.6, 2.4))):
        d.free(name, x, y)
    d.five('e', *'ABCDE').five('g', *'GHIJL').meet('m', 'e', 'g').meet('n', 'g', 'e')

    def tall(dx, dy, sx=2, sy=4):
        return {name: P(dx + x, dy + y) for name, (x, y) in
                zip('GHIJL', ((sx, 0), (-sx, 0), (0, sy), (0, -sy), (0.8 * sx, 0.6 * sy)))}
    out.append((d, _cases(('four', None), ('shifted', tall(1, 0.5)), ('apart', tall(9, 0)),
                          ('same', {name: P(x, y) for name, (x, y) in
                                    zip('GHIJL', ((0, 2), (0, -2), (4, 0), (-2.4, -1.6), (-4, 0)))}),
                          ('touching', tall(0, 0, 4, 2.5)))))
    # 4. a hyperbola, a parabola and a circle
    d = _Doc('meet_hyperbola_parabola').free('F1', -5, 0).free('F2', 5, 0).free('P', 3, 0)
    d.hyperbola('h', 'F1', 'F2', 'P').free('F', 4, 0).free('C', 0, -1).free('D', 0, 1).line('dl', 'C', 'D')
    d.parabola('p', 'F', 'dl').free('K', 0, 0).free('Q', 5, 0).circle('k', 'K', 'Q')
    d.meet('m', 'p', 'h').meet('n', 'h', 'p').meet('s', 'h', 'k').meet('t', 'p', 'k')
    out.append((d, _cases(('base', None), ('left', {'F': P(-4, 0)}), ('wide', {'F': P(6, 1), 'Q': P(8, 3)}),
                          ('far', {'K': P(30, 30), 'Q': P(31, 30)}))))
    # 5. circles and arcs: the slots of circle_circle, the part filter
    d = _Doc('meet_circles').free('O', 0, 0).free('A', 3, 0).circle('c', 'O', 'A')
    d.free('K', 2, 1).free('Q', 4.5, 1).circle('k', 'K', 'Q').meet('m', 'c', 'k').circles('q', 'c', 'k')
    d.free('B', -3, 0).arc('w', 'O', 'A', 'B').free('F1', -3, 0).free('F2', 3, 0).free('P', 0, 2)
    d.ellipse('e', 'F1', 'F2', 'P').meet('r', 'e', 'w').meet('s', 'w', 'e')
    out.append((d, _cases(('two', None), ('far', {'K': P(8, 0), 'Q': P(9, 0)}),
                          ('concentric', {'K': P(0, 0), 'Q': P(1, 0)}), ('same', {'K': P(0, 0), 'Q': P(0, 3)}),
                          ('lower_arc', {'A': P(-3, 0), 'B': P(3, 0)}))))
    # 6. far from the origin
    d = _Doc('meet_far', bounds=(999990, -1000010, 1000010, -999990))
    d.free('F1', 999996, -1000000).free('F2', 1000004, -1000000).free('P', 1000005, -1000000)
    d.ellipse('e', 'F1', 'F2', 'P').free('G1', 1000000, -1000004).free('G2', 1000000, -999996)
    d.free('R', 1000000, -999995).ellipse('g', 'G1', 'G2', 'R').meet('m', 'e', 'g')
    out.append((d, _cases(('four', None), ('two', {'G1': P(1000005, -1000004), 'G2': P(1000005, -999996),
                                                   'R': P(1000005, -999995)}))))
    # 7. a graph y = a·x² + c and a circle, an ellipse, an arc; the graph y = x² on the
    # parabola y − x² = 0 (binary-exact: coincident); a line graph and a hyperbola
    d = _Doc('meet_graph_conic').number('a', 0.25).number('c', 0)
    d.function('f', o('+', o('*', r(0), sq(X)), r(1)), 'a', 'c')
    d.free('K', 0, 5).free('Q', 4, 3).circle('k', 'K', 'Q').graph_conic('g', 'f', 'k')
    d.free('F1', -3, 0).free('F2', 3, 0).free('P', 0, 4).ellipse('e', 'F1', 'F2', 'P').graph_conic('h', 'f', 'e')
    d.free('B', -4, 3).arc('w', 'K', 'Q', 'B').graph_conic('s', 'f', 'w')
    d.function('q', sq(X)).equation('pq', o('-', Y, sq(X))).graph_conic('t', 'q', 'pq', count=2)
    d.function('l', o('*', n(0.5), X)).free('G1', -5, 0).free('G2', 5, 0).free('R', 3, 0)
    d.hyperbola('y', 'G1', 'G2', 'R').graph_conic('u', 'l', 'y', count=2)
    out.append((d, _cases(('base', None), ('tangent', {'a': N(0), 'c': N(4)}), ('close', {'a': N(0), 'c': N(3.99)}),
                          ('miss', {'c': N(20)}), ('back', {'c': N(-0.5)}), ('no_circle', {'Q': P(0, 5)}))))
    # 8. a graph and a circle far from the origin
    d = _Doc('meet_graph_far', bounds=(999990, -10, 1000010, 10)).number('a', 0.25).number('m', 1000000)
    d.function('f', o('*', r(0), sq(o('-', X, r(1)))), 'a', 'm')
    d.free('K', 1000000, 5).free('Q', 1000004, 3).circle('k', 'K', 'Q').graph_conic('g', 'f', 'k')
    out.append((d, _cases(('four', None), ('miss', {'Q': P(1000000, 7)}), ('touching', {'Q': P(1000000, 9)}))))
    # 9. conics and graphs in the curve slots of intersect.nearest and intersect.other_than:
    # for each kind of pair the solution nearest to N and the other one than it
    d = _Doc('meet_curve_slots').number('a', 0.25).number('c', 0).free('N', 3, 1)
    d.free('F1', -3, 0).free('F2', 3, 0).free('P', 0, 4).ellipse('e', 'F1', 'F2', 'P')
    d.free('A', -1, 0.5).free('B', 1, 0.5).line('l', 'A', 'B')
    d.nearest('x1', 'e', 'l', 'N').other_than('y1', 'l', 'e', 'x1')
    d.free('G1', -5, 0).free('G2', 5, 0).free('R', 3, 0).hyperbola('h', 'G1', 'G2', 'R')
    d.nearest('x2', 'e', 'h', 'N').other_than('y2', 'h', 'e', 'x2')
    d.function('f', o('+', o('*', r(0), sq(X)), r(1)), 'a', 'c')
    d.free('K', 0, 5).free('Q', 4, 3).circle('k', 'K', 'Q')
    d.nearest('x3', 'f', 'k', 'N').other_than('y3', 'k', 'f', 'x3')
    d.nearest('x4', 'l', 'f', 'N').other_than('y4', 'f', 'l', 'x4')
    d.function('g', o('+', X, n(1))).nearest('x5', 'f', 'g', 'N').other_than('y5', 'g', 'f', 'x5')
    d.free('C', -4, 3).arc('w', 'K', 'C', 'Q').nearest('x6', 'w', 'f', 'N').nearest('x7', 'e', 'w', 'N')
    d.free('S1', -1, 3).free('S2', 1, 3).segment('s', 'S1', 'S2').nearest('x8', 'f', 's', 'N')
    out.append((d, _cases(('base', None), ('left', {'N': P(-3, 1)}), ('tangent', {'A': P(-1, 4), 'B': P(1, 4)}),
                          ('miss', {'c': N(20)}), ('wide', {'S1': P(-4, 3), 'S2': P(4, 3)}),
                          ('vertical', {'A': P(2, 0), 'B': P(2, 1)}), ('off_arc', {'c': N(6)}))))
    return out


def _path_scenes():
    """Registry 1.9: a point on a conic and on a graph (docs/native/ops/point.on_path.md)."""
    out = []
    # 1. an ellipse (a = 5, b = 4), a hyperbola with a point on each branch, a parabola
    d = _Doc('path_conics').free('F1', -3, 0).free('F2', 3, 0).free('P', 0, 4).ellipse('e', 'F1', 'F2', 'P')
    d.on_path('E', 'e', 1, pathKind='ellipse')
    d.free('G1', -5, 0).free('G2', 5, 0).free('R', 3, 0).hyperbola('h', 'G1', 'G2', 'R')
    d.on_path('H', 'h', 0.5, branch=1, pathKind='hyperbola').on_path('K', 'h', -0.75, branch=-1)
    d.free('F', 0, 1).free('C', -1, -1).free('D', 1, -1).line('dl', 'C', 'D').parabola('p', 'F', 'dl')
    d.on_path('Q', 'p', 1.5, pathKind='parabola')
    out.append((d, _cases(('base', None),
                          ('turned', {'F1': P(1, 1), 'F2': P(3, 3), 'G1': P(0, 0), 'G2': P(2, 2), 'R': P(3, 0),
                                      'F': P(1, 1), 'C': P(0, -2), 'D': P(-2, 0)}),
                          ('circle', {'F1': P(1, 1), 'F2': P(1, 1), 'P': P(4, 5)}),
                          ('wrapped', {'E': T(8, pathKind='ellipse'), 'H': T(-2, branch=1, pathKind='hyperbola'),
                                       'K': T(2, branch=-1), 'Q': T(-3, pathKind='parabola')}),
                          ('degenerate', {'P': P(3, 0), 'F': P(0, -1)}))))
    # 2. one conic by its equation x²/9 + k·y² = 1: the kind changes under the point
    d = _Doc('path_conic_kind').number('k', 0.25)
    d.equation('q', o('-', o('+', o('/', sq(X), n(9)), o('*', r(0), sq(Y))), n(1)), 'k')
    d.on_path('A', 'q', 0.5, pathKind='ellipse').on_path('B', 'q', 0.5, branch=-1, pathKind='hyperbola')
    d.on_path('C', 'q', 0.5)
    out.append((d, _cases(('ellipse', None), ('hyperbola', {'k': N(-0.0625)}), ('tall', {'k': N(0.0625)}),
                          ('back', {'k': N(0.5)}))))
    # 3. graphs: a domain, a piecewise graph with a gap, a pole
    d = _Doc('path_graphs', (-4, -3, 4, 5))
    d.function('f', sq(X), lo=-1, hi=2).on_path('A', 'f', 0.5)
    gap = {'if': [{'cmp': '<', 'args': [X, n(0)]}, o('-', n(0), X),
                  {'if': [{'cmp': '>=', 'args': [X, n(1)]}, o('-', X, n(1))]}]}
    d.function('g', gap).on_path('B', 'g', -1.5)
    d.function('h', o('/', n(1), X)).on_path('C', 'h', 0.5)
    out.append((d, _cases(('inside', None), ('ends', {'A': T(5), 'B': T(1), 'C': T(-2)}),
                          ('low_end', {'A': T(-3), 'B': T(3)}), ('gap', {'B': T(0.5), 'C': T(0)}))))
    # 4. the closest point of an ellipse, a hyperbola (the nearest branch) and a parabola
    d = _Doc('closest_conics').free('F1', -4, 0).free('F2', 4, 0).free('P', 0, 3).ellipse('e', 'F1', 'F2', 'P')
    d.free('G1', -5, 0).free('G2', 5, 0).free('R', 3, 0).hyperbola('h', 'G1', 'G2', 'R')
    d.free('F', 0, 1).free('C', -1, -1).free('D', 1, -1).line('dl', 'C', 'D').parabola('p', 'F', 'dl')
    d.free('Z', 6, 2).closest('E', 'e', 'Z').closest('H', 'h', 'Z').closest('Q', 'p', 'Z')
    out.append((d, _cases(('outside', None), ('inside', {'Z': P(1, 0.5)}), ('left', {'Z': P(-2.5, -1)}),
                          ('axis', {'Z': P(1, 0)}), ('far_axis', {'Z': P(20, 0)}), ('centre', {'Z': P(0, 0)}),
                          ('conjugate', {'Z': P(0, 3)}), ('above', {'Z': P(0, 5)}),
                          ('turned', {'F1': P(1, 1), 'F2': P(3, 3), 'G1': P(0, 0), 'G2': P(2, 2), 'R': P(3, 0),
                                      'F': P(1, 1), 'C': P(0, -2), 'D': P(-2, 0)}))))
    # 5. the closest point of a graph: a domain, a piecewise graph with a gap, no value at all
    d = _Doc('closest_graphs', (-4, -3, 4, 5)).free('Z', 0, 3)
    d.function('f', sq(X), lo=-1, hi=2).closest('A', 'f', 'Z')
    d.function('g', gap).closest('B', 'g', 'Z')
    d.number('c', 1).function('h', call('sqrt', o('-', r(0), X)), 'c', lo=2, hi=5).closest('C', 'h', 'Z')
    out.append((d, _cases(('above', None), ('right', {'Z': P(5, 5)}), ('gap_left', {'Z': P(0.3, -0.5)}),
                          ('gap_right', {'Z': P(0.8, -0.5)}), ('far', {'Z': P(60, 0)}),
                          ('back', {'c': N(9), 'Z': P(3, 0)}))))
    return out


def _area_scenes():
    """Registry 1.9: ``function.area_between`` — lobes, limits, kinds of the second
    boundary and every status of the operation, with the area and the perimeter
    of each region."""
    out = []
    # 1. c − x² and the axis: the lobe, the second lobe that is not there, two limits;
    #    a lobe number with limits (invalid_parameter); a graph that is the axis for x < 0,
    #    whose first lobe lies on the axis (empty_region)
    d = _Doc('region_parabola_axis', (-4, -3, 4, 3)).number('c', 1).free('A', -2, 0).free('B', 0.5, 0)
    d.function('f', o('-', r(0), sq(X)), 'c').area('S', 'f').area('T', 'f', a='A', b='B').area('U', 'f', lobe=2)
    d.area('V', 'f', a='A', b='B', lobe=2)
    d.function('z', {'if': [{'cmp': '<', 'args': [X, n(0)]}, n(0), X]}).area('E', 'z')
    d.measures('S', 'T')
    out.append((d, _cases(('base', None), ('wide', {'c': N(4)}), ('below', {'c': N(-1)}),
                          ('touching', {'c': N(0)}), ('nearly', {'c': N(0.01)}),
                          ('reversed', {'A': P(1.5, 0), 'B': P(-1, 0)}))))
    # 2. two graphs: x + c over x²; x³ and x, the second lobe; sin and cos by lobes; f ≡ g
    d = _Doc('region_two_graphs', (-4, -2, 4, 6)).number('c', 2)
    d.function('f', o('+', X, r(0)), 'c').function('g', sq(X)).area('S', 'f', 'g')
    d.function('k', o('^', X, n(3))).function('m', X).area('U', 'k', 'm', lobe=2)
    d.function('s', call('sin', X)).function('q', call('cos', X)).area('W', 's', 'q').area('W2', 's', 'q', lobe=2)
    d.function('e', o('*', n(1), X)).area('Z', 'm', 'e')
    d.measures('S', 'U', 'W')
    out.append((d, _cases(('base', None), ('narrow', {'c': N(0)}), ('apart', {'c': N(-1)}))))
    # 3. a graph and a line: the lobe; limits at the common points, on the graph, literal
    d = _Doc('region_graph_line', (-4, -2, 4, 8)).free('P', -1, 1).free('Q', 2, 4).line('l', 'P', 'Q')
    d.function('f', sq(X)).area('S', 'f', 'l').graph_line('X', 'f', 'l')
    d.area('T', 'f', 'l', a='X1', b='X2').area('V', 'f', 'l', a=-2, b=3)
    d.on_graph('Ga', 'f', -0.5).on_graph('Gb', 'f', 1.5).area('L', 'f', 'l', a='Ga', b='Gb')
    d.measures('S', 'V', 'L')
    out.append((d, _cases(('base', None), ('vertical', {'Q': P(-1, 4)}), ('below', {'P': P(0, -1), 'Q': P(1, -1)}),
                          ('same_limits', {'Gb': T(-0.5)}))))
    # 4. a pole, a step and tan between the limits; a steep atan is continuous
    d = _Doc('region_discontinuous', (-4, -4, 4, 4)).number('a', -1).number('b', 2).number('c', 0)
    d.function('f', o('/', n(1), X)).area('S', 'f', a='a', b='b')
    d.function('g', {'if': [{'cmp': '<', 'args': [X, r(0)]}, n(1), n(2)]}, 'c').area('T', 'g', a='a', b='b')
    d.function('t', call('tan', X)).area('Z', 't', a=1, b='b')
    d.function('h', call('atan', o('*', n(50), X))).area('V', 'h', a='a', b=1)
    d.measures('S', 'V')
    out.append((d, _cases(('across', None), ('right', {'a': N(0.5)}), ('step_left', {'c': N(-3)}),
                          ('before_pole', {'b': N(1.5)}))))
    # 5. out of the domain: √x and the axis, x on [0, 3]
    d = _Doc('region_domain', (-2, -1, 6, 4)).number('a', -1).number('b', 1)
    d.function('f', call('sqrt', X)).area('S', 'f', a='a', b='b').area('U', 'f')
    d.function('g', X, lo=0, hi=3).area('T', 'g', a='a', b='b')
    d.measures('S', 'T')
    out.append((d, _cases(('base', None), ('inside', {'a': N(0), 'b': N(3)}), ('beyond', {'a': N(1), 'b': N(4)}))))
    # 6. far from the origin: a(1 − ((x − m)/10)²), flat enough for the jump test at x ≈ 10⁶
    d = _Doc('region_far', (999900, -100, 1000100, 100)).number('a', 0.5).number('m', 1000000)
    d.free('A', 999995, 0).free('B', 1000012, 0)
    d.function('f', o('*', r(0), o('-', n(1), sq(o('/', o('-', X, r(1)), n(10))))), 'a', 'm')
    d.area('S', 'f').area('T', 'f', a='A', b='B')
    d.measures('S', 'T')
    out.append((d, _cases(('base', None), ('below', {'a': N(-0.5)}), ('flat', {'a': N(0.25)}))))
    return out


def _boundary_scenes():
    """Registry 1.9: ``region.by_boundary`` — chains of lines, segments, circles
    and arcs, contours, and every status of the operation, with the area and the
    perimeter of each region."""
    out = []
    # 1. a triangle of lines through its free vertices: collinear, turned over, a
    #    vertex off its line; three lines with their intersections: concurrent, beyond
    d = _Doc('region_lines_flip', (-5, -5, 5, 5)).free('A', 0, 0).free('B', 4, 0).free('C', 0, 3).free('G', 0, 3)
    d.line('c', 'A', 'B').line('a', 'B', 'C').line('b', 'C', 'A')
    d.boundary('R', ['c', 'a', 'b'], ['A', 'B', 'C'], ['B', 'C', 'A'])
    d.boundary('V', ['c', 'a', 'b'], ['A', 'B', 'G'], ['B', 'G', 'A'])
    d.free('P1', -1, 0).free('P2', 1, 0).free('Q1', 0, -1).free('Q2', 0, 1).free('S1', 4, -1).free('S2', 2, 1)
    d.line('lc', 'P1', 'P2').line('lb', 'Q1', 'Q2').line('la', 'S1', 'S2')
    d.meet_lines('X', 'lb', 'lc').meet_lines('Y', 'lc', 'la').meet_lines('Z', 'la', 'lb')
    d.boundary('T', ['lc', 'la', 'lb'], ['X', 'Y', 'Z'], ['Y', 'Z', 'X']).measures('R', 'T')
    out.append((d, _cases(('base', None), ('collinear', {'C': P(2, 0)}), ('flipped', {'C': P(1, -2)}),
                          ('off_line', {'G': P(0.5, 3)}), ('concurrent', {'S1': P(1, -1), 'S2': P(-1, 1)}),
                          ('opposite', {'S1': P(-1, -1), 'S2': P(-3, 1)}))))
    # 2. two crossing segments and a circle (the owner's example 2): X the crossing,
    #    P and Q on the circle; the vertical segment moves to the tangent and beyond
    d = _Doc('region_owner2').free('O', 0, 0).free('T', 5, 0).circle('k', 'O', 'T')
    d.free('A', -2, 0).free('B', 7, 0).free('C', 0, -2).free('D', 0, 7)
    d.segment('ab', 'A', 'B').segment('cd', 'C', 'D').meet_lines('X', 'ab', 'cd')
    d.line_circle('P', 'ab', 'k').line_circle('Q', 'cd', 'k')
    d.boundary('R', ['ab', 'k', 'cd'], ['X', 'P2', 'X'], ['P2', 'Q2', 'Q2']).measures('R')
    out.append((d, _cases(('base', None), ('moved', {'C': P(3, -2), 'D': P(3, 7)}),
                          ('tilted', {'D': P(1, 7)}), ('tangent', {'C': P(5, -2), 'D': P(5, 7)}),
                          ('apart', {'C': P(6, -2), 'D': P(6, 7)}), ('cut', {'C': P(0, 1)}))))
    # 3. the lune of two circles (r 5 and 3): the part of the small one outside the
    #    big one; internal tangency, then no common points
    d = _Doc('region_lune').free('O1', 0, 0).free('T1', 5, 0).free('O2', 4, 0).free('T2', 7, 0)
    d.circle('c1', 'O1', 'T1').circle('c2', 'O2', 'T2').circles('V', 'c1', 'c2')
    d.boundary('L', ['c2', 'c1'], ['V2', 'V2'], ['V1', 'V1']).measures('L')
    out.append((d, _cases(('base', None), ('wide', {'O2': P(6, 0), 'T2': P(9, 0)}),
                          ('tangent', {'O2': P(2, 0), 'T2': P(5, 0)}), ('inside', {'O2': P(1, 0), 'T2': P(4, 0)}))))
    # 4. the lens of two circles of radius 5: external tangency, apart
    d = _Doc('region_lens').free('O1', 0, 0).free('T1', 5, 0).free('O2', 6, 0).free('T2', 11, 0)
    d.circle('c1', 'O1', 'T1').circle('c2', 'O2', 'T2').circles('V', 'c1', 'c2')
    d.boundary('N', ['c1', 'c2'], ['V2', 'V1'], ['V1', 'V2']).measures('N')
    out.append((d, _cases(('base', None), ('deep', {'O2': P(2, 0), 'T2': P(7, 0)}),
                          ('tangent', {'O2': P(10, 0), 'T2': P(15, 0)}), ('apart', {'O2': P(11, 0), 'T2': P(16, 0)}))))
    # 5. an annulus of two contours and an island in its hole; the hole crosses,
    #    touches and leaves its ring
    d = _Doc('region_annulus').free('O', 0, 0).free('T', 5, 0).circle('big', 'O', 'T')
    d.free('H', 1, 0).free('U', 3, 0).free('W', 2, 0).circle('hole', 'H', 'U').circle('isle', 'H', 'W')
    d.boundary('R', inside=['big'], outside=['hole']).boundary('I', inside=['big', 'isle'], outside=['hole'])
    d.measures('R', 'I')
    out.append((d, _cases(('base', None), ('crossing', {'H': P(4, 0), 'U': P(6, 0), 'W': P(5, 0)}),
                          ('touching', {'H': P(3, 0), 'U': P(5, 0), 'W': P(4, 0)}),
                          ('out', {'H': P(9, 0), 'U': P(11, 0), 'W': P(10, 0)}))))
    # 6. a square with a round hole; a sector, a circle segment and a clockwise polygon
    d = _Doc('region_polygon_hole').free('A', -4, -4).free('B', 4, -4).free('C', 4, 4).free('D', -4, 4)
    d.polygon('sq', 'A', 'B', 'C', 'D').free('H', 0, 0).free('U', 2, 0).circle('hole', 'H', 'U')
    d.boundary('R', inside=['sq'], outside=['hole'])
    d.free('M', -8, 6).free('Ma', -5, 6).free('Mb', -8, 9)
    d.op('op_s', 'sector.center_two_points', {'center': _ref('M'), 'a': _ref('Ma'), 'b': _ref('Mb')},
         [('sector', 's', 'sector')])
    d.free('N', 6, 6).free('Na', 9, 6).free('Nb', 6, 9).circle('kn', 'N', 'Na')
    d.op('op_g', 'sector.segment', {'circle': _ref('kn'), 'a': _ref('Na'), 'b': _ref('Nb')},
         [('segment', 'g', 'circlesegment')])
    d.free('W1', -9, -9).free('W2', -9, -6).free('W3', -6, -6).free('W4', -6, -9).polygon('cw', 'W1', 'W2', 'W3', 'W4')
    d.boundary('S', inside=['s']).boundary('G', inside=['g']).boundary('Q', inside=['cw'])
    d.measures('R', 'S', 'G', 'Q')
    out.append((d, _cases(('base', None), ('moved', {'H': P(-1, 1), 'U': P(1, 1)}),
                          ('crossing', {'H': P(3, 0), 'U': P(5, 0)}))))
    # 7. a piece on an arc: inside its arc, beyond its end, off its circle; a whole
    #    circle from a point to itself
    d = _Doc('region_arc_parts').free('O', 0, 0).free('E', 5, 0).free('F', -3, 4).free('K', 0, 5)
    d.arc('k', 'O', 'E', 'F').segment('ko', 'K', 'O').segment('oe', 'O', 'E')
    d.boundary('R', ['k', 'ko', 'oe'], ['E', 'K', 'O'], ['K', 'O', 'E']).circle('c', 'O', 'F')
    d.boundary('W', ['c'], ['F'], ['F']).measures('R', 'W')
    out.append((d, _cases(('base', None), ('beyond', {'K': P(-4, -3)}), ('off', {'K': P(0, 4)}))))
    # 8. carriers: a conic is not a carrier yet; a broken chain; two point elements at one joint
    eq = o('-', o('+', sq(X), sq(Y)), n(4))
    d = _Doc('region_carriers').free('A', -2, 0).free('B', 2, 0).segment('s', 'A', 'B').equation('k', eq)
    d.boundary('R', ['s', 'k'], ['A', 'A'], ['B', 'B'])
    out.append((d, _cases(('base', None),)))
    d = _Doc('region_chain_errors').free('A', 0, 0).free('B', 4, 0).free('C', 0, 3).free('C2', 0, 3)
    d.segment('ab', 'A', 'B').segment('bc', 'B', 'C').segment('ca', 'C', 'A')
    d.boundary('R', ['ab', 'bc'], ['A', 'B'], ['B', 'C'])
    d.boundary('J', ['ab', 'bc', 'ca'], ['A', 'B', 'C2'], ['B', 'C', 'A'])
    out.append((d, _cases(('base', None),)))
    return out


SCENES = (_function_scenes, _conic_scenes, _meet_scenes, _path_scenes, _area_scenes, _boundary_scenes)


# ── fixtures ─────────────────────────────────────────────────────────────

def _rounded(value):
    if isinstance(value, bool) or value is None or isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f'a non-finite number {value!r} in a curves fixture')
        return round(value, DIGITS) + 0.0
    if isinstance(value, dict):
        return {k: _rounded(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_rounded(v) for v in value]
    raise TypeError(f'{type(value).__name__} in a curves fixture')


def case_samples(document: dict, expect: dict) -> dict:
    """``{elementId: [[x, y | null], …]}`` of the defined graphs of a case."""
    from .kernel.function import function_samples
    bounds = document['viewDefaults']['bounds']
    return {el_id: function_samples(rec['value'], bounds) for el_id, rec in sorted(expect.items())
            if rec.get('type') == 'function' and rec.get('state') == 'defined'}


def _fixture(doc: dict, cases: list) -> dict:
    from .parity import PARITY_FORMAT, generate_scene
    scene = {'format': PARITY_FORMAT, 'id': doc['documentId'], 'document': doc, 'cases': cases}
    fixture = json.loads(json.dumps(generate_scene(scene)))
    has_graphs = any(el['type'] == 'function' for el in doc['elements'].values())
    for case in fixture['cases']:
        if has_graphs:
            case['samples'] = case_samples(doc, case['expect'])
    return _rounded(fixture)


def build_fixtures() -> dict:
    """``{file name: fixture}``."""
    out = {}
    for group in SCENES:
        for d, cases in group():
            out[d.doc['documentId'] + '.json'] = _fixture(d.doc, cases)
    return out


def _dump(fixture) -> str:
    return json.dumps(fixture, ensure_ascii=False, indent=1) + '\n'


def write_fixtures(directory=DEFAULT_DIR) -> list:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fixture in sorted(build_fixtures().items()):
        path = directory / name
        path.write_text(_dump(fixture), encoding='utf-8')
        written.append(path)
    return written


def _unlabelled(fixture: dict) -> dict:
    out = dict(fixture)
    out.pop('generatedBy', None)
    return out


def check_fixtures(directory=DEFAULT_DIR) -> list:
    """Files that differ from a fresh build (the version label aside)."""
    directory = Path(directory)
    problems = []
    built = build_fixtures()
    for name, fixture in sorted(built.items()):
        path = directory / name
        if not path.exists():
            problems.append(f'{path}: missing')
            continue
        if _unlabelled(json.loads(path.read_text(encoding='utf-8'))) != _unlabelled(fixture):
            problems.append(f'{path}: out of date')
    for path in sorted(directory.glob('*.json')):
        if path.name not in built:
            problems.append(f'{path}: not built here')
    return problems


def verify_fixture(fixture: dict, label: str = '') -> list:
    """Mismatches of one fixture: the parity replay (``tol.parity``) and the
    samples of its graphs."""
    from .kernel.numeric import tolerances
    from .parity import verify_fixture as verify_parity
    label = label or str(fixture.get('id', '?'))
    mismatches = verify_parity(fixture, label)
    from . import evaluate
    for case in fixture['cases']:
        if 'samples' not in case:
            continue
        where = f"{label} [{case['name']}]"
        ev = evaluate(fixture['document'], inputs=case.get('inputs'))
        tol = tolerances(case['scale']).parity_length
        got = case_samples(fixture['document'], ev.elements)
        if sorted(got) != sorted(case['samples']):
            mismatches.append(f'{where} samples: graphs {sorted(case["samples"])} expected, got {sorted(got)}')
            continue
        for el_id, rows in case['samples'].items():
            if len(rows) != len(got[el_id]):
                mismatches.append(f'{where} samples {el_id}: {len(rows)} points expected, got {len(got[el_id])}')
                continue
            for k, (want, have) in enumerate(zip(rows, got[el_id])):
                same = all((a is None) == (b is None) and (a is None or abs(a - b) <= tol)
                           for a, b in zip(want, have))
                if not same:
                    mismatches.append(f'{where} samples {el_id}[{k}]: expected {want!r}, got {have!r}')
    return mismatches


def verify_fixtures(directory=DEFAULT_DIR) -> tuple:
    """``(files, cases, mismatches)`` of the fixtures in ``directory``."""
    directory = Path(directory)
    files = cases = 0
    mismatches = []
    for path in sorted(directory.glob('*.json')):
        fixture = json.loads(path.read_text(encoding='utf-8'))
        files += 1
        cases += len(fixture['cases'])
        mismatches.extend(verify_fixture(fixture, path.name))
    return files, cases, mismatches
