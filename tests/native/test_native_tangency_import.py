"""Source tangents preserve live dependencies, saved evidence and output identity."""
import copy
import math

import pytest

from animageo import native
from animageo.native.convert.values import line_coefficients, native_report_value
from tests.native.ggb_synth import command, element, expression, point
from tests.native.test_native_ggb_inline import eid, imported


def number(label, value):
    return element('numeric', label, extra=f'<value val="{value}"/>')


def function(text='x^2', label='f'):
    return expression(label, text, 'function') + element('function', label)


def line(label, coords=None):
    extra = '' if coords is None else '<coords ' + ' '.join(
        f'{k}="{v}"' for k, v in zip(('x', 'y', 'z'), coords)) + '/>'
    return element('line', label, extra=extra)


def conic(text='x^2+4*y^2=4', matrix=(1, 4, -4, 0, 0, 0), label='K'):
    return expression(label, text, 'conic') + element('conic', label, extra='<matrix ' + ' '.join(
        f'A{i}="{v}"' for i, v in enumerate(matrix)) + '/>')


def producer(doc, items, name):
    return doc['operations'][doc['elements'][eid(items, name)]['producer']['operationId']]


def coefficients(ev, items, name):
    state = ev.elements[eid(items, name)]
    assert state['state'] == 'defined', state
    return native_report_value('line', state['value'])['value']


@pytest.mark.parametrize('arg', ['u', 'A', 'u+1', 'x(A)'])
def test_graph_tangent_uses_live_abscissa_and_ignores_point_ordinate(arg):
    x = 2 if arg == 'u+1' else 1
    doc, items = imported(number('u', 1) + point('A', 1., 7.) + function()
                          + command('Tangent', [arg, 'f'], ['t']) + line('t', (-2*x, 1, x*x)))
    assert items['t']['category'] == 'editable' and items['t']['value_check'] == 'passed'
    assert producer(doc, items, 't')['op'] == 'line.tangent_function_at'
    assert doc['operationRegistryVersion'] == '1.12'
    changes = {eid(items, 'u'): {'kind': 'number', 'value': 2},
               eid(items, 'A'): {'kind': 'point', 'value': [2, -100]}}
    ev = native.evaluate(doc, inputs=changes)
    x = 3 if arg == 'u+1' else 2
    assert coefficients(ev, items, 't') == pytest.approx(line_coefficients(-2*x, 1, x*x))
    assert eid(items, 't') not in doc['inputs']


@pytest.mark.parametrize('text,x,coords,reason', [
    ('sqrt(x)', 0, ('-Infinity', 1, 'NaN'), 'not_differentiable'),
    ('1/x', 0, ('Infinity', 1, 'NaN'), 'out_of_domain'),
    ('abs(x)', 0, ('NaN', 1, 'NaN'), 'not_differentiable'),
])
def test_undefined_graph_tangent_is_recovered_from_source_without_classic(text, x, coords, reason):
    doc, items = imported(number('u', x) + function(text) + command('Tangent', ['u', 'f'], ['t']) + line('t', coords))
    assert items['t']['category'] == 'editable'
    assert native.evaluate(doc).elements[eid(items, 't')]['reason'] == reason
    ev = native.evaluate(doc, inputs={eid(items, 'u'): {'kind': 'number', 'value': 1}})
    assert ev.elements[eid(items, 't')]['state'] == 'defined'


def test_normal_and_slope_keep_the_graph_point_tangent_chain():
    body = point('A', 1., 7.) + function() + expression('Q', '(x(A), f(x(A)))', 'point') + point('Q', 1., 1.)
    body += command('Tangent', ['A', 'f'], ['t']) + line('t', (-2, 1, 1))
    body += command('OrthogonalLine', ['Q', 't'], ['n']) + line('n', (1, 2, -3))
    body += command('Slope', ['n'], ['s']) + number('s', -.5)
    doc, items = imported(body)
    assert all(i['category'] == 'editable' for i in items.values())
    assert producer(doc, items, 'n')['args']['base']['elementId'] == eid(items, 't')
    assert producer(doc, items, 'n')['args']['point']['elementId'] == eid(items, 'Q')
    ev = native.evaluate(doc, inputs={eid(items, 'A'): {'kind': 'point', 'value': [0, 99]}})
    assert coefficients(ev, items, 'n') == pytest.approx([1, 0, 0])
    assert ev.elements[eid(items, 's')]['reason'] == 'vertical_line'


