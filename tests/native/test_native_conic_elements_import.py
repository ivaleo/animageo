"""Conic element imports retain source identity, evidence and live inputs."""
import math

import pytest

from animageo import native
from animageo.native.convert.values import line_coefficients, native_report_value
from tests.native.ggb_synth import command, element, expression, point
from tests.native.test_native_ggb_inline import eid, imported
from tests.native.test_native_tangency_import import conic, line, number, producer


def ellipse():
    return number('a', 4) + conic('a*x^2+9*y^2=36', (4, 9, -36, 0, 0, 0))


def circle():
    return (point('O', 1., -2.) + number('r', 3) + command('Circle', ['O', 'r'], ['c'])
            + element('conic', 'c', extra='<matrix A0="1" A1="1" A2="-4" A3="0" A4="-1" A5="2"/>'))


def undefined(label, kind='line'):
    return element(kind, label, extra='<coords x="NaN" y="NaN" z="NaN"/>')


def line_value(ev, items, name):
    state = ev.elements[eid(items, name)]
    assert state['state'] == 'defined', state
    return native_report_value('line', state['value'])['value']


@pytest.mark.parametrize('name,curve,outputs,coords,operation', [
    ('Directrix', ellipse(), ['left', 'right'], [(1, 0, 9/math.sqrt(5)), (1, 0, -9/math.sqrt(5))], 'conic.directrices'),
    ('Asymptote', conic('9*x^2-4*y^2=36', (9, -4, -36, 0, 0, 0)), ['s', 't'], [(-3, 2, 0), (-3, -2, 0)], 'conic.asymptotes'),
    ('FirstAxis', ellipse(), ['s'], [(0, 1, 0)], 'conic.axes'),
    ('MajorAxis', ellipse(), ['s'], [(0, 1, 0)], 'conic.axes'),
    ('SecondAxis', ellipse(), ['s'], [(1, 0, 0)], 'conic.axes'),
    ('MinorAxis', ellipse(), ['s'], [(1, 0, 0)], 'conic.axes'),
])
def test_source_line_sets_and_axis_aliases(name, curve, outputs, coords, operation):
    doc, items = imported(curve + command(name, ['K'], outputs) + ''.join(line(n, v) for n, v in zip(outputs, coords)))
    assert all(items[n]['category'] == 'editable' and items[n]['value_check'] == 'passed' for n in outputs)
    assert producer(doc, items, outputs[0])['op'] == operation
    ev = native.evaluate(doc)
    for n, saved in zip(outputs, coords):
        assert line_value(ev, items, n) == pytest.approx(line_coefficients(*saved))
    if name == 'Directrix':
        assert [doc['elements'][eid(items, n)]['producer']['slot'] for n in outputs] == ['directrix.2', 'directrix.1']
        ev = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': 1}})
        assert line_value(ev, items, 'right') == pytest.approx([1, 0, -36/math.sqrt(32)])
    elif name in ('FirstAxis', 'MajorAxis', 'SecondAxis', 'MinorAxis'):
        assert producer(doc, items, 's')['outputs'][0]['slot'] == ('focal' if name in ('FirstAxis', 'MajorAxis') else 'conjugate')


@pytest.mark.parametrize('name,names,coords,slots', [
    ('Focus', ['R', 'L'], [(math.sqrt(5), 0), (-math.sqrt(5), 0)], ['second', 'first']),
    ('Vertex', ['R', 'L', 'T', 'B'], [(3, 0), (-3, 0), (0, 2), (0, -2)], ['second', 'first', 'fourth', 'third']),
])
def test_saved_points_match_as_a_group_before_descendants(name, names, coords, slots):
    body = ellipse() + command(name, ['K'], names) + ''.join(point(n, *p) for n, p in zip(names, coords))
    body += command('Midpoint', [names[0], names[1]], ['M']) + point('M', 0., 0.)
    doc, items = imported(body)
    assert all(i['category'] == 'editable' for i in items.values())
    assert [doc['elements'][eid(items, n)]['producer']['slot'] for n in names] == slots
    ev = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': 1}})
    assert ev.elements[eid(items, names[0])]['value']['x'] > 0
    assert ev.elements[eid(items, 'M')]['value'] == pytest.approx({'x': 0, 'y': 0})


