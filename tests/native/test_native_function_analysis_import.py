"""Source-level function analysis stays live and never falls back to free points."""
import math

import pytest

from animageo import native
from tests.native.ggb_synth import command, element, expression, point
from tests.native.test_native_ggb_inline import eid, imported


def number(name, value):
    return element('numeric', name, extra=f'<value val="{value}"/>')


def function(text='x^2-a', *, label='f'):
    return expression(label, text, 'function') + element('function', label)


def undefined(name):
    return element('point', name, extra='<coords x="NaN" y="NaN" z="NaN"/>')


def producer(doc, items, name):
    return doc['operations'][doc['elements'][eid(items, name)]['producer']['operationId']]


@pytest.mark.parametrize('name,args,outputs,points,op', [
    ('Root', ['f'], ['P', 'Q'], [(-2., 0.), (2., 0.)], 'function.roots_polynomial'),
    ('Root', ['f', 's'], ['P'], [(2., 0.)], 'function.root_near'),
    ('Root', ['f', 'l', 'r'], ['P'], [(2., 0.)], 'function.root_interval'),
    ('Roots', ['f', '-3', '3'], ['P', 'Q'], [(-2., 0.), (2., 0.)], 'function.roots_interval'),
    ('Extremum', ['f'], ['P'], [(0., -4.)], 'function.extrema_polynomial'),
    ('Extremum', ['f', '-3', '3'], ['P'], [(0., -4.)], 'function.extrema_interval'),
])
def test_source_commands_without_classic_handlers_are_live(name, args, outputs, points, op):
    body = number('a', 4.) + number('s', 1.) + number('l', 0.) + number('r', 3.) + function()
    body += command(name, args, outputs) + ''.join(point(n, *p) for n, p in zip(outputs, points))
    doc, items = imported(body)
    assert all(e['category'] == 'editable' and e['value_check'] == 'passed' for e in items.values())
    assert producer(doc, items, 'P')['op'] == op
    assert eid(items, 'P') not in doc['inputs']
    moved = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': 1.}})
    expected = (0., -1.) if name == 'Extremum' else (-1., 0.) if len(outputs) == 2 else (1., 0.)
    assert moved.elements[eid(items, 'P')]['value'] == pytest.approx(dict(zip(('x', 'y'), expected)))


@pytest.mark.parametrize('axis,index,xy,op,slot', [
    ('xAxis', None, (-2., 0.), 'function.roots_polynomial', 'root.1'),
    ('xAxis', '2', (2., 0.), 'function.roots_polynomial', 'root.2'),
    ('xAxis', '3', None, 'function.roots_polynomial', 'root.3'),
    ('yAxis', None, (0., -4.), 'point.expression', 'point'),
    ('yAxis', '1', (0., -4.), 'point.expression', 'point'),
])
@pytest.mark.parametrize('reverse', [False, True])
def test_axis_lowerings_keep_static_index_and_function_identity(axis, index, xy, op, slot, reverse):
    args = [axis, 'f'] if reverse else ['f', axis]
    if index is not None:
        args.append(index)
    body = number('a', 4.) + function() + command('Intersect', args, ['P'])
    doc, items = imported(body + (point('P', *xy) if xy is not None else undefined('P')))
    assert items['P']['category'] == 'editable'
    assert producer(doc, items, 'P')['op'] == op
    assert doc['elements'][eid(items, 'P')]['producer']['slot'] == slot
    assert eid(items, 'f') in str(producer(doc, items, 'P')['args'])


def test_numeric_function_call_and_existing_tuple_keep_distinct_live_inputs():
    body = number('a', 2.) + number('b', 2.) + function('a*x^2')
    body += expression('v', 'f(b+1)') + number('v', 18.)
    body += expression('P', '(b, f(b))', 'point') + point('P', 2., 8.)
    doc, items = imported(body)
    assert all(e['category'] == 'editable' for e in items.values())
    assert producer(doc, items, 'v')['op'] == 'function.value'
    assert producer(doc, items, 'P')['op'] == 'point.expression'
    for changes, value, xy in [({'a': 3.}, 27., (2., 12.)), ({'b': -1.}, 0., (-1., 2.))]:
        ev = native.evaluate(doc, inputs={eid(items, n): {'kind': 'number', 'value': v} for n, v in changes.items()})
        assert ev.elements[eid(items, 'v')]['value']['value'] == pytest.approx(value)
        assert ev.elements[eid(items, 'P')]['value'] == pytest.approx(dict(zip(('x', 'y'), xy)))


