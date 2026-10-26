"""Functions y = f(x), registry 1.6 (docs/native/ops/function.*.md, docs/native/expr.md §5)."""
import math

import pytest

from animageo import native
from animageo.native.expr import ExprError, compile_function, evaluate as expr_evaluate, problems
from animageo.native.kernel.checks import run_checks
from animageo.native.kernel.function import function_runs, function_samples
from animageo.native.registry import registry, signature
from tests.native.conftest import DocBuilder, num, ref

X = {'var': 'x'}


def n(v):
    return {'num': v}


def op(name, *args):
    return {'op': name, 'args': list(args)}


def fn(name, *args):
    return {'fn': name, 'args': list(args)}


def cmp(sign, a, b):
    return {'cmp': sign, 'args': [a, b]}


def power(a, k):
    return op('^', a, n(k))


def expr_arg(ast):
    return {'kind': 'expr', 'ast': ast}


def refs(*ids):
    return {'kind': 'list', 'items': [ref(i) for i in ids]}


class Doc(DocBuilder):
    def __init__(self, bounds=(-10, -10, 10, 10)):
        super().__init__('g2', bounds, registry_version='1.6')

    def function(self, el_id, ast, *ref_ids, lo=None, hi=None):
        args = {'expr': expr_arg(ast), 'refs': refs(*ref_ids)}
        if lo is not None:
            args['min'] = num(lo)
        if hi is not None:
            args['max'] = num(hi)
        return self.op('op_' + el_id, 'function.expr', args, [('function', el_id, 'function')])

    def number(self, el_id, v):
        self.op('op_' + el_id, 'number.free', {}, [('number', el_id, 'number')])
        self.doc['inputs'][el_id] = {'kind': 'number', 'value': v}
        return self

    def search(self, name, base, el_prefix, args, count=None):
        if count is not None:
            args = dict(args, count=num(count))
        k = count or 1
        return self.op('op_' + el_prefix, name, args,
                       [(f'{base}.{i}', f'{el_prefix}{i}', 'point') for i in range(1, k + 1)])

    def roots(self, el_prefix, f, a, b, count=None):
        return self.search('function.root', 'root', el_prefix, {'function': ref(f), 'a': num(a), 'b': num(b)}, count)

    def extrema(self, el_prefix, f, a, b, count=None):
        return self.search('function.extremum', 'extremum', el_prefix,
                           {'function': ref(f), 'a': num(a), 'b': num(b)}, count)


def ev(doc):
    return native.evaluate(doc.doc)


def xy(record):
    assert record['state'] == 'defined', record
    return record['value']['x'], record['value']['y']


# ── expressions with x ────────────────────────────────────────────────────