@pytest.mark.parametrize('coords', [(1, 0, 0), (0, 1, 0), (-2, 1, 0)])
def test_slope_reads_saved_undefined_and_finite_numbers(coords):
    value = 'NaN' if coords[1] == 0 else -coords[0]/coords[1]
    doc, items = imported(expression('l', f'{coords[0]}*x+{coords[1]}*y=0', 'line') + line('l', coords)
                          + command('Slope', ['l'], ['s']) + number('s', value))
    assert items['s']['category'] == 'editable' and items['s']['value_check'] == 'passed'
    assert producer(doc, items, 's')['op'] == 'line.slope'


def test_group_matching_uses_normalized_lines_and_preserves_ids_after_motion():
    body = point('P', 4., 0.) + conic() + command('Tangent', ['P', 'K'], ['lower', 'upper'])
    body += line('lower', (math.sqrt(3), -6, -4*math.sqrt(3)))
    body += line('upper', (-math.sqrt(3), -6, 4*math.sqrt(3)))
    doc, items = imported(body)
    assert all(i['category'] == 'editable' for i in items.values())
    assert producer(doc, items, 'lower') is producer(doc, items, 'upper')
    assert [doc['elements'][eid(items, n)]['producer']['slot'] for n in ('lower', 'upper')] == ['tangent.2', 'tangent.1']
    ev = native.evaluate(doc, inputs={eid(items, 'P'): {'kind': 'point', 'value': [2, 0]}})
    assert ev.elements[eid(items, 'upper')]['detail'] == {'found': 1}
    assert ev.elements[eid(items, 'lower')]['reason'] == 'branch_absent'
    assert set(ev.elements) == set(doc['elements'])


@pytest.mark.parametrize('sparse', [False, True])
def test_undefined_slots_keep_original_ordinals_and_recover(sparse):
    outputs = ['', 'v'] if sparse else ['u', 'v']
    body = point('P', 0., 0.) + conic() + command('Tangent', ['P', 'K'], outputs)
    body += ''.join(line(n, ('NaN', 'NaN', 'NaN')) for n in outputs if n)
    doc, items = imported(body)
    assert '' not in items and items['v']['category'] == 'editable'
    assert doc['elements'][eid(items, 'v')]['producer']['slot'] == 'tangent.2'
    assert producer(doc, items, 'v')['args']['count']['value'] == 2
    ev = native.evaluate(doc, inputs={eid(items, 'P'): {'kind': 'point', 'value': [4, 0]}})
    assert ev.elements[eid(items, 'v')]['state'] == 'defined'


def test_single_saved_tangent_on_conic_keeps_general_search_semantics():
    doc, items = imported(point('P', 2., 0.) + conic() + command('Tangent', ['P', 'K'], ['t', ''])
                          + line('t', (1, 0, -2)))
    assert items['t']['category'] == 'editable'
    assert producer(doc, items, 't')['op'] == 'line.tangents_from_point_conic'
    ev = native.evaluate(doc, inputs={eid(items, 'P'): {'kind': 'point', 'value': [4, 0]}})
    assert ev.elements[eid(items, 't')]['detail'] == {'found': 2}


