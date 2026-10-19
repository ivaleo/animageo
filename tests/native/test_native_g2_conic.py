"""Conics, registry 1.6 (docs/native/ops/conic.*.md)."""
import math

import pytest

from animageo import native
from animageo.native.expr import compile_function
from animageo.native.kernel import conic as geo
from animageo.native.kernel.checks import run_checks
from animageo.native.registry import registry
from tests.native.conftest import DocBuilder, ref

X = {'var': 'x'}
Y = {'var': 'y'}


def n(v):
    return {'num': v}


def op(name, *args):
    return {'op': name, 'args': list(args)}


def sq(a):
    return op('^', a, n(2))


def expr_arg(ast):
    return {'kind': 'expr', 'ast': ast}


def refs(*ids):
    return {'kind': 'list', 'items': [ref(i) for i in ids]}


class Doc(DocBuilder):
    def __init__(self, bounds=(-10, -10, 10, 10)):
        super().__init__('g2c', bounds, registry_version='1.6')

    def conic(self, el_id, name, **slots):
        return self.op('op_' + el_id, name, {k: ref(v) for k, v in slots.items()}, [('conic', el_id, 'conic')])

    def ellipse(self, el_id, f1, f2, through):
        return self.conic(el_id, 'conic.ellipse_foci_point', f1=f1, f2=f2, through=through)

    def hyperbola(self, el_id, f1, f2, through):
        return self.conic(el_id, 'conic.hyperbola_foci_point', f1=f1, f2=f2, through=through)

    def parabola(self, el_id, focus, directrix):
        return self.conic(el_id, 'conic.parabola_focus_directrix', focus=focus, directrix=directrix)

    def five(self, el_id, *points):
        return self.conic(el_id, 'conic.five_points', **dict(zip('abcde', points)))

    def equation(self, el_id, ast, *ref_ids):
        return self.op('op_' + el_id, 'conic.equation', {'expr': expr_arg(ast), 'refs': refs(*ref_ids)},
                       [('conic', el_id, 'conic')])

    def number(self, el_id, v):
        self.op('op_' + el_id, 'number.free', {}, [('number', el_id, 'number')])
        self.doc['inputs'][el_id] = {'kind': 'number', 'value': v}
        return self

    def part(self, op_name, conic, el_prefix, slots, types='point'):
        return self.op('op_' + el_prefix, op_name, {'conic': ref(conic)},
                       [(slot, f'{el_prefix}_{slot}', types) for slot in slots])

    def line_conic(self, el_prefix, line, conic):
        return self.op('op_' + el_prefix, 'intersect.line_conic', {'line': ref(line), 'conic': ref(conic)},
                       [('first', el_prefix + '1', 'point'), ('second', el_prefix + '2', 'point')])


def ev(doc):
    return native.evaluate(doc.doc)


def value(e, el_id):
    record = e.elements[el_id]
    assert record['state'] == 'defined', record
    return record['value']


def reason(e, el_id):
    record = e.elements[el_id]
    assert record['state'] != 'defined', record
    return record['reason']


def approx(v, rel=1e-12, abs_=1e-12):
    return pytest.approx(v, rel=rel, abs=abs_)


def checks_pass(doc):
    report = run_checks(ev(doc))
    assert report.results and report.ok, report.errors


# ── the registry ──────────────────────────────────────────────────────────

G2_CONIC_OPS = {'conic.ellipse_foci_point', 'conic.hyperbola_foci_point', 'conic.parabola_focus_directrix',
                'conic.five_points', 'conic.equation', 'conic.center', 'conic.foci', 'conic.vertices',
                'conic.axes', 'intersect.line_conic'}


def test_records():
    reg = registry()
    for name in G2_CONIC_OPS:
        record = reg.get(name)
        assert record['since'] == '1.6' and record['status'] == 'beta', name
    assert 'conic' in reg.types
    for name in ('degenerate_conic', 'not_quadratic', 'not_central'):
        assert reg.reasons[name]['state'] == 'undefined'
    assert 'conic_axis_order' in reg.policies


def test_compile_two_variables():
    q = compile_function(op('+', sq(X), op('*', n(2), Y)), vars=('x', 'y'))
    assert q(3.0, 1.0) == 11.0


# ── ellipse, hyperbola, parabola by foci ──────────────────────────────────

