"""The area between two graphs, a graph and a line or the x-axis, registry 1.9
(docs/native/ops/function.area_between.md, docs/native/kernel.md §16)."""
import math

import pytest

from animageo import native
from animageo.native.kernel import region as R
from animageo.native.kernel.checks import run_checks
from animageo.native.registry import registry
from tests.native.conftest import DocBuilder, num, ref

X = {'var': 'x'}


def n(v):
    return {'num': v}


def op(name, *args):
    return {'op': name, 'args': list(args)}


def fn(name, *args):
    return {'fn': name, 'args': list(args)}


def poly(*coeffs):
    """``c0 + c1·x + c2·x² + …`` as an AST."""
    tree = n(coeffs[0])
    for k, c in enumerate(coeffs[1:], start=1):
        if c:
            tree = op('+', tree, op('*', n(c), op('^', X, n(k)) if k > 1 else X))
    return tree


class Doc(DocBuilder):
    def __init__(self, bounds=(-10, -10, 10, 10)):
        super().__init__('area', bounds, registry_version='1.9')

    def function(self, el_id, ast, lo=None, hi=None):
        args = {'expr': {'kind': 'expr', 'ast': ast}, 'refs': {'kind': 'list', 'items': []}}
        if lo is not None:
            args['min'] = num(lo)
        if hi is not None:
            args['max'] = num(hi)
        return self.op('op_' + el_id, 'function.expr', args, [('function', el_id, 'function')])

    def area(self, el_id, first, second=None, a=None, b=None, lobe=None):
        args = {'first': ref(first)}
        if second is not None:
            args['second'] = ref(second)
        for slot, v in (('a', a), ('b', b)):
            if v is not None:
                args[slot] = num(v) if isinstance(v, (int, float)) else ref(v)
        if lobe is not None:
            args['lobe'] = num(lobe)
        return self.op('op_' + el_id, 'function.area_between', args, [('region', el_id, 'region')])


def region_of(doc, el_id='S'):
    e = native.evaluate(doc.doc)
    return e, e.elements[el_id]


def defined(doc, el_id='S'):
    e, rec = region_of(doc, el_id)
    assert rec['state'] == 'defined', rec
    return e, rec['value']


def signed(ring, kinds):
    total = 0.0
    for piece, (kind, _source) in zip(ring, kinds):
        if kind == 'line':
            total += R.line_area(*piece)
        elif kind in ('ccw', 'cw'):
            total += R.arc_area(piece, kind)
        else:
            total += sum(-(b[0] - a[0]) * (a[1] + b[1]) / 2 for a, b in zip(piece, piece[1:]))
    return total


def assert_closed(value):
    for ring in value['rings']:
        for here, there in zip(ring, ring[1:] + ring[:1]):
            assert here[-1 if len(here) != 3 else 1] == there[0]


def test_record():
    rec = registry().get('function.area_between')
    assert rec['since'] == '1.9' and rec['status'] == 'beta'
    assert [i['type'] for i in rec['inputs']] == ['function', 'graph_bound', 'limit', 'limit']
    assert rec['outputs'] == [{'slot': 'region', 'type': 'region'}]


def test_parabola_and_the_axis_lobe():
    d = Doc().function('f', poly(1, 0, -1)).area('S', 'f')
    e, v = defined(d)
    assert v['area'] == pytest.approx(4 / 3, abs=1e-12)
    assert v['shape'] == [[['line', 'axis'], ['graph', 'first']]]
    axis, graph = v['rings'][0]
    assert axis[0][0] == pytest.approx(-1.0) and axis[1][0] == pytest.approx(1.0)
    assert axis[0][1] == pytest.approx(0.0, abs=1e-12) and axis[1][1] == pytest.approx(0.0, abs=1e-12)
    assert len(graph) == R.GRAPH_STEPS + 1
    assert graph[0][0] == axis[1][0] and graph[-1][0] == axis[0][0]
    assert_closed(v)
    assert signed(v['rings'][0], v['shape'][0]) > 0
    assert run_checks(e).results == {'op_S:on_both': 'passed'}


