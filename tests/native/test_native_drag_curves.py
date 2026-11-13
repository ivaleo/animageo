"""Projection and drag of a point on a conic and on a graph (registry 1.9;
``native.project``, ``native.project_input``, ``native.drag``; kernel.md §8.1)."""
import copy
import math

import pytest

from animageo import native
from animageo.native.kernel import paths
from tests.native.conftest import ref
from tests.native.test_native_intersect_conics import X, n, op
from tests.native.test_native_path_curves import at, by_k, doc, ellipse, hyperbola, near, square, value


def par(t, **extra):
    return dict({'kind': 'pathParameter', 'value': t}, **extra)


def point(d, el_id, inputs):
    return value(native.evaluate(d.doc, inputs=inputs), el_id)


# ── project / project_input ───────────────────────────────────────────────

def test_project_input_of_an_ellipse():
    d = at(ellipse(doc()), 'P', 'e', 0.5)
    got = native.project_input(d.doc, 'e', (0, 7))
    assert got == {'kind': 'pathParameter', 'value': pytest.approx(math.pi / 2, abs=1e-12), 'pathKind': 'ellipse'}
    assert native.project(d.doc, 'P', (0, 7)) == pytest.approx(math.pi / 2, abs=1e-12)


def test_project_input_takes_the_nearest_branch_of_a_hyperbola():
    d = at(hyperbola(doc()), 'P', 'h', 0.0)
    got = native.project_input(d.doc, 'P', (-5, 0))
    assert got == {'kind': 'pathParameter', 'value': 0.0, 'branch': -1, 'pathKind': 'hyperbola'}
    assert native.project_input(d.doc, 'P', (5, 0))['branch'] == 1
    near(point(d, 'P', {'P': got}), (-3, 0))


def test_project_input_of_old_paths_is_the_parameter():
    d = doc().at('A', 0, 0).at('B', 4, 0).segment('s', 'A', 'B')
    assert native.project_input(d.doc, 's', (3, 2)) == {'kind': 'pathParameter', 'value': 0.75}


def test_project_on_a_graph_reads_the_bounds_of_the_document():
    step = {'if': [{'cmp': '>', 'args': [X, n(50)]}, n(0), n(70)]}
    d = doc().graph('f', step)
    d.doc['viewDefaults'] = {'bounds': [-10, -10, 10, 10]}
    assert native.project(d.doc, 'f', (0, 0)) == pytest.approx(0, abs=1e-7)
    d.doc['viewDefaults'] = {'bounds': [-20, -10, 20, 10]}
    assert native.project(d.doc, 'f', (0, 0)) == pytest.approx(50, abs=1e-7)
    assert native.project_input(d.doc, 'f', (0, 0)) == {'kind': 'pathParameter', 'value': pytest.approx(50, abs=1e-7)}


def test_project_without_a_point_of_the_graph_is_none():
    d = doc().graph('f', {'fn': 'sqrt', 'args': [X]}, lo=-5, hi=-1)
    assert native.project(d.doc, 'f', (0, 0)) is None
    assert native.project_input(d.doc, 'f', (0, 0)) is None


def test_nearest_input_of_a_frame():
    f = paths.frame('conic', {'kind': 'hyperbola', 'c': [0, 0], 'axis': [1, 0], 'a': 3, 'b': 4})
    assert paths.nearest_input(f, -5, 0, 1e-10) == {'kind': 'pathParameter', 'value': 0.0, 'branch': -1,
                                                    'pathKind': 'hyperbola'}


# ── drag without a hint ───────────────────────────────────────────────────

def test_drag_on_an_ellipse_projects_and_writes_the_kind():
    d = at(ellipse(doc()), 'P', 'e', 0.5)
    out = native.drag(d.doc, {}, 'P', (0, -7))
    assert out['status'] == 'ok'
    assert out['inputs']['P'] == {'kind': 'pathParameter', 'value': pytest.approx(3 * math.pi / 2),
                                  'pathKind': 'ellipse'}