def test_ellipse_by_foci():
    d = Doc().free('F1', -4, 0).free('F2', 4, 0).free('P', 0, 3).ellipse('e', 'F1', 'F2', 'P')
    v = value(ev(d), 'e')
    assert v['kind'] == 'ellipse' and v['c'] == [0.0, 0.0] and v['axis'] == [1.0, 0.0]
    assert v['a'] == 5.0 and v['b'] == approx(3.0)
    checks_pass(d)


def test_ellipse_coincident_foci_is_a_circle():
    v = value(ev(Doc().free('F1', 1, 1).free('F2', 1, 1).free('P', 4, 5).ellipse('e', 'F1', 'F2', 'P')), 'e')
    assert v == {'kind': 'ellipse', 'c': [1.0, 1.0], 'axis': [1.0, 0.0], 'a': 5.0, 'b': 5.0}


def test_ellipse_point_between_foci_is_degenerate():
    e = ev(Doc().free('F1', -4, 0).free('F2', 4, 0).free('P', 1, 0).ellipse('e', 'F1', 'F2', 'P'))
    assert reason(e, 'e') == 'degenerate_conic'


def test_hyperbola_by_foci():
    d = Doc().free('F1', 0, -5).free('F2', 0, 5).free('P', 0, 3).hyperbola('h', 'F1', 'F2', 'P')
    v = value(ev(d), 'h')
    assert v['kind'] == 'hyperbola' and v['axis'] == [0.0, 1.0] and v['a'] == 3.0 and v['b'] == approx(4.0)
    checks_pass(d)


@pytest.mark.parametrize('px, py, why', [(0, 0, 'degenerate_conic'), (5, 0, 'degenerate_conic'),
                                         (7, 0, 'degenerate_conic')])
def test_hyperbola_degenerate(px, py, why):
    e = ev(Doc().free('F1', -5, 0).free('F2', 5, 0).free('P', px, py).hyperbola('h', 'F1', 'F2', 'P'))
    # (0, 0): on the perpendicular bisector; (7, 0): on the focal line outside
    assert reason(e, 'h') == why


def test_hyperbola_coincident_foci():
    e = ev(Doc().free('F1', 1, 0).free('F2', 1, 0).free('P', 3, 3).hyperbola('h', 'F1', 'F2', 'P'))
    assert reason(e, 'h') == 'coincident_points'


def test_parabola_by_focus_and_directrix():
    d = Doc().free('F', 0, 1).free('A', -1, -1).free('B', 1, -1).line('l', 'A', 'B').parabola('p', 'F', 'l')
    v = value(ev(d), 'p')
    assert v == {'kind': 'parabola', 'vertex': [0.0, 0.0], 'axis': [0.0, 1.0], 'p': 2.0}
    checks_pass(d)
    e = ev(Doc().free('F', 0, -1).free('A', -1, -1).free('B', 1, -1).line('l', 'A', 'B').parabola('p', 'F', 'l'))
    assert reason(e, 'p') == 'degenerate_conic'


# ── five points and an equation ───────────────────────────────────────────

def _five(points, bounds=(-10, -10, 10, 10)):
    d = Doc(bounds)
    names = []
    for k, (x, y) in enumerate(points):
        d.free(f'P{k}', x, y)
        names.append(f'P{k}')
    return d.five('c', *names)


def test_five_points_ellipse():
    d = _five([(5, 0), (-5, 0), (0, 3), (0, -3), (3, 2.4)])
    v = value(ev(d), 'c')
    assert v['kind'] == 'ellipse'
    assert v['c'][0] == approx(0.0) and v['c'][1] == approx(0.0)
    assert v['a'] == approx(5.0) and v['b'] == approx(3.0) and v['axis'] == [approx(1.0), approx(0.0)]
    checks_pass(d)


def test_five_points_circle_parabola_hyperbola():
    circle = value(ev(_five([(2, 0), (0, 2), (-2, 0), (0, -2), (math.sqrt(2), math.sqrt(2))])), 'c')
    assert circle['kind'] == 'ellipse' and circle['axis'] == [1.0, 0.0] and circle['a'] == circle['b'] == approx(2.0)
    parabola = value(ev(_five([(0, 0), (1, 1), (-1, 1), (2, 4), (-2, 4)])), 'c')
    assert parabola['kind'] == 'parabola' and parabola['p'] == approx(0.5)
    assert parabola['axis'] == [approx(0.0), approx(1.0)]
    hyperbola = value(ev(_five([(1, 1), (2, 0.5), (-1, -1), (-2, -0.5), (4, 0.25)])), 'c')   # x·y = 1
    assert hyperbola['kind'] == 'hyperbola' and hyperbola['a'] == approx(math.sqrt(2))
    assert hyperbola['axis'] == [approx(math.sqrt(0.5)), approx(math.sqrt(0.5))]


