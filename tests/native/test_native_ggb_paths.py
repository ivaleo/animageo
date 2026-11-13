"""GGB import of a point on a conic, a point on a graph with a domain or ``If``,
and ``ClosestPoint`` of a conic and of a graph (registry 1.9, ``mapVersion`` 6)."""
import math

import numpy as np
import pytest

from animageo import native
from tests.native.ggb_synth import command, element, point
from tests.native.test_native_ggb_conics import conic_body
from tests.native.test_native_ggb_functions import function_source, operation
from tests.native.test_native_ggb_inline import eid, imported


def value(doc, items, name, inputs=None):
    state = native.evaluate(doc, inputs=inputs).elements[eid(items, name)]
    return state['value'] if state['state'] == 'defined' else state['reason']


def all_editable(items):
    assert all(e['category'] == 'editable' and e['value_check'] in ('passed', 'not_checked')
               for e in items.values()), {n: (e['category'], e.get('reason')) for n, e in items.items()}


# ── Point(conic) ──────────────────────────────────────────────────────────

@pytest.mark.parametrize('kind, xy, extra', [
    ('Ellipse', (3 * math.cos(1), 2 * math.sin(1)), {'pathKind': 'ellipse'}),
    ('Hyperbola', (-3 * math.cosh(.5), 2 * math.sinh(.5)), {'pathKind': 'hyperbola', 'branch': -1}),
    ('Hyperbola', (3 * math.cosh(.5), -2 * math.sinh(.5)), {'pathKind': 'hyperbola', 'branch': 1}),
    ('Parabola', (2., 1.), {'pathKind': 'parabola'}),
])
def test_point_on_a_conic_is_a_point_on_its_path(kind, xy, extra):
    doc, items = imported(conic_body(kind) + command('Point', ['q'], ['P']) + point('P', *xy))
    all_editable(items)
    assert items['P']['value_check'] == 'passed'
    assert operation(doc, items, 'P')['op'] == 'point.on_path'
    entry = doc['inputs'][eid(items, 'P')]
    assert {k: v for k, v in entry.items() if k != 'value'} == dict(extra, kind='pathParameter')
    assert doc['operationRegistryVersion'] == '1.9'
    got = value(doc, items, 'P')
    assert (got['x'], got['y']) == pytest.approx(xy, abs=1e-9)


def test_point_on_a_conic_follows_it():
    doc, items = imported(conic_body('Ellipse') + command('Point', ['q'], ['P']) + point('P', 0., 2.))
    # the point through (0, 2) moves to (0, 3): the ellipse x²/9 + y²/9·… keeps P at the top
    moved = value(doc, items, 'P', {eid(items, 'T'): {'kind': 'point', 'value': [0, 3]}})
    assert moved['x'] == pytest.approx(0, abs=1e-9) and moved['y'] == pytest.approx(3, abs=1e-9)


def test_point_on_a_conic_with_a_number_stays_a_picture():
    doc, items = imported(conic_body('Ellipse') + command('Point', ['q', '0.25'], ['P']) + point('P', 0., 2.))
    assert items['P']['category'] in ('picture', 'unsupported')
    assert items['P']['reason'] == 'unsupported_signature'


# ── ClosestPoint ──────────────────────────────────────────────────────────

def largest_real_root(coefficients):
    return float(max(r.real for r in np.roots(coefficients) if abs(r.imag) < 1e-12))


@pytest.mark.parametrize('kind, a, foot', [
    ('Ellipse', (0., 5.), (0., 2.)),
    ('Ellipse', (-7., 0.), (-3., 0.)),
    ('Hyperbola', (-4., 0.), (-3., 0.)),                 # the nearest branch: −1
    ('Hyperbola', (4., 0.), (3., 0.)),
])
def test_closest_point_of_a_conic(kind, a, foot):
    doc, items = imported(conic_body(kind) + point('A', *a) + command('ClosestPoint', ['q', 'A'], ['P'])
                          + point('P', *foot))
    all_editable(items)
    assert items['P']['value_check'] == 'passed'
    assert operation(doc, items, 'P')['op'] == 'point.closest'


def test_closest_point_of_a_parabola_in_general_position():
    # y = x²/4 from (1, 5): u³ − 12u − 8 = 0
    u = largest_real_root([1, 0, -12, -8])
    doc, items = imported(conic_body('Parabola') + point('A', 1., 5.) + command('ClosestPoint', ['q', 'A'], ['P'])
                          + point('P', u, u * u / 4))
    all_editable(items)
    assert items['P']['value_check'] == 'passed'


def test_closest_point_of_a_graph():
    # y = x² from (1, 3): 2u³ − 5u − 1 = 0
    u = largest_real_root([2, 0, -5, -1])
    doc, items = imported(function_source('x²') + point('A', 1., 3.) + command('ClosestPoint', ['f', 'A'], ['P'])
                          + point('P', u, u * u))
    all_editable(items)
    assert items['P']['value_check'] == 'passed'
    assert operation(doc, items, 'P')['op'] == 'point.closest'
    moved = value(doc, items, 'P', {eid(items, 'A'): {'kind': 'point', 'value': [2, 4]}})
    assert (moved['x'], moved['y']) == pytest.approx((2, 4), abs=1e-7)


# ── Point(f) on a domain and on If ─────────────────────────────────────────

def test_point_on_a_graph_with_a_domain_clamps_like_geogebra():
    doc, items = imported(command('Function', ['x²', '-1', '1'], ['f']) + element('function', 'f')
                          + command('Point', ['f'], ['P']) + point('P', .5, .25))
    all_editable(items)
    assert items['P']['value_check'] == 'passed'
    assert operation(doc, items, 'P')['op'] == 'point.on_function'
    end = value(doc, items, 'P', {eid(items, 'P'): {'kind': 'pathParameter', 'value': 3.}})
    assert end == {'x': 1., 'y': 1.}


def test_point_on_a_piecewise_graph_keeps_its_branch_and_waits_in_a_gap():
    doc, items = imported(function_source('If(x < 0, -x, If(x >= 1, x - 1))') + command('Point', ['f'], ['P'])
                          + point('P', 2., 1.))
    all_editable(items)
    assert items['P']['value_check'] == 'passed'
    p = eid(items, 'P')
    assert value(doc, items, 'P', {p: {'kind': 'pathParameter', 'value': .5}}) == 'out_of_domain'
    assert value(doc, items, 'P', {p: {'kind': 'pathParameter', 'value': -2.}}) == {'x': -2., 'y': 2.}
    out = native.drag(doc, {}, p, (.5, 3.))
    assert out['status'] == 'no_convergence'              # the gap: the point stays where it was
    assert native.drag(doc, {}, p, (3., 3.))['inputs'][p]['value'] == 3.


def test_a_saved_point_off_the_branch_differs():
    doc, items = imported(function_source('If(x < 0, -x, x)') + command('Point', ['f'], ['P']) + point('P', .5, .25))
    assert items['P']['category'] == 'differs' and items['P']['reason'] == 'value_mismatch'