def test_drag_on_a_hyperbola_switches_to_the_nearest_branch():
    d = at(hyperbola(doc()), 'P', 'h', 0.5, branch=1, pathKind='hyperbola')
    out = native.drag(d.doc, None, 'P', (-4, 1))
    assert out['status'] == 'ok'
    assert out['inputs']['P']['branch'] == -1 and out['inputs']['P']['pathKind'] == 'hyperbola'
    got = point(d, 'P', out['inputs'])
    assert got[0] < 0
    assert math.hypot(got[0] + 4, got[1] - 1) <= paths_distance(d, 'h', (-4, 1)) + 1e-12


def paths_distance(d, path, xy):
    curve = paths.frame('conic', native.evaluate(d.doc).elements[path]['value'])
    best = math.inf
    for b in (1, -1):
        for k in range(-40000, 40001):
            p = paths.point_at(curve, k / 10000, b)
            best = min(best, math.hypot(p['x'] - xy[0], p['y'] - xy[1]))
    return best


def test_drag_on_a_parabola():
    d = at(doc().parabola('q'), 'P', 'q', 0.0)
    out = native.drag(d.doc, {}, 'P', (0, 5))
    assert out['status'] == 'ok'
    assert out['inputs']['P'] == par(pytest.approx(-math.sqrt(3)), pathKind='parabola')


def test_drag_reattaches_a_point_whose_conic_changed_kind():
    d = by_k()
    at(d, 'P', 'q', 0.5, pathKind='ellipse')
    inputs = {'k': {'kind': 'number', 'value': -1 / 16}}
    assert point(d, 'P', inputs) == 'path_kind_changed'
    out = native.drag(d.doc, inputs, 'P', (5, 0))
    assert out['status'] == 'ok'
    assert out['inputs']['P'] == par(0.0, branch=1, pathKind='hyperbola')
    near(point(d, 'P', out['inputs']), (3, 0))


def test_drag_on_a_graph_path_stops_at_the_end_of_the_domain():
    d = at(square(doc(), lo=-1, hi=2), 'P', 'f', 0.5)
    out = native.drag(d.doc, {}, 'P', (5, 5))
    assert out == {'status': 'clamped', 'inputs': {'P': par(2)}}
    assert native.drag(d.doc, {}, 'P', (2, 4))['status'] == 'ok'
    out = native.drag(d.doc, {}, 'P', (0, 3))         # ±√2.5, the negative one outside the domain
    assert out['status'] == 'ok'
    assert out['inputs']['P']['value'] == pytest.approx(math.sqrt(2.5), abs=1e-7)


def test_drag_on_a_graph_path_across_a_gap_takes_the_nearest_end():
    cond = {'if': [{'cmp': '<', 'args': [X, n(0)]}, op('-', n(0), X),
                   {'if': [{'cmp': '>=', 'args': [X, n(1)]}, op('-', X, n(1))]}]}
    d = at(doc().graph('f', cond), 'P', 'f', -1.0)
    out = native.drag(d.doc, {}, 'P', (0.8, -0.5))
    assert out['status'] == 'ok'
    assert out['inputs']['P']['value'] == pytest.approx(1, abs=1e-7)


def test_drag_on_a_graph_without_a_point_does_not_move():
    d = at(doc().graph('f', {'fn': 'sqrt', 'args': [X]}, lo=-5, hi=-1), 'P', 'f', -2.0)
    inputs = {}
    out = native.drag(d.doc, inputs, 'P', (0, 0))
    assert out['status'] == 'no_convergence' and out['inputs'] is inputs


# ── drag through a hint ───────────────────────────────────────────────────

def midpoint_of(d, path, t, **extra):
    """``M`` the midpoint of ``P`` on ``path`` and ``C = (1, 1)``, dragged through ``P``."""
    at(d, 'P', path, t, **extra)
    d.at('C', 1, 1)
    d.op('op_M', 'point.midpoint', {'a': ref('P'), 'b': ref('C')}, [('point', 'M', 'point')])
    d.doc.setdefault('appearance', {})['M'] = {'drag': {'via': 'P'}}
    return d