@pytest.mark.parametrize('points, why', [
    ([(0, 0), (1, 0), (2, 0), (3, 0), (0, 1)], 'degenerate_conic'),     # four collinear: a pencil
    ([(0, 0), (1, 0), (2, 0), (0, 1), (1, 2)], 'degenerate_conic'),     # three collinear: a pair of lines
    ([(1, 1)] * 5, 'coincident_points'),
    ([(0, 0), (0, 0), (1, 0), (0, 1), (2, 3)], 'degenerate_conic'),
])
def test_five_points_degenerate(points, why):
    assert reason(ev(_five(points)), 'c') == why


def _ellipse_equation():
    return op('-', op('+', op('/', sq(X), n(9)), op('/', sq(Y), n(4))), n(1))   # x²/9 + y²/4 − 1


def test_equation_kinds():
    d = Doc().equation('e', _ellipse_equation())
    v = value(ev(d), 'e')
    assert v['kind'] == 'ellipse' and v['c'] == [approx(0.0), approx(0.0)] and v['axis'] == [1.0, approx(0.0)]
    assert v['a'] == approx(3.0) and v['b'] == approx(2.0)          # B read at points: rounding noise
    v = value(ev(Doc().number('k', 4.0).equation('e', op('-', op('*', X, Y), {'ref': 0}), 'k')), 'e')
    assert v['kind'] == 'hyperbola' and v['a'] == approx(math.sqrt(8))
    v = value(ev(Doc().equation('e', op('-', Y, sq(op('-', X, n(1)))))), 'e')        # y = (x − 1)²
    assert v['kind'] == 'parabola' and v['vertex'] == [approx(1.0), approx(0.0)] and v['p'] == approx(0.5)
    assert v['axis'] == [approx(0.0), approx(1.0)]
    v = value(ev(Doc().equation('e', op('-', op('+', sq(X), sq(Y)), n(25)))), 'e')
    assert v == {'kind': 'ellipse', 'c': [0.0, 0.0], 'axis': [1.0, 0.0], 'a': 5.0, 'b': 5.0}


@pytest.mark.parametrize('tree, why', [
    (op('+', op('^', X, n(3)), Y), 'not_quadratic'),
    (op('-', {'fn': 'sin', 'args': [X]}, Y), 'not_quadratic'),
    (op('+', op('+', sq(X), sq(Y)), n(1)), 'degenerate_conic'),                 # no real points
    (op('-', sq(X), sq(Y)), 'degenerate_conic'),                                 # a pair of lines
    (op('+', X, Y), 'degenerate_conic'),                                         # a line
    (op('-', {'fn': 'sqrt', 'args': [X]}, Y), 'not_quadratic'),                  # no value at x < 0
])
def test_equation_refused(tree, why):
    assert reason(ev(Doc().equation('e', tree)), 'e') == why


# ── parts ─────────────────────────────────────────────────────────────────

def test_parts_of_an_ellipse():
    d = Doc().free('F1', -4, 0).free('F2', 4, 0).free('P', 0, 3).ellipse('e', 'F1', 'F2', 'P')
    d.part('conic.center', 'e', 'c', ['center']).part('conic.foci', 'e', 'f', ['first', 'second'])
    d.part('conic.vertices', 'e', 'v', ['first', 'second', 'third', 'fourth'])
    d.part('conic.axes', 'e', 'x', ['focal', 'conjugate'], 'line')
    e = ev(d)
    assert value(e, 'c_center') == {'x': 0.0, 'y': 0.0}
    assert value(e, 'f_first') == {'x': -4.0, 'y': 0.0} and value(e, 'f_second') == {'x': 4.0, 'y': 0.0}
    assert value(e, 'v_first') == {'x': -5.0, 'y': 0.0} and value(e, 'v_fourth')['y'] == approx(3.0)
    assert value(e, 'x_focal') == {'p': [0.0, 0.0], 'dir': [1.0, 0.0]}
    assert value(e, 'x_conjugate')['dir'] == [-0.0, 1.0] or value(e, 'x_conjugate')['dir'] == [0.0, 1.0]
    checks_pass(d)