@pytest.mark.parametrize('same', [True, False])
def test_saved_multiplicity_and_conflicting_undefined_refuse_group_and_close_dependents(same):
    body = point('P', 2., 0.) + conic() + command('Tangent', ['P', 'K'], ['t', 's'])
    body += line('t', (1, 0, -2)) + line('s', (-2, 0, 4) if same else ('NaN',)*3)
    body += command('OrthogonalLine', ['P', 't'], ['n']) + line('n', (0, 1, 0))
    doc, items = imported(body)
    if same:
        for n in ('t', 's'):
            assert items[n]['native_ids'] == [] and items[n]['reason'] == 'unsupported_signature'
            assert 'multiplicity' in items[n]['detail']
        assert items['n']['category'] == 'closure'
    else:
        assert items['t']['category'] == items['s']['category'] == 'editable'
    assert all(o['op'] != 'line.free' for o in doc['operations'].values())


def test_missing_saved_line_coords_are_not_filled_from_classic():
    doc, items = imported(point('P', 2., 0.) + conic() + command('Tangent', ['P', 'K'], ['t', '']) + line('t'))
    assert items['t']['category'] == 'differs' and items['t']['reason'] == 'value_unchecked'


@pytest.mark.parametrize('circle', [False, True])
def test_parallel_tangents_accept_conic_sections_and_use_live_base(circle):
    curve = conic('x^2+y^2=4', (1, 1, -4, 0, 0, 0)) if circle else conic()
    radius = 2 if circle else 1
    body = curve + point('A', 0., 0.) + point('B', 1., 0.)
    body += command('Line', ['A', 'B'], ['l']) + line('l', (0, 1, 0))
    body += command('Tangent', ['l', 'K'], ['t', 's']) + line('t', (0, 1, -radius)) + line('s', (0, 1, radius))
    doc, items = imported(body)
    assert items['t']['category'] == items['s']['category'] == 'editable'
    assert producer(doc, items, 't')['op'] == 'line.tangents_parallel_conic'
    ev = native.evaluate(doc, inputs={eid(items, 'B'): {'kind': 'point', 'value': [0, 1]}})
    for name in ('t', 's'):
        a, b, c = coefficients(ev, items, name)
        assert abs(a) == pytest.approx(1) and b == pytest.approx(0) and abs(c) == pytest.approx(2)


def test_inline_helpers_are_owned_delete_with_host_and_survive_reload_undo():
    body = point('A', 1., 7.) + number('k', 2) + command('Tangent', ['A', 'k*x^2'], ['t']) + line('t', (-4, 1, 2))
    doc, items = imported(body)
    assert items['t']['category'] == 'editable'
    host = producer(doc, items, 't')['id']
    helpers = set(doc['elements']) - {eid(items, n) for n in items}
    assert len(helpers) == 6
    for h in helpers:
        assert doc['elements'][h]['origin'] == {'kind': 'auto', 'source': host}
        assert doc['appearance'][h]['role'] == 'aux' and not doc['appearance'][h]['visible']
    snapshot = native.dumps(doc)
    reloaded = native.load(snapshot)
    assert native.validate(reloaded) == []
    cleaned, _ = native.delete(reloaded, [eid(items, 't')], mode='operation')
    assert not helpers.intersection(cleaned.elements)
    restored = native.load(snapshot)
    assert native.content_hash(restored) == native.content_hash(doc)
    ev = native.evaluate(restored, inputs={eid(items, 'A'): {'kind': 'point', 'value': [2, -9]}})
    assert coefficients(ev, items, 't') == pytest.approx(line_coefficients(-8, 1, 8))


@pytest.mark.parametrize('code,expected', [
    ('t = Tangent(A,K)', 'line.tangents_from_point_conic'),
    ('t = Tangent(1,f)', 'line.tangent_function_at'),
    ('t = Tangent(A,f)', 'line.tangent_function_at'),
    ('t = Tangent(l,K)', 'line.tangents_parallel_conic'),
    ('t = Slope(l)', 'line.slope'),
    ('t = Tangent(K,A)', 'line.tangents_from_point_conic'),
    ('t = Tangent(K,l)', 'line.tangents_parallel_conic'),
])
def test_existing_dsl_factories_lower_through_map(code, expected):
    from animageo.geo.construction import Construction
    from animageo.parsers import dsl
    from tests.native.test_native_l5_ggb import NS
    c = Construction()
    curve = 'f=Function("x^2")\n' if ',f)' in code else 'K=Conic("x^2+4*y^2=4")\n' if 'K' in code else ''
    dsl.run(c, 'A=Point(4,0)\nB=Point(0,1)\n' + curve + 'l=Line(A,B)\n' + code)
    doc, report = native.from_construction(c, id_namespace=NS)
    assert not report['untranslated']
    ops = [o for o in doc['operations'].values() if o['op'] == expected]
    assert len(ops) == 1 and native.validate(doc) == []
    printed = native.print_commands(doc)
    assert any(i.code == 'unprintable_operation' for i in printed.issues)