@pytest.mark.parametrize('name,names,values', [
    ('Focus', ['F', 'G'], [(1, -2), (1, -2)]),
    ('Vertex', ['A', 'B', 'C', 'D'], [(-2, -2), (4, -2), (1, -5), (1, 1)]),
    ('Axes', ['h', 'v'], [(0, 1, 2), (1, 0, -1)]),
    ('FirstAxis', ['h'], [(0, 1, 2)]),
])
def test_circle_parts_have_owned_adapter_and_keep_duplicate_focus_names(name, names, values):
    kind = 'line' if name in ('Axes', 'FirstAxis') else 'point'
    body = circle() + command(name, ['c'], names)
    body += ''.join(line(n, v) if kind == 'line' else point(n, *v) for n, v in zip(names, values))
    doc, items = imported(body)
    assert all(items[n]['category'] == 'editable' for n in names)
    host = producer(doc, items, names[0])
    adapter_id = host['args']['conic']['elementId']
    adapter = doc['elements'][adapter_id]
    adapter_op = doc['operations'][adapter['producer']['operationId']]
    assert adapter_op['op'] == 'conic.from_circle'
    assert adapter_op['outputs'] == [{'slot': 'conic', 'elementId': adapter_id}]
    assert adapter['origin'] == {'kind': 'auto', 'source': host['id']}
    assert doc['appearance'][adapter_id]['role'] == 'aux' and not doc['appearance'][adapter_id]['visible']
    if name == 'Focus':
        assert [doc['elements'][eid(items, n)]['producer']['slot'] for n in names] == ['first', 'second']
    snapshot = native.dumps(doc)
    restored = native.load(snapshot)
    ev = native.evaluate(restored, inputs={eid(items, 'O'): {'kind': 'point', 'value': [-2, 3]}})
    if name == 'Focus':
        assert all(ev.elements[eid(items, n)]['value'] == {'x': -2., 'y': 3.} for n in names)
    cleaned, _ = native.delete(restored, [eid(items, names[0])], mode='operation')
    assert adapter_id not in cleaned.elements and native.validate(cleaned) == []
    assert native.content_hash(native.load(snapshot)) == native.content_hash(doc)


def test_center_uses_actual_circle_type_without_adapter_and_moves():
    doc, items = imported(circle() + command('Center', ['c'], ['Q']) + point('Q', 1., -2.))
    assert items['Q']['category'] == 'editable' and items['Q']['value_check'] == 'passed'
    assert producer(doc, items, 'Q')['op'] == 'point.center'
    assert not any(op['op'] == 'conic.from_circle' for op in doc['operations'].values())
    ev = native.evaluate(doc, inputs={eid(items, 'O'): {'kind': 'point', 'value': [-2, 3]}})
    assert ev.elements[eid(items, 'Q')]['value'] == {'x': -2., 'y': 3.}


def test_center_of_collapsed_three_point_circle_keeps_upstream_and_recovers():
    body = point('M', 1., -2.) + point('N', 1., -2.) + point('O', 1., -2.)
    body += command('Circle', ['M', 'N', 'O'], ['c'])
    body += element('conic', 'c', extra='<matrix A0="1" A1="1" A2="5" A3="0" A4="-1" A5="2"/>')
    doc, items = imported(body + command('Center', ['c'], ['Q']) + point('Q', 1., -2.))
    assert producer(doc, items, 'Q')['op'] == 'point.center'
    assert items['Q']['category'] == 'differs' and items['Q']['reason'] == 'value_mismatch'
    saved = native.evaluate(doc)
    assert saved.elements[eid(items, 'c')]['reason'] == 'collinear_points'
    assert saved.elements[eid(items, 'Q')]['reason'] == 'upstream'
    moved = native.evaluate(doc, inputs={eid(items, 'N'): {'kind': 'point', 'value': [2, -2]},
                                        eid(items, 'O'): {'kind': 'point', 'value': [1, -1]}})
    assert moved.elements[eid(items, 'Q')]['value'] == pytest.approx({'x': 1.5, 'y': -1.5})