def test_parts_of_a_parabola():
    d = Doc().free('F', 0, 1).free('A', -1, -1).free('B', 1, -1).line('l', 'A', 'B').parabola('p', 'F', 'l')
    d.part('conic.center', 'p', 'c', ['center']).part('conic.foci', 'p', 'f', ['first', 'second'])
    d.part('conic.vertices', 'p', 'v', ['first', 'second', 'third', 'fourth'])
    d.part('conic.axes', 'p', 'x', ['focal', 'conjugate'], 'line')
    e = ev(d)
    assert reason(e, 'c_center') == 'not_central'
    assert value(e, 'f_first') == {'x': 0.0, 'y': 1.0} and reason(e, 'f_second') == 'branch_absent'
    assert value(e, 'v_first') == {'x': 0.0, 'y': 0.0} and reason(e, 'v_fourth') == 'branch_absent'
    assert reason(e, 'x_conjugate') == 'branch_absent'
    checks_pass(d)


# ── a line and a conic ────────────────────────────────────────────────────

def _with_line(d, ax, ay, bx, by, kind='line'):
    d.free('A', ax, ay).free('B', bx, by)
    getattr(d, kind)('l', 'A', 'B')
    return d


def test_line_ellipse_two_points_tangent_and_none():
    base = lambda: Doc().free('F1', -4, 0).free('F2', 4, 0).free('P', 0, 3).ellipse('e', 'F1', 'F2', 'P')  # noqa: E731
    d = _with_line(base(), -10, 0, 10, 0).line_conic('q', 'l', 'e')
    e = ev(d)
    assert value(e, 'q1') == {'x': approx(-5.0), 'y': 0.0} and value(e, 'q2') == {'x': approx(5.0), 'y': 0.0}
    checks_pass(d)
    e = ev(_with_line(base(), -1, 3, 1, 3).line_conic('q', 'l', 'e'))                       # tangent at the top
    assert e.elements['q1']['value'] == e.elements['q2']['value'] == {'x': approx(0.0), 'y': approx(3.0)}
    assert e.elements['q1']['detail'] == {'multiplicity': 2}
    e = ev(_with_line(base(), -1, 4, 1, 4).line_conic('q', 'l', 'e'))
    assert reason(e, 'q1') == reason(e, 'q2') == 'no_intersection'


def test_line_conic_order_follows_the_line():
    d = Doc().free('F1', -4, 0).free('F2', 4, 0).free('P', 0, 3).ellipse('e', 'F1', 'F2', 'P')
    e = ev(_with_line(d, 10, 0, -10, 0).line_conic('q', 'l', 'e'))
    assert value(e, 'q1')['x'] == approx(5.0) and value(e, 'q2')['x'] == approx(-5.0)


def test_line_conic_segment_part():
    d = Doc().free('F1', -4, 0).free('F2', 4, 0).free('P', 0, 3).ellipse('e', 'F1', 'F2', 'P')
    e = ev(_with_line(d, 0, 0, 10, 0, 'segment').line_conic('q', 'l', 'e'))
    assert reason(e, 'q1') == 'outside_part' and value(e, 'q2')['x'] == approx(5.0)


def test_line_parabola_parallel_to_the_axis():
    d = Doc().free('F', 0, 1).free('C', -1, -1).free('D', 1, -1).line('dl', 'C', 'D').parabola('p', 'F', 'dl')
    d = _with_line(d, 2, -5, 2, 5).line_conic('q', 'l', 'p')
    e = ev(d)
    assert value(e, 'q1') == {'x': 2.0, 'y': approx(1.0)} and reason(e, 'q2') == 'branch_absent'
    checks_pass(d)


def test_line_hyperbola_asymptote_parallel_and_tangent():
    hyp = lambda: Doc().free('F1', -5, 0).free('F2', 5, 0).free('P', 3, 0).hyperbola('h', 'F1', 'F2', 'P')  # noqa: E731
    # asymptotes y = ±(4/3)x; a parallel line through (3, 0) meets once
    e = ev(_with_line(hyp(), 3, 0, 6, 4).line_conic('q', 'l', 'h'))
    assert e.elements['q1']['state'] == 'defined' and reason(e, 'q2') == 'branch_absent'
    e = ev(_with_line(hyp(), 0, 0, 3, 4).line_conic('q', 'l', 'h'))                      # the asymptote
    assert reason(e, 'q1') == 'no_intersection'
    e = ev(_with_line(hyp(), 3, -1, 3, 1).line_conic('q', 'l', 'h'))                      # tangent at the vertex
    assert value(e, 'q1') == {'x': approx(3.0), 'y': approx(0.0)}
    assert e.elements['q1']['detail'] == {'multiplicity': 2}
    d = _with_line(hyp(), -10, 1, 10, 2).line_conic('q', 'l', 'h')
    checks_pass(d)