class TestExpressions:
    def test_function_nodes_need_vars(self):
        tree = op('+', X, n(1))
        assert problems(tree, 0, ('x',)) == []
        assert problems(tree, 0) == [('/args/0', "node 'var' is not in AST v1")]

    @pytest.mark.parametrize('tree', [
        {'if': [cmp('<', X, n(0)), op('neg', X), X]},
        {'if': [{'and': [cmp('>=', X, n(-1)), {'not': [cmp('>', X, n(1))]}]}, n(1)]},
        {'if': [{'or': [cmp('<=', X, n(0)), cmp('>', X, n(2))]}, n(0), power(X, 2)]},
    ])
    def test_valid_trees(self, tree):
        assert problems(tree, 0, ('x',)) == []

    @pytest.mark.parametrize('tree, pointer', [
        ({'var': 'y'}, ''),
        (cmp('<', X, n(0)), ''),                              # a condition is not a value
        ({'if': [X, n(1), n(2)]}, '/if/0'),                   # a value is not a condition
        ({'if': [cmp('<', X, n(0))]}, ''),
        ({'if': [cmp('==', X, n(0)), n(1)]}, '/if/0'),
        ({'if': [{'and': [cmp('<', X, n(0))]}, n(1)]}, '/if/0'),
        ({'var': 'x', 'num': 1}, ''),
    ])
    def test_invalid_trees(self, tree, pointer):
        found = problems(tree, 0, ('x',))
        assert found and found[0][0] == pointer, found

    def test_compile_matches_evaluate(self):
        trees = [op('+', n(1), op('*', n(2), n(3))), fn('sqrt', n(2)), op('/', n(1), n(3)),
                 fn('max', {'ref': 0}, n(-1)), op('^', n(2), n(0.5)), fn('lg', n(1000))]
        for tree in trees:
            assert compile_function(tree, [4.5])(0.0) == expr_evaluate(tree, [4.5])

    def test_compile_values_and_domain(self):
        abs_ = compile_function({'if': [cmp('<', X, n(0)), op('neg', X), X]})
        assert (abs_(-2.0), abs_(3.0)) == (2.0, 3.0)
        part = compile_function({'if': [cmp('>', X, n(0)), fn('ln', X)]})
        assert part(math.e) == pytest.approx(1.0)
        with pytest.raises(ExprError) as err:
            part(-1.0)
        assert err.value.reason == 'out_of_domain'
        with pytest.raises(ExprError):
            compile_function(op('/', n(1), X))(0.0)
        assert compile_function(op('*', {'ref': 0}, X), [2.0])(3.0) == 6.0

    def test_compile_refuses_bad_tree(self):
        with pytest.raises(ExprError):
            compile_function({'var': 'y'})


# ── the registry ──────────────────────────────────────────────────────────

G2_FUNCTION_OPS = {'function.expr', 'function.root', 'function.extremum', 'intersect.function_function',
                   'intersect.function_line', 'point.on_function'}


def test_registry_records():
    reg = registry()
    assert reg.version == '1.7'
    for name in G2_FUNCTION_OPS:
        record = reg.get(name)
        assert record['status'] == 'beta' and record['since'] == '1.6'
    assert reg.get('function.expr')['inputs'][0]['vars'] == ['x']
    assert signature(reg.get('function.expr'))['inputs'][0]['vars'] == ['x']
    assert 'vars' not in signature(reg.get('number.expression'))['inputs'][0]
    assert 'function' in reg.types and 'roots_ascending' in reg.policies


def test_expression_slot_without_vars_refuses_x():
    d = Doc()
    d.op('op_n', 'number.expression', {'expr': expr_arg(X), 'refs': refs()}, [('number', 'n', 'number')])
    rec = ev(d).elements['n']
    assert (rec['state'], rec['reason']) == ('error', 'formula')


# ── function.expr ─────────────────────────────────────────────────────────

def test_function_value():
    d = Doc().number('k', 2.0).function('f', op('*', {'ref': 0}, X), 'k', lo=-1, hi=3)
    rec = ev(d).elements['f']
    assert rec['state'] == 'defined'
    assert rec['value'] == {'expr': op('*', {'ref': 0}, X), 'refs': [2.0], 'domain': [-1.0, 3.0]}


def test_function_empty_domain():
    rec = ev(Doc().function('f', X, lo=2, hi=2)).elements['f']
    assert (rec['state'], rec['reason']) == ('undefined', 'empty_range')


def test_function_formula_error():
    rec = ev(Doc().function('f', {'var': 'y'})).elements['f']
    assert (rec['state'], rec['reason']) == ('error', 'formula')


# ── function.root ─────────────────────────────────────────────────────────

def test_simple_roots():
    d = Doc().function('f', op('-', power(X, 2), n(2))).roots('r', 'f', -3, 3, count=3)
    e = ev(d)
    assert xy(e.elements['r1']) == pytest.approx((-math.sqrt(2), 0.0), abs=1e-12)
    assert xy(e.elements['r2']) == pytest.approx((math.sqrt(2), 0.0), abs=1e-12)
    assert e.elements['r3']['reason'] == 'branch_absent'
    report = run_checks(e)
    assert report.results == {'op_r:on_graph': 'passed'}