def test_sparse_circle_foci_reserve_ordinal_and_undefined_vertices_recover():
    doc, items = imported(circle() + command('Focus', ['c'], ['', 'F']) + point('F', 1., -2.))
    assert items['F']['category'] == 'editable' and '' not in items
    assert doc['elements'][eid(items, 'F')]['producer']['slot'] == 'second'
    body = number('a', 0) + conic('a*x^2+y^2=4*x', (0, 1, 0, 0, -2, 0))
    body += command('Vertex', ['K'], ['P', 'Q', 'R', 'S']) + point('P', 0., 0.)
    body += ''.join(undefined(n, 'point') for n in ('Q', 'R', 'S'))
    doc, items = imported(body)
    assert all(items[n]['category'] == 'editable' for n in ('P', 'Q', 'R', 'S'))
    ev = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': 1}})
    assert all(ev.elements[eid(items, n)]['state'] == 'defined' for n in ('P', 'Q', 'R', 'S'))


def test_second_axis_of_parabola_is_an_honest_mismatch():
    doc, items = imported(conic('y^2=4*x', (0, 1, 0, 0, -2, 0))
                          + command('SecondAxis', ['K'], ['s']) + line('s', (1, 0, 0)))
    assert items['s']['category'] == 'differs' and items['s']['reason'] == 'value_mismatch'
    assert native.evaluate(doc).elements[eid(items, 's')]['reason'] == 'branch_absent'


@pytest.mark.parametrize('name', ['Diameter', 'ConjugateDiameter'])
@pytest.mark.parametrize('direction', ['d', 'v'])
def test_diameter_aliases_accept_live_line_or_vector(name, direction):
    body = ellipse() + point('A', 0., 0.) + point('B', 1., 1.)
    body += command('Line', ['A', 'B'], ['d']) + line('d', (-1, 1, 0))
    body += command('Vector', ['A', 'B'], ['v']) + element('vector', 'v', extra='<coords x="1" y="1" z="0"/>')
    body += command(name, [direction, 'K'], ['s']) + line('s', (4, 9, 0))
    doc, items = imported(body)
    assert items['s']['category'] == 'editable'
    ev = native.evaluate(doc, inputs={eid(items, 'B'): {'kind': 'point', 'value': [0, 1]}})
    assert line_value(ev, items, 's') == pytest.approx([0, 1, 0])


def test_polar_supports_inline_point_and_curve_with_numeric_dependency():
    body = number('a', 4) + point('A', 1., 0.)
    body += command('Polar', ['A+(1,0)', 'a*x^2+9*y^2=36'], ['s']) + line('s', (8, 0, -36))
    doc, items = imported(body)
    assert items['s']['category'] == 'editable'
    ev = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': 1}})
    assert line_value(ev, items, 's') == pytest.approx([1, 0, -18])
    assert native.validate(doc) == []
    assert any(i.code == 'unprintable_operation' for i in native.print_commands(doc).issues)


@pytest.mark.parametrize('name,args,kind', [
    ('Polar', ['l', 'K'], 'point'), ('Directrix', ['2'], 'line'),
    ('Asymptote', ['f'], 'line'), ('Eccentricity', ['K'], 'numeric'),
    ('Diameter', ['2', 'K'], 'line'),
])
def test_unsupported_signatures_never_become_free_saved_objects(name, args, kind):
    body = ellipse() + expression('l', 'y=0', 'line') + line('l', (0, 1, 0))
    body += expression('f', 'x^2', 'function') + element('function', 'f')
    body += command(name, args, ['bad'])
    body += point('bad', 1., 0.) if kind == 'point' else number('bad', .5) if kind == 'numeric' else line('bad', (1, 0, 0))
    _, items = imported(body)
    assert items['bad']['reason'] == 'unsupported_signature' and items['bad']['native_ids'] == []