def test_via_a_point_on_an_ellipse_wraps_its_parameter():
    d = midpoint_of(ellipse(doc()), 'e', 6.0, pathKind='ellipse')
    target = ((5 * math.cos(0.3) + 1) / 2, (3 * math.sin(0.3) + 1) / 2)
    out = native.drag(d.doc, {}, 'M', target)
    assert out['status'] == 'ok'
    got = out['inputs']['P']
    assert got['pathKind'] == 'ellipse' and set(got) == {'kind', 'value', 'pathKind'}
    assert 0 <= got['value'] < 2 * math.pi and got['value'] == pytest.approx(0.3, abs=1e-9)


def test_via_a_point_on_a_hyperbola_keeps_its_branch():
    d = midpoint_of(hyperbola(doc()), 'h', 0.2, branch=-1, pathKind='hyperbola')
    target = ((-3 * math.cosh(0.8) + 1) / 2, (4 * math.sinh(0.8) + 1) / 2)
    out = native.drag(d.doc, {}, 'M', target)
    assert out['status'] == 'ok'
    assert out['inputs']['P'] == par(pytest.approx(0.8, abs=1e-9), branch=-1, pathKind='hyperbola')
    # the target by the other branch: the nearest point the left branch reaches, not a switch
    out = native.drag(d.doc, {}, 'M', ((3 * math.cosh(0.8) + 1) / 2, (4 * math.sinh(0.8) + 1) / 2))
    assert out['status'] == 'ok'
    assert out['inputs']['P']['branch'] == -1 and out['inputs']['P']['pathKind'] == 'hyperbola'


def test_via_a_point_on_a_parabola():
    d = midpoint_of(doc().parabola('q'), 'q', 0.0)
    target = ((-2 * 1.5 + 1) / 2, (1.5 ** 2 + 1) / 2)
    out = native.drag(d.doc, {}, 'M', target)
    assert out['status'] == 'ok'
    assert out['inputs']['P'] == par(pytest.approx(1.5, abs=1e-9))


def test_via_a_point_on_a_graph_path_stops_at_the_end_of_the_domain():
    d = midpoint_of(square(doc(), hi=2), 'f', 0.5)
    out = native.drag(d.doc, {}, 'M', ((1.5 + 1) / 2, (2.25 + 1) / 2))
    assert out['status'] == 'ok' and out['inputs']['P']['value'] == pytest.approx(1.5, abs=1e-9)
    out = native.drag(d.doc, {}, 'M', ((5 + 1) / 2, (25 + 1) / 2))
    assert out == {'status': 'clamped', 'inputs': {'P': par(2.0)}}


def test_the_inputs_are_not_changed():
    d = midpoint_of(hyperbola(doc()), 'h', 0.2, branch=-1, pathKind='hyperbola')
    inputs = {'C': {'kind': 'point', 'value': [1, 1]}}
    before = copy.deepcopy(inputs)
    native.drag(d.doc, inputs, 'M', (0, 0))
    native.drag(d.doc, inputs, 'P', (0, 0))
    assert inputs == before


# ── the timeline ──────────────────────────────────────────────────────────

def timeline(*frames):
    return {'version': 2, 'keyframes': list(frames)}


def test_timeline_wraps_a_point_on_an_ellipse_and_keeps_the_branch_of_a_hyperbola():
    d = at(ellipse(doc()), 'P', 'e', 6.0, pathKind='ellipse')
    at(hyperbola(d), 'H', 'h', 0.5, branch=-1, pathKind='hyperbola')
    tm = timeline({'t': 0, 'values': {'P': {'tparam': 6.0}, 'H': {'tparam': 0.5}}},
                  {'t': 2, 'values': {'P': {'tparam': 0.3, 'direction': 'short'},
                                      'H': {'tparam': -0.5, 'direction': 'ccw'}}, 'easing': 'linear'})
    s = native.sample_timeline(d.doc, tm, 1)
    assert s['inputs']['P'] == par(pytest.approx((6.0 + 0.3 + 2 * math.pi) / 2), pathKind='ellipse')
    assert s['inputs']['H'] == par(pytest.approx(0.0), branch=-1, pathKind='hyperbola')
    near(point(d, 'H', s['inputs']), (-3, 0))