def test_reordered_finite_outputs_match_once_and_keep_slots_after_degree_change():
    body = number('a', 4.) + function() + command('Root', ['f'], ['Q', 'P', 'U'])
    doc, items = imported(body + point('Q', 2., 0.) + point('P', -2., 0.) + undefined('U'))
    op = producer(doc, items, 'P')
    assert op is producer(doc, items, 'Q') and op['args']['count']['value'] == 3
    assert [doc['elements'][eid(items, n)]['producer']['slot'] for n in ('Q', 'P', 'U')] == ['root.2', 'root.1', 'root.3']
    assert all(items[n]['category'] == 'editable' for n in ('Q', 'P', 'U'))
    for value, reasons in [(0., ('branch_absent', None, 'branch_absent')), (-1., ('no_root',) * 3), (4., (None, None, 'branch_absent'))]:
        ev = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': value}})
        assert tuple(ev.elements[eid(items, n)].get('reason') for n in ('Q', 'P', 'U')) == reasons


def test_sparse_output_ordinals_and_missing_elements_are_not_invented():
    body = number('a', 4.) + function()
    body += '<command name="Root"><input a0="f"/><output a2="U" a0="" a1="ghost"/></command>'
    doc, items = imported(body + undefined('U'))
    assert items['U']['category'] == 'editable' and 'ghost' not in items
    op = producer(doc, items, 'U')
    assert op['args']['count']['value'] == 3
    assert op['outputs'] == [{'slot': 'root.3', 'elementId': eid(items, 'U')}]
    assert all(e['displayName'] != 'ghost' for e in doc['elements'].values())


def test_saved_homogeneous_coords_are_normalized_before_matching():
    body = number('a', 4.) + function() + command('Root', ['f'], ['P'])
    doc, items = imported(body + element('point', 'P', extra='<coords x="-6" y="0" z="-3"/>'))
    assert items['P']['category'] == 'editable' and items['P']['value_check'] == 'passed'
    assert doc['elements'][eid(items, 'P')]['producer']['slot'] == 'root.2'
    assert producer(doc, items, 'P')['args']['count']['value'] == 2


@pytest.mark.parametrize('name,args,text,saved', [
    ('Root', ['f', '0'], '0', (0., 0.)),
    ('Root', ['f', '-1', '1'], '0', (0., 0.)),
    ('Roots', ['f', '-1', '1'], 'x^2', None),
    ('Root', ['f', '0'], 'x^3-2x+2', None),
    ('Intersect', ['f', 'xAxis', '1'], 'x^2-4', (2., 0.)),
])
def test_known_solver_differences_stay_dependent_and_fail_value_check(name, args, text, saved):
    doc, items = imported(function(text) + command(name, args, ['P'])
                          + (undefined('P') if saved is None else point('P', *saved)))
    assert items['P']['category'] == 'differs' and items['P']['reason'] == 'value_mismatch'
    assert items['P']['value_check'] == 'failed' and eid(items, 'P') not in doc['inputs']
    assert producer(doc, items, 'P')['op'] != 'point.free'