def test_tangency_capability_and_strict_native_only_reason():
    from animageo.native.convert.mapping import dsl_map, map_problems
    assert native.has('tangency')
    assert dsl_map().version == 9 and map_problems() == []
    assert 'strict' in dsl_map().ops_without_classic['line.tangent_conic_at']


@pytest.mark.parametrize('text,x', [('x(A+A)', 2), ('x((2,3))', 2), ('x(A)+y(A)', 8)])
def test_coordinate_abscissa_expressions_are_scalar_dependencies(text, x):
    doc, items = imported(point('A', 1., 7.) + function() + command('Tangent', [text, 'f'], ['t'])
                          + line('t', (-2*x, 1, x*x)))
    assert items['t']['category'] == 'editable'
    assert coefficients(native.evaluate(doc), items, 't') == pytest.approx(line_coefficients(-2*x, 1, x*x))


def test_private_abscissa_shared_by_another_tangent_is_adopted_on_delete():
    doc, items = imported(point('A', -2., 7.) + function() + command('Tangent', ['A', 'f'], ['t'])
                          + line('t', (4, 1, 4)))
    host = producer(doc, items, 't')
    shared = copy.deepcopy(host)
    shared.update(id='shared_tangent', outputs=[{'slot': 'line', 'elementId': 'shared_line'}])
    shared.pop('seq', None)
    doc['operations'][shared['id']] = shared
    doc['elements']['shared_line'] = {'id': 'shared_line', 'displayName': 'other', 'type': 'line',
                                     'producer': {'operationId': shared['id'], 'slot': 'line'}}
    assert native.validate(doc) == []
    helpers = {e for e, v in doc['elements'].items() if v.get('origin', {}).get('source') == host['id']}
    cleaned, _ = native.delete(doc, [eid(items, 't')], mode='operation')
    assert helpers <= set(cleaned.elements) and native.validate(cleaned) == []
    assert all(cleaned.elements[h]['origin']['source'] in cleaned.operations for h in helpers)
    assert cleaned.elements[shared['args']['x']['elementId']]['origin']['source'] == shared['id']
    assert native.evaluate(cleaned).elements['shared_line']['state'] == 'defined'
    cleaned, _ = native.delete(cleaned, ['shared_line'], mode='operation')
    assert not helpers.intersection(cleaned.elements)


def test_a_defined_line_can_take_first_rank_while_undefined_sibling_reserves_second():
    body = point('P', 1., 1.) + conic('x^2-y^2=1', (1, -1, -1, 0, 0, 0))
    body += command('Tangent', ['P', 'K'], ['absent', 'finite'])
    doc, items = imported(body + line('absent', ('NaN',)*3) + line('finite', (1, 0, -1)))
    assert items['absent']['category'] == items['finite']['category'] == 'editable'
    assert doc['elements'][eid(items, 'finite')]['producer']['slot'] == 'tangent.1'
    assert doc['elements'][eid(items, 'absent')]['producer']['slot'] == 'tangent.2'


def test_wrong_saved_coefficients_remain_dependent_and_report_a_mismatch():
    doc, items = imported(point('P', 2., 0.) + conic() + command('Tangent', ['P', 'K'], ['t', ''])
                          + line('t', (1, 0, -3)))
    assert items['t']['category'] == 'differs' and items['t']['reason'] == 'value_mismatch'
    assert producer(doc, items, 't')['op'] == 'line.tangents_from_point_conic'


