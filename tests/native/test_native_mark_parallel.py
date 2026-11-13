"""Registry 1.8: ``mark.parallel`` — the op, its check, validation, steps
and commands (docs/native/ops/mark.parallel.md)."""
import pytest

from animageo import native
from animageo.native.conditions.statements import mark_statements
from animageo.native.kernel.ops.mark import parallel_directions
from tests.native.conftest import DocBuilder, num, point_input, ref_list


def base(**marks):
    b = DocBuilder('par', registry_version='1.8', bounds=(-6, -4, 8, 7))
    for name, (x, y) in dict(A=(0, 0), B=(4, 1), C=(-1, 3), D=(3, 4), E=(-2, -2), F=(2, -1),
                             G=(1, 5), H=(5, 6)).items():
        b.free(name, x, y)
    b.segment('s', 'A', 'B').segment('t', 'C', 'D')
    b.two('vector.by_points', 'v', 'D', 'C', 'vector')
    b.two('line.by_points', 'l', 'E', 'F', 'line')
    b.two('ray.by_points', 'r', 'H', 'G', 'ray', slots=('origin', 'through'))
    for name, (items, count) in marks.items():
        args = {'lines': ref_list(*items)}
        if count is not None:
            args['count'] = num(count)
        b.op('op_' + name, 'mark.parallel', args, [('mark', name, 'mark')])
    return b


def results(doc, inputs=None):
    return native.check(doc, inputs=inputs).results


def test_value_and_count():
    b = base(m=(('s', 't'), None), n=(('s', 't'), 3), bad=(('s', 't'), 2.5), zero=(('s', 't'), 0))
    elements = native.evaluate(b.doc).elements
    assert elements['m']['value'] == {'kind': 'parallel', 'count': 1}
    assert elements['n']['value'] == {'kind': 'parallel', 'count': 3}
    for name in ('bad', 'zero'):
        assert elements[name] == {'state': 'undefined', 'type': 'mark', 'reason': 'invalid_parameter'}


def test_every_straight_type_and_a_polygon_side():
    b = base(m=(('s', 'v', 'l', 'r'), 2))
    b.op('op_q', 'polygon.by_points', {'vertices': ref_list('A', 'B', 'D', 'C')},
         [('polygon', 'q', 'polygon'), ('side.1', 'q1', 'segment'), ('side.3', 'q3', 'segment')])
    b.op('op_k', 'mark.parallel', {'lines': ref_list('q1', 'q3')}, [('mark', 'k', 'mark')])
    assert [i for i in native.validate(b.doc) if i.severity == 'error'] == []
    checks = results(b.doc)
    assert checks['op_m:parallel'] == 'passed' and checks['op_k:parallel'] == 'passed'
    checks = results(b.doc, {'D': point_input(3, 5), 'F': point_input(2, 0)})
    assert checks['op_m:parallel'] == 'failed' and checks['op_k:parallel'] == 'failed'


def test_zero_length_is_inconclusive_and_the_mark_stays():
    b = base(m=(('s', 't'), None))
    inputs = {'D': point_input(-1, 3)}
    assert results(b.doc, inputs)['op_m:parallel'] == 'inconclusive'
    assert native.evaluate(b.doc, inputs=inputs).elements['m']['state'] == 'defined'


def test_a_point_or_a_circle_is_not_straight():
    b = base(m=(('s', 'A'), None))
    assert any(i.severity == 'error' for i in native.validate(b.doc))


def test_one_line_is_not_enough():
    b = base(m=(('s',), None))
    assert any(i.severity == 'error' for i in native.validate(b.doc))


def test_needs_registry_18():
    b = base(m=(('s', 't'), None))
    b.doc['operationRegistryVersion'] = '1.7'
    assert 'needs_newer_registry' in {i.code for i in native.validate(b.doc)}
    b.doc['operationRegistryVersion'] = '1.8'
    assert native.min_registry_version(b.doc) == '1.8'


def test_directions_follow_the_first_line():
    seg = lambda a, b: ('segment', {'a': list(a), 'b': list(b)})        # noqa: E731
    items = [seg((0, 0), (4, 1)), seg((3, 4), (-1, 3)), ('line', {'p': [0, 0], 'dir': [0.97, 0.24]}),
             ('ray', {'origin': [0, 0], 'dir': [-0.97, -0.24]}), ('vector', {'a': [1, 1], 'b': [5, 2]})]
    assert parallel_directions(items) == ['forward', 'backward', 'forward', 'backward', 'forward']
    # a first line of no length or undefined gives way to the next one
    assert parallel_directions([seg((1, 1), (1, 1)), ('segment', None), seg((0, 0), (-1, 0)),
                                seg((0, 0), (2, 0))]) == ['forward', 'forward', 'forward', 'backward']


@pytest.mark.parametrize('overrides, bad', [
    ({'stroke': '#9933cc', 'parallel_count': 0, 'parallel_direction': 'backward'}, None),
    ({'stroke': 'red'}, 'stroke'),
    ({'parallel_count': 4}, 'parallel_count'),
    ({'parallel_count': True}, 'parallel_count'),
    ({'parallel_direction': 'up'}, 'parallel_direction'),
])
def test_appearance_overrides_are_typed(overrides, bad):
    b = base(m=(('s', 't'), None))
    b.doc['appearance'] = {'m': {'overrides': overrides}}
    paths = [i.path for i in native.validate(b.doc) if i.severity == 'error']
    assert paths == ([] if bad is None else ['/appearance/m/overrides/' + bad])


def test_suppressed_mark_kind_parallel_is_known():
    from animageo.native.document import MARK_KINDS
    assert 'parallel' in MARK_KINDS


def test_statements_and_steps():
    b = base(m=(('s', 't', 'l'), 2))
    doc = native.load(b.doc)
    assert mark_statements(doc, 'op_m') == [{'kind': 'parallel', 'a': {'ref': 's'}, 'b': {'ref': 't'}},
                                           {'kind': 'parallel', 'a': {'ref': 's'}, 'b': {'ref': 'l'}}]
    lines = native.describe(b.doc)
    assert '6. Отмечаем параллельные s, t и l.' in lines, lines


def test_command_pairs_become_segments():
    result = native.parse_commands('A = (0, 0)\nB = (4, 1)\nC = (-1, 3)\nD = (3, 4)\n'
                                   'ОтметкаПараллельных(AB, CD, 2)')
    ops = [op for op in result.document.data['operations'].values()]
    helpers = [op['op'] for op in ops if op['op'] not in ('point.free', 'mark.parallel')]
    assert helpers == ['segment.by_points', 'segment.by_points']
    mark = next(op for op in ops if op['op'] == 'mark.parallel')
    assert mark['args']['count'] == {'kind': 'number', 'value': 2.0}
    assert result.document.data['operationRegistryVersion'] == '1.8'
