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


def T(t):
    return {'kind': 'pathParameter', 'value': round(t, 6) + 0.0}


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


SCENES = (_function_scenes, _conic_scenes)


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