def test_two_graphs():
    d = Doc().function('f', X).function('g', poly(0, 0, 1)).area('S', 'f', 'g')
    e, v = defined(d)
    assert v['area'] == pytest.approx(1 / 6, abs=1e-12)
    assert v['shape'] == [[['graph', 'second'], ['graph', 'first']]]
    assert_closed(v)
    assert run_checks(e).ok


def test_graph_and_a_line():
    d = Doc().function('f', poly(0, 0, 1)).free('P', 0, 1).free('Q', 3, 1).line('l', 'P', 'Q').area('S', 'f', 'l')
    e, v = defined(d)
    assert v['area'] == pytest.approx(4 / 3, abs=1e-12)
    assert v['shape'] == [[['graph', 'first'], ['line', 'second']]]
    assert_closed(v)
    assert run_checks(e).ok


def test_vertical_line_is_out_of_domain():
    d = Doc().function('f', poly(0, 0, 1)).free('P', 1, 0).free('Q', 1, 3).line('l', 'P', 'Q').area('S', 'f', 'l')
    _e, rec = region_of(d)
    assert rec['state'] == 'undefined' and rec['reason'] == 'out_of_domain'
    assert rec['detail'] == {'slot': 'second'}


def test_explicit_limits_cut_at_the_root():
    d = Doc().function('f', X).area('S', 'f', a=2, b=-1)
    e, v = defined(d)
    assert v['area'] == pytest.approx(2.5, abs=1e-12)
    assert v['shape'] == [
        [['graph', 'first'], ['line', 'axis'], ['line', 'limit']],
        [['line', 'axis'], ['line', 'limit'], ['graph', 'first']],
    ]
    assert_closed(v)
    for ring, kinds in zip(v['rings'], v['shape']):
        assert signed(ring, kinds) > 0
    assert run_checks(e).ok


def test_limits_are_points():
    d = Doc().function('f', poly(1, 0, -1)).free('A', -1, 5).free('B', 1, -3).area('S', 'f', a='A', b='B')
    _e, v = defined(d)
    assert v['area'] == pytest.approx(4 / 3, abs=1e-12)
    assert v['shape'] == [[['line', 'axis'], ['graph', 'first']]]       # the limits are roots: no edges


def test_second_lobe():
    cubic = poly(0, -1, 0, 1)                                            # x³ − x
    _e, v1 = defined(Doc().function('f', cubic).area('S', 'f'))
    _e, v2 = defined(Doc().function('f', cubic).area('S', 'f', lobe=2))
    assert v1['area'] == pytest.approx(0.25, abs=1e-12)
    assert v2['area'] == pytest.approx(0.25, abs=1e-12)
    assert v1['shape'] == [[['line', 'axis'], ['graph', 'first']]]      # above the axis
    assert v2['shape'] == [[['graph', 'first'], ['line', 'axis']]]      # below it
    assert v1['rings'][0][0][0][0] == pytest.approx(-1.0) and v2['rings'][0][0][0][0] == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize('build, reason', [
    (lambda d: d.function('f', poly(1, 0, 1)).area('S', 'f'), 'no_root_in_window'),
    (lambda d: d.function('f', X).area('S', 'f'), 'branch_absent'),
    (lambda d: d.function('f', poly(0, -1, 0, 1)).area('S', 'f', lobe=3), 'branch_absent'),
    (lambda d: d.function('f', X).function('g', X).area('S', 'f', 'g'), 'coincident'),
    (lambda d: d.function('f', X).area('S', 'f', a=1, b=1), 'empty_range'),
    (lambda d: d.function('f', X).area('S', 'f', a=0, b=1, lobe=1), 'invalid_parameter'),
    (lambda d: d.function('f', poly(1, 0, -1)).area('S', 'f', lobe=0.5), 'invalid_parameter'),
    (lambda d: d.function('f', fn('sqrt', X)).area('S', 'f', a=-1, b=1), 'out_of_domain'),
    (lambda d: d.function('f', X, lo=0, hi=1).area('S', 'f', a=0, b=2), 'out_of_domain'),
    (lambda d: d.function('f', {'if': [{'cmp': '<', 'args': [X, n(0)]}, n(1), n(2)]}).area('S', 'f', a=-1, b=1),
     'discontinuous'),
    (lambda d: d.function('f', op('/', n(1), X)).area('S', 'f', a=-1, b=2), 'discontinuous'),
    (lambda d: d.function('f', fn('tan', X)).area('S', 'f', a=1, b=2), 'discontinuous'),
])
def test_undefined(build, reason):
    _e, rec = region_of(build(Doc()))
    assert rec['state'] == 'undefined', rec
    assert rec['reason'] == reason, rec