def test_missing_coords_and_line_multiplicity_do_not_claim_success():
    body = ellipse() + command('Directrix', ['K'], ['s']) + line('s')
    _, items = imported(body)
    assert items['s']['reason'] == 'value_unchecked'
    body = circle() + command('Axes', ['c'], ['s', 't']) + line('s', (0, 1, 2)) + line('t', (0, 2, 4))
    doc, items = imported(body)
    assert all(items[n]['reason'] == 'unsupported_signature' and items[n]['native_ids'] == [] for n in ('s', 't'))
    assert not any(op['op'] == 'conic.from_circle' for op in doc['operations'].values())


@pytest.mark.parametrize('source,operation', [
    ('Q=Center(K)', 'conic.center'), ('F,G=Focus(K)', 'conic.foci'),
    ('A,B,C,D=Vertex(K)', 'conic.vertices'), ('l,m=Axes(K)', 'conic.axes'),
    ('l=MajorAxis(K)', 'conic.axes'), ('l=MinorAxis(K)', 'conic.axes'),
    ('l,m=Directrix(K)', 'conic.directrices'), ('l=Polar(P,K)', 'line.polar_conic'),
    ('l=Polar(K,P)', 'line.polar_conic'),
])
def test_existing_dsl_factories_use_the_same_lowerings(source, operation):
    from animageo.geo.construction import Construction
    from animageo.parsers import dsl
    from tests.native.test_native_l5_ggb import NS
    c = Construction()
    dsl.run(c, 'a=4\nP=Point(1,0)\nK=Conic("a*x^2+9*y^2=36")\n' + source)
    doc, report = native.from_construction(c, id_namespace=NS)
    assert report['untranslated'] == [] and native.validate(doc) == []
    assert any(op['op'] == operation for op in doc['operations'].values())


@pytest.mark.parametrize('source', ['F,G=Focus(c)', 'A,B,C,D=Vertex(c)', 'l,m=Axes(c)',
                                  'l=MajorAxis(c)', 'l=MinorAxis(c)'])
def test_dsl_circle_aliases_keep_existing_output_names_and_honest_values(source):
    from animageo.geo.construction import Construction
    from animageo.parsers import dsl
    from tests.native.test_native_l5_ggb import NS
    c = Construction()
    dsl.run(c, 'O=Point(1,-2)\nc=Circle(O,3)\n'+source)
    doc, report = native.from_construction(c, id_namespace=NS)
    assert report['untranslated'] == [] and native.validate(doc) == []
    requested = source.split('=')[0].split(',')
    records = {e['name']: e for e in report['elements']}
    host = doc['operations'][doc['elements'][records[requested[0]]['native_ids'][0]]['producer']['operationId']]
    assert len(host['outputs']) == len(requested)
    adapter_id = host['args']['conic']['elementId']
    assert doc['operations'][doc['elements'][adapter_id]['producer']['operationId']]['op'] == 'conic.from_circle'
    assert all(records[n]['category'] in ('editable', 'differs') for n in requested)


def test_capability_map_and_source_only_reasons():
    from animageo.native.convert.mapping import dsl_map, map_problems
    assert native.has('conic_elements') and dsl_map().version == 10 and map_problems() == []
    assert not {'conic.directrices', 'line.polar_conic'}.intersection(dsl_map().ops_without_classic)
    assert all(dsl_map().ops_without_classic[name] for name in ('conic.from_circle', 'conic.asymptotes', 'line.conjugate_diameter'))


def test_large_finite_saved_line_coefficients_are_scaled_before_matching():
    body = conic('x^2-y^2=1', (1, -1, -1, 0, 0, 0)) + command('Asymptote', ['K'], ['s', 't'])
    doc, items = imported(body + line('s', (-1.7e308, 1.7e308, 0)) + line('t', (-1, -1, 0)))
    assert items['s']['category'] == items['t']['category'] == 'editable'
    assert line_value(native.evaluate(doc), items, 's') == pytest.approx([math.sqrt(.5), -math.sqrt(.5), 0])