@pytest.mark.parametrize('name,args,text,reason', [
    ('Root', ['f'], 'sin(x)', 'unsupported_signature'),
    ('Extremum', ['f'], 'If(x>0,x^2)', 'unsupported_signature'),
    ('Root', ['f', '(1,0)'], 'x^2-4', 'unsupported_signature'),
    ('Root', ['f', 'floor(a)'], 'x^2-4', 'formula_unsupported'),
    ('Root', ['f', 'a+'], 'x^2-4', 'parse_error'),
    ('Roots', ['f'], 'x^2-4', 'unsupported_signature'),
    ('Extremum', ['f', '0'], 'x^2-4', 'unsupported_signature'),
    ('Intersect', ['f', 'xAxis'], 'sin(x)', 'unsupported_signature'),
    ('Intersect', ['f', 'xAxis', 'a'], 'x^2-4', 'unsupported_signature'),
    ('Intersect', ['f', 'yAxis', '2'], 'x^2-4', 'unsupported_signature'),
    ('Intersect', ['f', 'yAxis', '1+0'], 'x^2-4', 'unsupported_signature'),
])
def test_unsupported_signatures_never_import_saved_points_as_free(name, args, text, reason):
    doc, items = imported(number('a', 1.) + function(text) + command(name, args, ['P']) + point('P', 0., 0.))
    assert items['P']['category'] != 'editable' and items['P']['reason'] == reason
    assert items['P']['native_ids'] == []


def test_inline_function_and_arithmetic_helpers_are_owned_and_deleted_with_host():
    body = number('a', 1.) + command('Root', ['x^2-a', 'a+1'], ['P']) + point('P', 1., 0.)
    doc, items = imported(body)
    assert items['P']['category'] == 'editable'
    host = producer(doc, items, 'P')['id']
    helpers = set(doc['elements']) - {eid(items, n) for n in items}
    assert len(helpers) == 2
    for h in helpers:
        assert doc['elements'][h]['displayName'] == ''
        assert doc['elements'][h]['origin'] == {'kind': 'auto', 'source': host}
        assert doc['appearance'][h]['role'] == 'aux'
    ev = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': 4.}})
    assert ev.elements[eid(items, 'P')]['value'] == pytest.approx(dict(x=2., y=0.))
    cleaned, _ = native.delete(doc, [eid(items, 'P')], mode='operation')
    assert not helpers.intersection(cleaned.elements)
    assert set(cleaned.elements) == {eid(items, 'a')}


def test_many_outputs_use_bounded_assignment_instead_of_permutations():
    # Thirty saved undefined outputs all retain their rank, even though only two roots exist.
    names = [f'P_{i}' for i in range(30)]
    body = function('x^2-4') + command('Root', ['f'], names)
    body += point(names[0], -2., 0.) + point(names[1], 2., 0.) + ''.join(undefined(n) for n in names[2:])
    doc, items = imported(body)
    assert all(e['category'] == 'editable' for e in items.values())
    assert producer(doc, items, names[0])['args']['count']['value'] == 30


def test_absent_saved_coords_are_insufficient_evidence_even_when_both_evaluations_are_undefined():
    doc, items = imported(function('x^2+1') + command('Root', ['f'], ['P']) + element('point', 'P'))
    assert items['P']['category'] == 'differs'
    assert items['P']['reason'] == 'value_unchecked'
    assert items['P']['value_check'] == 'not_checked'
    assert native.evaluate(doc).elements[eid(items, 'P')]['reason'] == 'no_root'


@pytest.mark.parametrize('finite', [False, True])
def test_conflicting_saved_outputs_explicitly_refuse_instead_of_sharing_a_slot(finite):
    body = function('x^2-4') + command('Root', ['f'], ['P', 'Q'])
    doc, items = imported(body + point('P', 2., 0.) + (point('Q', 2., 0.) if finite else undefined('Q')))
    assert all(items[n]['native_ids'] == [] and items[n]['reason'] == 'unsupported_signature' for n in ('P', 'Q'))
    assert all(op['op'] != 'point.free' for op in doc['operations'].values())


def test_scalar_value_and_ordinate_preserve_explicit_domain_without_clamping():
    body = (number('a', 0.) + command('Function', ['x^2', '1', '3'], ['f']) + element('function', 'f')
            + command('Intersect', ['f', 'yAxis'], ['P']) + undefined('P')
            + expression('v', 'f(a)') + element('numeric', 'v', extra='<value val="NaN"/>'))
    doc, items = imported(body)
    assert items['P']['category'] == items['v']['category'] == 'editable'
    saved = native.evaluate(doc)
    assert saved.elements[eid(items, 'v')]['reason'] == 'out_of_domain'
    assert saved.elements[eid(items, 'P')]['state'] == 'undefined'
    ev = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': 2.}})
    assert ev.elements[eid(items, 'v')]['value']['value'] == 4.
    assert ev.elements[eid(items, 'P')]['state'] == 'undefined'
    assert doc['operationRegistryVersion'] == '1.11'