def test_unsupported_curve_causes_honest_tangent_and_normal_closure():
    body = point('A', 1., 7.) + function('gamma(x)')
    body += command('Tangent', ['A', 'f'], ['t']) + line('t', (1, 0, -1))
    body += command('OrthogonalLine', ['A', 't'], ['n']) + line('n', (0, 1, -7))
    _, items = imported(body)
    assert items['t']['category'] == items['n']['category'] == 'closure'
    assert items['t']['native_ids'] == items['n']['native_ids'] == []


@pytest.mark.parametrize('curve,command,expected', [
    ('f=Function("a*x^2")', 't=Tangent(1,f)', 'line.tangent_function_at'),
    ('K=Conic("a*x^2+4*y^2=4")', 't,s=Tangent(A,K)', 'line.tangents_from_point_conic'),
])
def test_dsl_formula_coefficients_remain_live_in_tangent_dependencies(curve, command, expected):
    from animageo.geo.construction import Construction
    from animageo.parsers import dsl
    from tests.native.test_native_l5_ggb import NS
    c = Construction()
    dsl.run(c, 'a=2\nA=Point(4,0)\n' + curve + '\n' + command)
    doc, report = native.from_construction(c, id_namespace=NS)
    assert report['untranslated'] == [] and native.validate(doc) == []
    items = {e['name']: e for e in report['elements']}
    tid, aid = (items[n]['native_ids'][0] for n in ('t', 'a'))
    assert doc['operations'][doc['elements'][tid]['producer']['operationId']]['op'] == expected
    before = native.evaluate(doc).elements[tid]
    after = native.evaluate(doc, inputs={aid: {'kind': 'number', 'value': 1}}).elements[tid]
    assert before['state'] == after['state'] == 'defined' and before['value'] != after['value']


@pytest.mark.parametrize('axis,factory,saved', [
    ('xAxis', 'Slope', number('s', 0)), ('yAxis', 'Slope', number('s', 'NaN')),
    ('xAxis', 'Tangent', line('s', (0, 1, -1))),
    ('yAxis', 'Tangent', line('s', (1, 0, -2))),
], ids=['slope_x_axis', 'slope_y_axis', 'parallel_x_axis', 'parallel_y_axis'])
def test_builtin_axis_line_inputs_use_owned_axis_geometry(axis, factory, saved):
    args = [axis, 'K'] if factory == 'Tangent' else [axis]
    body = conic() + command(factory, args, ['s']) + saved
    doc, items = imported(body)
    assert items['s']['category'] == 'editable' and native.validate(doc) == []
    assert 'xAxis' not in items and 'yAxis' not in items
    helpers = set(doc['elements']) - {eid(items, n) for n in items}
    assert len(helpers) == 3
    cleaned, _ = native.delete(doc, [eid(items, 's')], mode='operation')
    assert not helpers.intersection(cleaned.elements)


def test_dsl_static_function_domain_is_not_discarded():
    from animageo.geo.construction import Construction
    from animageo.parsers import dsl
    from tests.native.test_native_l5_ggb import NS
    c = Construction()
    dsl.run(c, 'f=Function("x^2",0,2)\nt=Tangent(3,f)')
    doc, report = native.from_construction(c, id_namespace=NS)
    items = {e['name']: e for e in report['elements']}
    assert native.evaluate(doc).elements[items['t']['native_ids'][0]]['reason'] == 'out_of_domain'


def test_legacy_inline_point_circle_refusal_remains_unchanged():
    body = point('O', 0., 0.) + command('Circle', ['O', '2'], ['c'])
    body += element('conic', 'c', extra='<matrix A0="1" A1="1" A2="-4" A3="0" A4="0" A5="0"/>')
    body += command('Tangent', ['(4,0)', 'c'], ['t', 's'])
    body += line('t', (1, math.sqrt(12), -4)) + line('s', (1, -math.sqrt(12), -4))
    _, items = imported(body)
    for name in ('t', 's'):
        assert items[name]['reason'] == 'formula_unsupported' and items[name]['native_ids'] == []