def test_double_root_fills_two_slots():
    d = Doc().function('f', power(op('-', X, n(1.3)), 2)).roots('r', 'f', -3, 3, count=2)
    e = ev(d)
    for el in ('r1', 'r2'):
        assert xy(e.elements[el]) == pytest.approx((1.3, 0.0), abs=1e-7)
        assert e.elements[el]['detail'] == {'multiplicity': 2}


def test_root_on_a_grid_node():
    e = ev(Doc().function('f', X).roots('r', 'f', -1, 1))
    assert xy(e.elements['r1']) == (0.0, 0.0)
    assert 'detail' not in e.elements['r1']


@pytest.mark.parametrize('ast, reason', [
    (op('+', power(X, 2), n(1)), 'no_root_in_window'),
    (op('/', n(1), op('-', X, n(0.3))), 'no_root_in_window'),          # a pole is not a root
    ({'if': [cmp('<', X, n(0.3)), n(-1), n(1)]}, 'no_root_in_window'),  # nor a jump
    (op('*', n(0), X), 'coincident'),
])
def test_no_roots(ast, reason):
    rec = ev(Doc().function('f', ast).roots('r', 'f', -1, 2)).elements['r1']
    assert (rec['state'], rec['reason']) == ('undefined', reason)


def test_root_empty_interval():
    assert ev(Doc().function('f', X).roots('r', 'f', 2, 1)).elements['r1']['reason'] == 'empty_range'
    d = Doc().function('f', X, lo=5, hi=6).roots('r', 'f', 0, 1)
    assert ev(d).elements['r1']['reason'] == 'empty_range'


def test_root_with_number_inputs():
    d = Doc().number('a', -3.0).number('b', 0.0).function('f', op('-', power(X, 2), n(4)))
    d.op('op_r', 'function.root', {'function': ref('f'), 'a': ref('a'), 'b': ref('b')}, [('root.1', 'r1', 'point')])
    assert xy(ev(d).elements['r1']) == pytest.approx((-2.0, 0.0), abs=1e-12)


def test_root_count_out_of_range_has_no_slots():
    d = Doc().function('f', X).roots('r', 'f', -1, 1, count=1)
    d.doc['operations']['op_r']['args']['count'] = num(0)
    assert ev(d).elements['r1']['state'] == 'error'


# ── function.extremum ─────────────────────────────────────────────────────

def test_extrema():
    cubic = op('-', power(X, 3), op('*', n(3), X))
    e = ev(Doc().function('f', cubic).extrema('m', 'f', -3, 3, count=3))
    assert xy(e.elements['m1']) == pytest.approx((-1.0, 2.0), abs=1e-7)
    assert e.elements['m1']['detail'] == {'kind': 'max'}
    assert xy(e.elements['m2']) == pytest.approx((1.0, -2.0), abs=1e-7)
    assert e.elements['m2']['detail'] == {'kind': 'min'}
    assert e.elements['m3']['reason'] == 'branch_absent'
    assert run_checks(e).results == {'op_m:on_graph': 'passed'}


def test_extremum_of_a_kink_and_none():
    e = ev(Doc().function('f', fn('abs', op('-', X, n(0.25)))).extrema('m', 'f', -1, 1))
    assert xy(e.elements['m1']) == pytest.approx((0.25, 0.0), abs=1e-7)
    assert ev(Doc().function('f', X).extrema('m', 'f', -1, 1)).elements['m1']['reason'] == 'no_root_in_window'


# ── intersections ─────────────────────────────────────────────────────────

def _ff(d, count=2):
    return d.search('intersect.function_function', 'point', 'p', {'first': ref('f'), 'second': ref('g')}, count)


