"""Independent graph checks, legacy behavior and point/number output smoke."""
import pytest

from animageo import native
from animageo.native.kernel.checks import CHECKS
from animageo.native.kernel.numeric import tolerances
from animageo.native.kernel.values import Input
from tests.native.conftest import num, ref
from tests.native.function_analysis_helpers import Doc, X, n, o, power, fn


def test_general_root_checks_use_the_analytic_ast_slope():
    value = {'expr': fn('atan', o('*', n(1e100), X)), 'refs': [], 'domain': [None, None]}
    args = {'function': Input('function', value)}
    error = CHECKS[('function.roots_interval', 'on_graph')](args, {'root.1': {'x': 0, 'y': 1}}, tolerances(1))
    assert error == pytest.approx(1e-100, rel=1e-12, abs=0)


def test_legacy_root_and_extremum_keep_their_original_details():
    d = Doc().function(power(X, 2)).interval(count=2, a=-1, b=1)
    args = {'function': ref('f'), 'a': num(-1), 'b': num(1), 'count': num(2)}
    d.op('op_old_roots', 'function.root', args,
         [('root.1', 'Old1', 'point'), ('root.2', 'Old2', 'point')])
    d.op('op_old_extremum', 'function.extremum', dict(args, count=num(1)),
         [('extremum.1', 'OldExt', 'point')])
    ev = native.evaluate(d.doc)
    assert ev.elements['P1']['detail'] == {'found': 1}
    assert ev.elements['P2']['reason'] == 'branch_absent'
    for key in ('Old1', 'Old2'):
        assert ev.elements[key]['value'] == {'x': 0, 'y': 0}
        assert ev.elements[key]['detail'] == {'multiplicity': 2}
    assert ev.elements['OldExt']['detail'] == {'kind': 'min'}


def output_doc():
    d = Doc('function_analysis_output').number('k', 1).function(o('-', power(X, 2), {'ref': 0}), 'k')
    d.interval(a=-3, b=3, count=2)
    d.op('op_ext', 'function.extrema_interval', {'function': ref('f'), 'a': num(-3), 'b': num(3), 'count': num(1)},
         [('extremum.1', 'Ext', 'point')])
    d.op('op_value', 'function.value', {'function': ref('f'), 'x': num(2)}, [('number', 'v', 'number')])
    d.op('op_label', 'text.free', {'text': {'kind': 'template', 'value': 'v={0}'}, 'anchor': ref('Ext'),
                                  'refs': {'kind': 'list', 'items': [ref('v')]}}, [('text', 'Label', 'text')])
    return d.doc


@pytest.mark.parametrize('k', [1, 4])
def test_point_and_scalar_analysis_values_cross_the_classic_bridge(k):
    from animageo.native.kernel import bridge

    doc = output_doc()
    construction, names = bridge.build_construction(doc, inputs={'k': num(k)})
    construction.rebuild(full=True)
    want = {'P1': {'x': -(k ** .5), 'y': 0}, 'P2': {'x': k ** .5, 'y': 0},
            'Ext': {'x': 0, 'y': -k}, 'v': {'value': 4 - k, 'unit': 'scalar'}}
    for key, value in want.items():
        data = construction.objectByName(names.by_id[key]).data
        got = bridge.from_classic(doc['elements'][key]['type'], data)
        assert got == value
    assert native.evaluate(doc, inputs={'k': num(k)}).elements['Label']['value']['text'] == f'v={4 - k}'


@pytest.mark.manim
def test_analysis_points_labels_and_numeric_text_export_after_input_change(tmp_path):
    pytest.importorskip('manim')
    doc = output_doc()
    path = tmp_path / 'function_analysis.svg'
    result = native.render(doc, inputs={'k': num(4)}, fmt='svg', out=path)
    assert result.fmt == 'svg'
    svg = path.read_text()
    assert '<svg' in svg and '<path' in svg
    assert native.evaluate(doc, inputs={'k': num(4)}).elements['Label']['value']['text'] == 'v=0'