def test_out_of_domain_names_the_slot():
    d = Doc().function('f', X).function('g', fn('sqrt', X)).area('S', 'f', 'g', a=-1, b=1)
    _e, rec = region_of(d)
    assert rec['reason'] == 'out_of_domain' and rec['detail'] == {'slot': 'second'}


def test_domain_end_within_tolerance_is_cut():
    d = Doc().function('f', X, lo=0, hi=1).area('S', 'f', a=0, b=1)
    _e, v = defined(d)
    assert v['area'] == pytest.approx(0.5, abs=1e-12)


def test_steep_smooth_graph_is_continuous():
    d = Doc().function('f', fn('exp', op('*', n(5), X))).area('S', 'f', a=-1, b=1)
    _e, v = defined(d)
    assert v['area'] == pytest.approx((math.exp(5) - math.exp(-5)) / 5, rel=1e-8)     # Simpson on 256 cells


def _step(left, middle, right):
    """``if(x < 0, left, if(x > 0, right, middle))``."""
    return {'if': [{'cmp': '<', 'args': [X, n(0)]}, n(left),
                   {'if': [{'cmp': '>', 'args': [X, n(0)]}, n(right), n(middle)]}]}


def test_a_step_through_its_middle_value_is_discontinuous():
    # the node x = 0 holds the middle value: two neighbouring cells jump by 1 each,
    # a plateau of |Δu| that no strict maximum finds
    _e, rec = region_of(Doc().function('f', _step(-1, 0, 1)).area('S', 'f', a=-1, b=1))
    assert (rec['state'], rec['reason'], rec['detail']) == ('undefined', 'discontinuous', {'slot': 'first'}), rec
    _e, v = defined(Doc().function('f', _step(-1, 0, 1)).area('S', 'f', a=0.5, b=1))
    assert v['area'] == pytest.approx(0.5, abs=1e-12)


class _Log:
    """The decisions of :func:`continuity`, with the tolerances of scale 1."""

    def __init__(self):
        from animageo.native.kernel.numeric import tolerances
        self.tol = tolerances(1.0)
        self.decisions = []

    def decide(self, name, value, tol):
        self.decisions.append((name, value))


def _checked(u, lo=-1.0, hi=1.0):
    """``(result, cells checked)`` of the continuity test of ``u`` on ``[lo, hi]``."""
    from animageo.native.kernel.ops.area import continuity
    log = _Log()
    result = continuity(u, lo, hi, log, 'first')
    return result, len([1 for name, _v in log.decisions if name == 'jump'])


@pytest.mark.parametrize('u, most', [
    (lambda x: 2.0, 1),                     # one plateau of zeros, no neighbour: one cell
    (lambda x: x, 1),                       # every |Δu| equal: one plateau, one cell
    (lambda x: 3 * x - 0.25, 1),
    (lambda x: x * x, 2),                   # |Δu| falls to the vertex and rises: the two ends
    (lambda x: math.sin(3 * x), 8),
])
def test_smooth_graphs_check_few_cells(u, most):
    result, checked = _checked(u)
    assert result is None
    assert 1 <= checked <= most, checked