def test_function_function():
    d = Doc().function('f', power(X, 2)).function('g', op('+', X, n(2)))
    e = ev(_ff(d, 3))
    assert xy(e.elements['p1']) == pytest.approx((-1.0, 1.0), abs=1e-12)
    assert xy(e.elements['p2']) == pytest.approx((2.0, 4.0), abs=1e-12)
    assert e.elements['p3']['reason'] == 'branch_absent'
    assert run_checks(e).results == {'op_p:on_both': 'passed'}


def test_function_function_tangent_and_none():
    d = Doc().function('f', power(X, 2)).function('g', op('-', op('*', n(2), X), n(1)))
    e = ev(_ff(d))
    for el in ('p1', 'p2'):
        assert xy(e.elements[el]) == pytest.approx((1.0, 1.0), abs=1e-7)
        assert e.elements[el]['detail'] == {'multiplicity': 2}
    d = Doc().function('f', power(X, 2)).function('g', op('-', X, n(2)))
    assert ev(_ff(d)).elements['p1']['reason'] == 'no_intersection'
    d = Doc().function('f', X).function('g', op('*', n(1), X))
    assert ev(_ff(d)).elements['p1']['reason'] == 'coincident'


def test_function_function_window():
    """The search runs in the window B4 of the bounds: x = 30 is outside B4 of (−5…5)."""
    d = Doc(bounds=(-5, -5, 5, 5)).function('f', op('-', X, n(30))).function('g', n(0))
    assert ev(_ff(d, 1)).elements['p1']['reason'] == 'no_intersection'
    d = Doc(bounds=(-5, -5, 5, 5)).function('f', op('-', X, n(15))).function('g', n(0))
    assert xy(ev(_ff(d, 1)).elements['p1']) == pytest.approx((15.0, 0.0))


def _fl(d, line, count=2):
    return d.search('intersect.function_line', 'point', 'p', {'function': ref('f'), 'line': ref(line)}, count)


def test_function_line():
    d = Doc().function('f', power(X, 2)).free('A', 0, 1).free('B', 1, 1).line('l', 'A', 'B')
    e = ev(_fl(d, 'l'))
    assert xy(e.elements['p1']) == pytest.approx((-1.0, 1.0), abs=1e-12)
    assert xy(e.elements['p2']) == pytest.approx((1.0, 1.0), abs=1e-12)
    assert run_checks(e, ['on_both']).results == {'op_p:on_both': 'passed'}


def test_function_segment_part_filter():
    d = Doc().function('f', power(X, 2)).free('A', 0, 1).free('B', 5, 1).segment('s', 'A', 'B')
    e = ev(_fl(d, 's'))
    assert e.elements['p1']['reason'] == 'outside_part'
    assert xy(e.elements['p2']) == pytest.approx((1.0, 1.0), abs=1e-12)


def test_function_vertical_line():
    d = Doc().function('f', power(X, 2)).free('A', 2, 0).free('B', 2, 1).line('l', 'A', 'B')
    e = ev(_fl(d, 'l'))
    assert xy(e.elements['p1']) == pytest.approx((2.0, 4.0))
    assert e.elements['p2']['reason'] == 'branch_absent'


def test_function_line_tangent():
    d = Doc().function('f', power(X, 2)).free('A', 0, -1).free('B', 1, 1).line('l', 'A', 'B')
    e = ev(_fl(d, 'l'))
    assert xy(e.elements['p1']) == pytest.approx((1.0, 1.0), abs=1e-7)
    assert e.elements['p1']['detail'] == {'multiplicity': 2}


# ── point.on_function ─────────────────────────────────────────────────────

def _on(d, x):
    d.op('op_P', 'point.on_function', {'function': ref('f')}, [('point', 'P', 'point')])
    d.doc['inputs']['P'] = {'kind': 'pathParameter', 'value': x}
    return d


def test_point_on_function():
    e = ev(_on(Doc().function('f', power(X, 2)), 2.0))
    assert xy(e.elements['P']) == (2.0, 4.0)
    assert run_checks(e).results == {'op_P:on_graph': 'passed'}


