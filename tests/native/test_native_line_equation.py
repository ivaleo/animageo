"""Line equations: direction, numeric dependencies and ordinary line behavior."""
import math

import pytest

from animageo import native
from animageo.native.registry import registry
from tests.native.conftest import DocBuilder, ref_list

X, Y = {'var': 'x'}, {'var': 'y'}


def n(v):
    return {'num': v}


def o(op, *args):
    return {'op': op, 'args': list(args)}


def equation(b, name, ast, *refs):
    return b.op('op_' + name, 'line.equation',
                {'expr': {'kind': 'expr', 'ast': ast}, 'refs': ref_list(*refs)}, [("line", name, "line")])


def doc():
    return DocBuilder('line_equations', registry_version='1.10')


def test_catalog_and_feature():
    rec = registry().get('line.equation')
    assert rec['since'] == '1.10'
    assert rec['stepKind'] == 'line_equation'
    assert rec['undefined'] == ['not_linear', 'degenerate_line', 'upstream']
    assert rec['inputs'][0]['vars'] == ['x', 'y']
    assert native.has('line_equation')


@pytest.mark.parametrize('ast,p,direction', [
    (o('-', Y, o('+', o('*', n(2), X), n(1))), [-.4, .2], [1/math.sqrt(5), 2/math.sqrt(5)]),
    (o('-', X, n(4)), [4, 0], [0, -1]),
    (o('+', Y, n(1)), [0, -1], [1, 0]),
    (o('neg', o('-', X, n(4))), [4, 0], [0, 1]),
])
def test_orientation_and_foot(ast, p, direction):
    b = equation(doc(), 'g', ast)
    assert native.validate(b.doc) == []
    v = native.evaluate(b.doc).elements['g']['value']
    assert v['p'] == pytest.approx(p)
    assert v['dir'] == pytest.approx(direction)


@pytest.mark.parametrize('ast,why', [
    (o('+', o('^', X, n(2)), Y), 'not_linear'),
    ({'fn': 'sqrt', 'args': [X]}, 'not_linear'),
    (o('*', X, Y), 'not_linear'),
    (n(0), 'degenerate_line'), (n(1), 'degenerate_line'),
    (o('+', o('*', n(1e-15), X), n(1)), 'degenerate_line'),
])
def test_reasons(ast, why):
    ev = native.evaluate(equation(doc(), 'g', ast).doc).elements['g']
    assert (ev['state'], ev['reason']) == ('undefined', why)


def test_live_parameters_intersection_and_upstream_recovery():
    b = doc().number('a', 2).number('b', 1)
    equation(b, 'g', o('-', Y, o('+', o('*', {'ref': 0}, X), {'ref': 1})), 'a', 'b')
    b.free('A', 4, 0).free('B', 4, 1).line('h', 'A', 'B').intersect('P', 'g', 'h')
    assert native.evaluate(b.doc).elements['P']['value'] == pytest.approx({'x': 4, 'y': 9})
    assert native.evaluate(b.doc, inputs={'a': {'kind': 'number', 'value': -1}}).elements['P']['value'] == \
        pytest.approx({'x': 4, 'y': -3})
    b.op('op_bad', 'number.expression', {'expr': {'kind': 'expr', 'ast': o('/', n(1), {'ref': 0})},
          'refs': ref_list('a')}, [('number', 'bad', 'number')])
    equation(b, 'k', o('-', Y, {'ref': 0}), 'bad')
    ev = native.evaluate(b.doc, inputs={'a': {'kind': 'number', 'value': 0}})
    assert ev.elements['k']['reason'] == 'upstream'
    assert native.evaluate(b.doc).elements['k']['state'] == 'defined'


def test_scaled_equations():
    for factor in (1e-200, 1e200):
        b = equation(doc(), 'g', o('*', n(factor), o('-', X, n(4))))
        assert native.evaluate(b.doc).elements['g']['value']['p'] == pytest.approx([4, 0])


def test_validation_and_describe():
    b = equation(doc(), 'g', o('-', X, n(4)))
    assert 'g — прямая, заданная уравнением' in str(native.describe(b.doc))
    b.doc['operationRegistryVersion'] = '1.9'
    assert 'needs_newer_registry' in [i.code for i in native.validate(b.doc)]


def test_bridge_labels_and_commands():
    from animageo.native.kernel import bridge
    from animageo.native.commands import parse_commands, print_commands
    b = equation(doc(), 'g', o('-', X, n(4)))
    constr, names = bridge.build_construction(b.doc)
    constr.rebuild(full=True)
    data = constr.objectByName(names.by_id['g']).data
    assert data.__class__.__name__ == 'Line'
    assert bridge.from_classic('line', data) == native.evaluate(b.doc).elements['g']['value']
    b.doc['appearance'] = {'g': {'label': {'visible': True, 'mode': 'name'}}}
    assert native.layout_labels(b.doc, backend='metrics')['g']['text'] == '$g$'
    printed = print_commands(b.doc)
    assert any(i.code == 'unprintable_operation' for i in printed.issues)
    assert parse_commands(printed.text, base=b.doc).document.data == b.doc


@pytest.mark.manim
def test_render_line_equation(tmp_path):
    pytest.importorskip('manim')
    b = equation(doc(), 'g', o('-', X, n(4)))
    b.doc['appearance'] = {'g': {'label': {'visible': False}}}
    native.render(b.doc, out=tmp_path / 'line.svg', fmt='svg', report=False)
    assert b'<path' in (tmp_path / 'line.svg').read_bytes()


def test_line_equation_fixtures_cover_reasons_and_motion():
    from animageo.native import curves_fixtures
    fixtures = curves_fixtures.build_fixtures()
    names = {name + '.json' for name in ('line_eq_slope', 'line_eq_vertical', 'line_eq_param', 'line_eq_kinds')}
    assert names <= fixtures.keys()
    reasons = {rec.get('reason') for name in names for case in fixtures[name]['cases']
               for rec in case['expect'].values()}
    assert {'not_linear', 'degenerate_line', 'upstream'} <= reasons
    for name in names:
        assert curves_fixtures.verify_fixture(fixtures[name]) == []


def test_line_equation_in_a_subnormal_frame():
    b = DocBuilder('tiny_line_frame', bounds=(0, 0, 1e-310, 1e-310), registry_version='1.10')
    equation(b, 'g', X)
    rec = native.evaluate(b.doc).elements['g']
    assert rec['state'] == 'defined', rec
    assert rec['value'] == {'p': [0, 0], 'dir': [0, -1]}