def test_sparse_undefined_lines_keep_rank_and_recover_without_rebinding():
    body = ellipse() + command('Asymptote', ['K'], ['', 's']) + undefined('s')
    doc, items = imported(body)
    assert items['s']['category'] == 'editable' and '' not in items
    assert doc['elements'][eid(items, 's')]['producer']['slot'] == 'asymptote.2'
    assert native.evaluate(doc).elements[eid(items, 's')]['reason'] == 'no_asymptote'
    ev = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': -4}})
    assert ev.elements[eid(items, 's')]['state'] == 'defined'


def test_empty_groups_create_no_circle_adapter_or_phantom_output():
    doc, items = imported(circle() + command('Focus', ['c'], ['', '']))
    assert set(items) == {'O', 'r', 'c'}
    assert not any(op['op'] == 'conic.from_circle' for op in doc['operations'].values())


def test_large_sparse_capacity_is_bounded_and_keeps_absent_slots():
    body = conic('x^2-y^2=1', (1, -1, -1, 0, 0, 0))
    body += '<command name="Asymptote"><input a0="K"/><output a99="s"/></command>' + undefined('s')
    doc, items = imported(body)
    assert items['s']['category'] == 'editable'
    assert producer(doc, items, 's')['args']['count']['value'] == 100
    assert doc['elements'][eid(items, 's')]['producer']['slot'] == 'asymptote.100'
    assert native.evaluate(doc).elements[eid(items, 's')]['reason'] == 'branch_absent'


def test_finite_saved_line_cannot_occupy_an_explicit_excess_slot():
    body = conic('x^2-y^2=1', (1, -1, -1, 0, 0, 0))
    body += '<command name="Asymptote"><input a0="K"/><output a99="s"/></command>' + line('s', (-1, 1, 0))
    doc, items = imported(body)
    assert items['s']['category'] == 'differs' and items['s']['reason'] == 'value_mismatch'
    assert doc['elements'][eid(items, 's')]['producer']['slot'] == 'asymptote.100'
    assert native.evaluate(doc).elements[eid(items, 's')]['reason'] == 'branch_absent'


def test_undefined_source_branch_cannot_hide_in_excess_capacity():
    body = conic('x^2-y^2=1', (1, -1, -1, 0, 0, 0))
    body += '<command name="Asymptote"><input a0="K"/><output a0="s" a2="t"/></command>'
    doc, items = imported(body + undefined('s') + undefined('t'))
    assert items['s']['category'] == 'differs' and items['t']['category'] == 'editable'
    assert doc['elements'][eid(items, 's')]['producer']['slot'] == 'asymptote.1'
    assert doc['elements'][eid(items, 't')]['producer']['slot'] == 'asymptote.3'


@pytest.mark.parametrize('ordinal', ['100', '9'*5000], ids=['over_capacity', 'oversized_ordinal'])
def test_source_output_capacity_is_refused_before_integer_conversion(ordinal):
    from animageo.native.convert import ImportRefused
    body = conic('x^2-y^2=1', (1, -1, -1, 0, 0, 0))
    body += f'<command name="Asymptote"><input a0="K"/><output a{ordinal}="s"/></command>' + undefined('s')
    with pytest.raises(ImportRefused, match='conic output capacity exceeds 100'):
        imported(body)


def test_nonquadratic_source_never_becomes_a_saved_free_polar():
    body = number('a', 1) + conic('sin(x)+y^2=1', (1, 1, -1, 0, 0, 0))
    body += command('Polar', ['(1,0)', 'K'], ['p']) + line('p', (1, 0, -1))
    doc, items = imported(body)
    # A nonquadratic curve has a producer with an undefined state, rather
    # than a saved free conic or a guessed polar line.
    assert items['p']['category'] == 'differs'
    assert native.evaluate(doc).elements[eid(items, 'p')]['state'] == 'undefined'