def test_point_on_function_clamps_to_domain():
    e = ev(_on(Doc().function('f', power(X, 2), lo=-1, hi=1), 3.0))
    assert xy(e.elements['P']) == (1.0, 1.0)


def test_point_on_function_out_of_domain():
    rec = ev(_on(Doc().function('f', fn('sqrt', X)), -1.0)).elements['P']
    assert (rec['state'], rec['reason']) == ('undefined', 'out_of_domain')


def test_point_on_function_moves_with_input():
    d = _on(Doc().function('f', power(X, 2)), 0.0)
    assert xy(native.evaluate(d.doc, inputs={'P': {'kind': 'pathParameter', 'value': -3.0}}).elements['P']) == \
        (-3.0, 9.0)


# ── sampling ──────────────────────────────────────────────────────────────

def _value(ast, lo=None, hi=None):
    return {'expr': ast, 'refs': [], 'domain': [lo, hi]}


def test_samples():
    pts = function_samples(_value(power(X, 2), lo=0.0), [-4, -4, 4, 4])
    assert len(pts) == 33 and pts[0] == [0.0, 0.0] and pts[-1] == [4.0, 16.0]
    assert function_samples(_value(X, lo=10.0), [-4, -4, 4, 4]) == []
    holes = function_samples(_value(op('/', n(1), X)), [-4, -4, 4, 4])
    assert holes[16] == [0.0, None]


def test_runs_break_at_a_pole_and_a_jump():
    runs = function_runs(_value(op('/', n(1), X)), (-4, 4), (-4, 4))
    assert len(runs) == 2
    assert max(p[0] for p in runs[0]) < 0 < min(p[0] for p in runs[1])
    jump = function_runs(_value({'if': [cmp('<', X, n(0.3)), n(-1), n(1)]}), (-4, 4), (-4, 4))
    assert len(jump) == 2
    assert all(p[1] == -1 for p in jump[0]) and all(p[1] == 1 for p in jump[1])


def test_runs_clip_to_the_window():
    runs = function_runs(_value(power(X, 2)), (-4, 4), (-1, 1))
    ys = [p[1] for run in runs for p in run]
    assert max(ys) <= 3.0 + 1e-12 and len(runs) == 1
    smooth = function_runs(_value(fn('sin', X)), (-4, 4), (-2, 2))
    assert len(smooth) == 1 and smooth[0][0][0] == -4 and smooth[0][-1][0] == 4


@pytest.mark.parametrize('ast, x_range, y_range', [
    (fn('sin', X), (-3.7, 5.3), (-2.1, 3.3)),
    (fn('sin', X), (-10, 10), (-6, 6)),
    (fn('cos', op('*', n(3), X)), (-4, 4), (-4, 4)),
    (op('/', power(X, 3), n(7)), (-4, 4), (-4, 4)),
    (op('/', power(X, 3), n(7)), (-1.3, 2.9), (-1.1, 1.7)),
])
def test_runs_of_a_smooth_graph_are_one_run(ast, x_range, y_range):
    # A graph inside the widened window over the whole x-range is one
    # polyline: each run is drawn on its own and a dash restarts at its start.
    runs = function_runs(_value(ast), x_range, y_range)
    assert len(runs) == 1
    assert runs[0][0][0] == x_range[0] and runs[0][-1][0] == x_range[1]


@pytest.mark.parametrize('hi', [2.9, 1.3, 0.7, 2.1, 1.7])
def test_runs_reach_the_end_of_the_domain(hi):
    runs = function_runs(_value(fn('sin', X), hi=hi), (-4, 5), (-2, 2))
    assert len(runs) == 1 and runs[0][0][0] == -4 and runs[0][-1] == (hi, math.sin(hi))


def test_runs_of_a_graph_that_leaves_the_window_end_at_its_edge():
    runs = function_runs(_value(fn('tan', X)), (-4, 4), (-1, 1))
    assert len(runs) == 3                  # three branches between the poles ±π/2
    for run in runs:
        assert all(-3.0 - 1e-12 <= y <= 3.0 + 1e-12 for _x, y in run)
        assert abs(run[-1][1] - 3.0) < 1e-12 or run[-1][0] == 4