def test_plateau_of_a_step_is_checked_once():
    from animageo.native.kernel.ops.area import suspect_cells
    assert suspect_cells([0, 0, 1, 1, 0, 0]) == [2]
    assert suspect_cells([1, 1, 1]) == [0]
    assert suspect_cells([0, 2, 1, 2, 0]) == [1, 3]           # a single cell: the strict maximum as before
    assert suspect_cells([0, 1, 1, 2, 0]) == [3]              # a plateau below a higher cell is no maximum
    result, checked = _checked(lambda x: -1.0 if x < 0 else 1.0 if x > 0 else 0.0)
    assert result is not None and result.reason == 'discontinuous' and checked == 1


def test_large_coordinates():
    # −(x − 1000)(x − 1002): a lobe of width 2 far from the origin
    shift = op('-', X, n(1001))
    tree = op('-', n(1), op('^', shift, n(2)))
    d = Doc(bounds=(990, -10, 1010, 10)).function('f', tree).area('S', 'f')
    e, v = defined(d)
    assert v['area'] == pytest.approx(4 / 3, rel=1e-9)
    assert run_checks(e).ok


def test_a_tangent_with_limits_gives_two_lobes():
    d = Doc().function('f', poly(0, 0, 1)).area('S', 'f', a=-1, b=1)
    _e, v = defined(d)
    assert len(v['rings']) == 2
    assert v['area'] == pytest.approx(2 / 3, abs=1e-12)


def test_a_tangent_lobe_is_empty():
    # x² touches the axis once: no finite lobe
    _e, rec = region_of(Doc().function('f', poly(0, 0, 1)).area('S', 'f'))
    assert rec['reason'] == 'branch_absent'


def test_lobe_is_a_param_absent_with_limits():
    rec = registry().get('function.area_between')
    assert rec['inputSets'] == [['first', 'a', 'b'], ['first', 'second', 'a', 'b'], ['first'], ['first', 'second']]
    assert [p['slot'] for p in rec['params']] == ['lobe']


def test_zero_lobes_are_dropped():
    # max(x, 0): h ≡ 0 left of 0, every grid node there is a root
    d = Doc().function('f', fn('max', X, n(0))).area('S', 'f', a=-1, b=1)
    _e, v = defined(d)
    assert len(v['rings']) == 1 and v['area'] == pytest.approx(0.5, abs=1e-12)


def test_too_many_lobes_is_an_error():
    d = Doc().function('f', fn('sin', op('*', n(10), X))).area('S', 'f', a=0.1, b=21)
    _e, rec = region_of(d)
    assert rec['state'] == 'error' and rec['reason'] == 'limit_exceeded', rec


# ── measure.area and measure.perimeter of a region ────────────────────────

def _measured(doc):
    doc.op('op_a', 'measure.area', {'of': ref('S')}, [('number', 'a', 'number')])
    doc.op('op_p', 'measure.perimeter', {'of': ref('S')}, [('number', 'p', 'number')])
    e = native.evaluate(doc.doc)
    return e.elements['S'], e.elements['a'], e.elements['p']


def test_measures_of_a_region():
    s, a, p = _measured(Doc().function('f', poly(1, 0, -1)).area('S', 'f'))
    assert a['state'] == 'defined' and a['value'] == {'value': s['value']['area'], 'unit': 'area'}
    assert p['value']['unit'] == 'length'
    assert p['value']['value'] == pytest.approx(2 + 2 * 1.4789428575445975, rel=1e-5)
    assert p['value']['value'] == R.perimeter(s['value'])


def test_measures_of_an_undefined_region_are_upstream():
    _s, a, p = _measured(Doc().function('f', poly(1, 0, 1)).area('S', 'f'))
    assert a['reason'] == 'upstream' and p['reason'] == 'upstream'