# ── pure geometry ─────────────────────────────────────────────────────────

@pytest.mark.parametrize('v', [
    {'kind': 'ellipse', 'c': [1.0, 2.0], 'axis': [0.6, 0.8], 'a': 5.0, 'b': 3.0},
    {'kind': 'hyperbola', 'c': [-1.0, 0.5], 'axis': [0.8, -0.6], 'a': 2.0, 'b': 1.5},
    {'kind': 'parabola', 'vertex': [0.5, -1.0], 'axis': [-0.6, 0.8], 'p': 1.25},
])
def test_matrix_vanishes_on_the_curve(v):
    m = geo.matrix(v)
    for x, y in geo.vertices(v):
        h = [x, y, 1.0]
        assert abs(sum(h[i] * m[i][j] * h[j] for i in range(3) for j in range(3))) < 1e-12
        assert geo.residual(v, x, y) < 1e-12
    assert geo.residual(v, *geo.label_anchor(v)) < 1e-12


# ── the classic bridge and drawing ────────────────────────────────────────

def _scene():
    d = Doc().free('F1', -4, 0).free('F2', 4, 0).free('P', 0, 3).ellipse('e', 'F1', 'F2', 'P')
    d.free('G1', -2, 5).free('G2', 2, 5).free('Q', 1, 5).hyperbola('h', 'G1', 'G2', 'Q')
    d.free('F', 0, -3).free('C', -1, -5).free('D', 1, -5).line('dl', 'C', 'D').parabola('p', 'F', 'dl')
    return d.equation('k', op('-', op('+', sq(X), sq(Y)), n(1)))


def _label(d):
    for el_id in ('e', 'h', 'p', 'k'):
        d.doc['elements'][el_id]['displayName'] = el_id
        d.doc.setdefault('appearance', {})[el_id] = {'label': {'mode': 'name'}}
    return d


def test_bridge_identity():
    from animageo.geo.lib_conic import ConicType
    from animageo.native.kernel.bridge import build_construction, from_classic
    d = _scene()
    construction, names = build_construction(d.doc)
    construction.rebuild(full=True)
    e = ev(d)
    kinds = {'e': ConicType.ELLIPSE, 'h': ConicType.HYPERBOLA, 'p': ConicType.PARABOLA, 'k': ConicType.CIRCLE}
    for el_id, kind in kinds.items():
        data = construction.element(names.by_id[el_id]).data
        assert data.type == kind
        assert from_classic('conic', data) == e.elements[el_id]['value']
    ell = construction.element(names.by_id['e']).data.as_ellipse()
    assert ell['semi_axes'] == (approx(5.0), approx(3.0))


def test_label_anchor_of_a_kernel_conic():
    from animageo.label_placement import _get_anchor
    from animageo.native.kernel.bridge import build_construction
    construction, names = build_construction(_scene().doc)
    construction.rebuild(full=True)
    anchor = _get_anchor(construction.element(names.by_id['e']))
    assert list(anchor) == [approx(0.0), approx(3.0)]


@pytest.mark.manim
def test_conics_are_drawn(tmp_path):
    pytest.importorskip('manim')
    d = _scene()
    native.render(d.doc, out=tmp_path / 'u.svg', fmt='svg', report=False)
    unlabelled = (tmp_path / 'u.svg').read_bytes()
    _label(d)
    native.render(d.doc, out=tmp_path / 'c.svg', fmt='svg', report=False)
    svg = (tmp_path / 'c.svg').read_bytes()
    plain = Doc().free('F1', -4, 0)
    native.render(plain.doc, out=tmp_path / 'p.svg', fmt='svg', report=False)
    assert unlabelled.count(b'<path') >= (tmp_path / 'p.svg').read_bytes().count(b'<path') + 5
    assert svg.count(b'<path') > unlabelled.count(b'<path')            # the four labels
    native.render(d.doc, out=tmp_path / 'c.tikz', fmt='tikz', report=False)
    tikz = (tmp_path / 'c.tikz').read_text()
    assert 'ellipse (' in tikz and 'circle (' in tikz