def test_runs_respect_domain_and_gaps():
    runs = function_runs(_value(fn('sqrt', X)), (-4, 4), (-4, 4))
    assert len(runs) == 1 and runs[0][0][0] >= 0
    assert function_runs(_value(X, lo=10.0), (-4, 4), (-4, 4)) == []


# ── the classic bridge, drawing, «Команды», steps ─────────────────────────

def _plot_doc():
    d = Doc(bounds=(-4, -4, 4, 4)).function('f', op('/', n(1), X)).function('g', fn('sin', X), lo=-3, hi=3)
    d.free('A', -3, -1).free('B', 3, 1).line('l', 'A', 'B')
    _fl(d, 'l', 1)
    return _on(d, 0.5)


def test_bridge_identity():
    from animageo.native.kernel.bridge import build_construction, from_classic
    d = _plot_doc()
    construction, names = build_construction(d.doc)
    construction.rebuild(full=True)
    e = ev(d)
    for el_id in ('f', 'g', 'p1', 'P'):
        data = construction.element(names.by_id[el_id]).data
        rec = e.elements[el_id]
        assert from_classic(rec['type'], data) == rec['value'], el_id
    f = construction.element(names.by_id['f']).data
    assert math.isnan(f(0.0)) and f(2.0) == 0.5


def test_bridge_moves_the_point_on_a_function():
    from animageo.native.kernel.bridge import build_construction, from_classic
    construction, names = build_construction(_plot_doc().doc, inputs={'P': {'kind': 'pathParameter', 'value': 2.0}})
    construction.rebuild(full=True)
    assert from_classic('point', construction.element(names.by_id['P']).data) == {'x': 2.0, 'y': 0.5}


def _render(doc, tmp_path, name, fmt='svg'):
    pytest.importorskip('manim')
    native.render(doc, out=tmp_path / f'{name}.{fmt}', fmt=fmt, report=False)
    return (tmp_path / f'{name}.{fmt}').read_bytes()


@pytest.mark.manim
def test_functions_are_drawn(tmp_path):
    d = _plot_doc()
    plain = Doc(bounds=(-4, -4, 4, 4)).free('A', -3, -1).free('B', 3, 1).line('l', 'A', 'B')
    svg = _render(d.doc, tmp_path, 'plot')
    base = _render(plain.doc, tmp_path, 'base')
    assert svg.count(b'<path') >= base.count(b'<path') + 3        # two branches of 1/x, sin, the points
    tikz = _render(d.doc, tmp_path, 'plot', fmt='tikz').decode()
    assert tikz.count('plot coordinates') >= 3


def test_commands_print_functions_with_a_warning():
    from animageo.native.commands import print_commands
    result = print_commands(_plot_doc().doc)
    warnings = [i for i in result.issues if i.code == 'unprintable_operation']
    assert warnings and all('будут позже' in i.message for i in warnings)


def test_steps_describe_functions():
    d = Doc().function('f', op('-', power(X, 2), n(2))).roots('r', 'f', -3, 3, count=2)
    assert 'нули r1, r2 функции f' in '\n'.join(native.describe(d.doc))


def test_a_search_that_finds_nothing_has_no_checks():
    """As in 2D, an operation with no defined output has nothing to check."""
    e = ev(Doc().function('f', op('+', power(X, 2), n(1))).roots('r', 'f', -1, 2, count=2))
    assert run_checks(e).results == {}
    d = Doc().function('f', power(X, 2)).free('A', 0.5, 2).free('B', 0.5, 2).segment('s', 'A', 'B')
    e = ev(_fl(d, 's'))
    assert e.elements['p1']['reason'] == 'zero_length' and 'op_p:on_both' not in run_checks(e).results