def test_ordinate_only_uses_existing_expression_registry():
    doc, items = imported(function('x^2+1') + command('Intersect', ['f', 'yAxis'], ['P']) + point('P', 0., 1.))
    assert items['P']['category'] == 'editable'
    assert doc['operationRegistryVersion'] == '1.10'


def test_source_output_limit_is_reported_before_constructing_an_invalid_count():
    from animageo.native.convert.ggb import ImportRefused
    body = function('x^2-4') + '<command name="Root"><input a0="f"/><output a100="P"/></command>' + undefined('P')
    with pytest.raises(ImportRefused, match='output capacity exceeds 100'):
        imported(body)


def test_downstream_formula_uses_resolved_root_rank_and_recovers():
    body = (number('a', 4.) + function() + command('Root', ['f'], ['P', 'Q'])
            + point('P', 2., 0.) + point('Q', -2., 0.)
            + expression('T', '(x(P)+1, f(x(P)+1))', 'point') + point('T', 3., 5.))
    doc, items = imported(body)
    assert all(e['category'] == 'editable' for e in items.values())
    for a, x, y in [(1., 2., 3.), (4., 3., 5.)]:
        ev = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': a}})
        assert ev.elements[eid(items, 'T')]['value'] == pytest.approx(dict(x=x, y=y))


def test_named_point_is_not_accepted_as_a_root_start():
    doc, items = imported(function('x^2-4') + point('A', 1., 0.)
                          + command('Root', ['f', 'A'], ['P']) + point('P', 2., 0.))
    assert items['P']['reason'] == 'unsupported_signature'
    assert items['P']['native_ids'] == []


def test_axis_reader_uses_numbered_input_attributes_not_xml_attribute_order():
    body = function('x^2-4')
    body += '<command name="Intersect"><input a2="2" a0="f" a1="xAxis"/><output a0="P"/></command>'
    doc, items = imported(body + point('P', 2., 0.))
    assert items['P']['category'] == 'editable'
    assert doc['elements'][eid(items, 'P')]['producer']['slot'] == 'root.2'


@pytest.mark.parametrize('name,args,signature', [
    ('Root', ['f', '0', '3'], 'Root(f, 0, 3)'),
    ('Intersect', ['f', 'xAxis', '2'], 'Intersect(f, xAxis, 2)'),
    ('Root', ['f', 'A'], 'Root(f, A)'),
])
def test_source_report_signatures_preserve_arguments_including_refusals(name, args, signature):
    doc, items = imported(function('x^2-4') + point('A', 1., 0.) + command(name, args, ['P']) + point('P', 2., 0.))
    assert items['P']['signature'] == signature


@pytest.mark.parametrize('text', ['sin(x)+a', 'If(x>0,x^2)+a', 'x/x+a'])
def test_nonpolynomial_body_is_refused_even_when_a_numeric_reference_is_undefined(text):
    body = (number('b', 0.) + expression('a', '1/b') + element('numeric', 'a', extra='<value val="NaN"/>')
            + function(text) + command('Root', ['f'], ['P']) + undefined('P'))
    doc, items = imported(body)
    assert items['P']['reason'] == 'unsupported_signature'
    assert items['P']['native_ids'] == []


def test_polynomial_with_undefined_coefficient_stays_live_and_recovers():
    body = (number('b', 0.) + expression('a', '1/b') + element('numeric', 'a', extra='<value val="NaN"/>')
            + function('x^2+a') + command('Root', ['f'], ['P']) + undefined('P'))
    doc, items = imported(body)
    assert items['P']['category'] == 'editable'
    assert native.evaluate(doc).elements[eid(items, 'P')]['reason'] == 'upstream'
    recovered = native.evaluate(doc, inputs={eid(items, 'b'): {'kind': 'number', 'value': -1.}})
    assert recovered.elements[eid(items, 'P')]['value'] == dict(x=-1., y=0.)
