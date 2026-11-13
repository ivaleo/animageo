"""A point on a conic and on a graph: ``point.on_path`` with the paths
``conic`` and ``function`` (registry 1.9; docs/native/ops/point.on_path.md)."""
import math

import pytest

from animageo import native
from animageo.native.kernel import paths
from animageo.native.registry import registry
from tests.native.conftest import ref
from tests.native.test_native_intersect_conics import X, Doc, checks_pass, n, op


def at(d, el_id, path, t, **extra):
    d.op('op_' + el_id, 'point.on_path', {'path': ref(path)}, [('point', el_id, 'point')])
    d.doc['inputs'][el_id] = dict({'kind': 'pathParameter', 'value': t}, **extra)
    return d


def value(ev, el_id):
    record = ev.elements[el_id]
    if record['state'] != 'defined':
        return record['reason']
    return record['value']['x'], record['value']['y']


def near(got, want, tol=1e-9):
    assert not isinstance(got, str), got
    assert got[0] == pytest.approx(want[0], abs=tol) and got[1] == pytest.approx(want[1], abs=tol), (got, want)


def doc():
    d = Doc()
    d.doc['operationRegistryVersion'] = '1.9'
    return d


def ellipse(d, el_id='e', f1=(-4, 0), f2=(4, 0), through=(0, 3)):
    """a = 5, b = 3 by default."""
    return d.ellipse(el_id, f1, f2, through)


def hyperbola(d, el_id='h'):
    """x²/9 − y²/16 = 1."""
    return d.hyperbola(el_id)


# ── the registry ──────────────────────────────────────────────────────────

def test_the_path_family_takes_conics_and_graphs_since_1_9():
    reg = registry()
    assert reg.families['path'][-3:] == ['conic', 'function', 'locus']
    assert reg.member_since('path', 'conic') == '1.9'
    assert reg.member_since('path', 'function') == '1.9'
    assert reg.member_since('path', 'circle') is None
    assert reg.paths['conic']['kind'] == 'conic'
    assert reg.paths['function']['kind'] == 'graph'
    assert reg.reasons['path_kind_changed']['state'] == 'undefined'
    assert reg.get('point.on_path')['since'] == '1.1'       # the record keeps its contract
    assert reg.get('point.closest')['since'] == '1.4'


def test_a_conic_path_needs_registry_1_9():
    d = ellipse(Doc())
    at(d, 'P', 'e', 0.5)
    assert native.min_registry_version(d.doc) == '1.9'
    d.doc['operationRegistryVersion'] = '1.8'
    issues = native.validate(d.doc)
    assert [(i.code, i.path, i.elementId) for i in issues] == [
        ('needs_newer_registry', '/operations/op_P/args/path', 'e')]
    d.doc['operationRegistryVersion'] = '1.9'
    assert native.validate(d.doc) == []


# ── conics ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('t', [0.0, 0.7, math.pi / 2, 2.5, 4.0, 2 * math.pi, -1.0, 9.0])
def test_ellipse_by_the_eccentric_anomaly_from_its_axis(t):
    d = ellipse(doc())
    at(d, 'P', 'e', t)
    near(value(native.evaluate(d.doc), 'P'), (5 * math.cos(t), 3 * math.sin(t)))
    checks_pass(d)


def test_a_turned_ellipse_measures_from_its_own_axis():
    phi = math.radians(30)
    u = (math.cos(phi), math.sin(phi))
    nrm = (-u[1], u[0])
    c = (1.0, 2.0)
    d = ellipse(doc(), f1=(c[0] - 4 * u[0], c[1] - 4 * u[1]), f2=(c[0] + 4 * u[0], c[1] + 4 * u[1]),
                through=(c[0] + 5 * u[0], c[1] + 5 * u[1]))
    for t in (0.0, 1.0, 3.0):
        at(d, 'P', 'e', t)
        want = (c[0] + 5 * math.cos(t) * u[0] + 3 * math.sin(t) * nrm[0],
                c[1] + 5 * math.cos(t) * u[1] + 3 * math.sin(t) * nrm[1])
        near(value(native.evaluate(d.doc), 'P'), want)


def test_a_circle_conic_runs_by_the_angle_from_x():
    d = doc().five('k', (2, 0), (-2, 0), (0, 2), (0, -2), (math.sqrt(2), math.sqrt(2)))
    assert native.evaluate(d.doc).elements['k']['value']['axis'] == [1.0, 0.0]
    at(d, 'P', 'k', 1.0)
    near(value(native.evaluate(d.doc), 'P'), (2 * math.cos(1.0), 2 * math.sin(1.0)))


@pytest.mark.parametrize('branch', [None, 1, -1])
@pytest.mark.parametrize('t', [0.0, 0.5, -1.2])
def test_hyperbola_keeps_its_branch(branch, t):
    d = hyperbola(doc())
    at(d, 'P', 'h', t, **({} if branch is None else {'branch': branch}))
    s = -1 if branch == -1 else 1
    near(value(native.evaluate(d.doc), 'P'), (s * 3 * math.cosh(t), 4 * math.sinh(t)))
    checks_pass(d)


def test_parabola_by_its_own_frame():
    # focus (0, 1), directrix y = −1: vertex (0, 0), axis (0, 1), p = 2, n = (−1, 0)
    d = doc().parabola('q')
    for t in (0.0, 1.0, -1.5):
        at(d, 'P', 'q', t)
        near(value(native.evaluate(d.doc), 'P'), (-2 * t, t * t))
    checks_pass(d)


def test_a_far_hyperbola_parameter_is_not_finite():
    d = hyperbola(doc())
    at(d, 'P', 'h', 1000.0)
    assert value(native.evaluate(d.doc), 'P') == 'non_finite'


def by_k(k=0.25):
    """x²/9 + k·y² = 1: an ellipse for k > 0 (k = 1/4: a = 3, b = 2), a hyperbola for k < 0."""
    d = doc().number('k', k)
    y = {'var': 'y'}
    ast = op('-', op('+', op('/', op('^', X, n(2)), n(9)), op('*', {'ref': 0}, op('^', y, n(2)))), n(1))
    return d.op('op_q', 'conic.equation', {'expr': {'kind': 'expr', 'ast': ast},
                                          'refs': {'kind': 'list', 'items': [ref('k')]}}, [('conic', 'q', 'conic')])


def test_path_kind_guards_the_parameter():
    d = by_k()
    at(d, 'P', 'q', 0.5, pathKind='ellipse')
    near(value(native.evaluate(d.doc), 'P'), (3 * math.cos(0.5), 2 * math.sin(0.5)))
    # k < 0: a hyperbola, the point waits
    ev = native.evaluate(d.doc, inputs={'k': {'kind': 'number', 'value': -1 / 16}})
    assert ev.elements['q']['value']['kind'] == 'hyperbola'
    assert value(ev, 'P') == 'path_kind_changed'
    # the kind returns: the same t
    near(value(native.evaluate(d.doc, inputs={'k': {'kind': 'number', 'value': 1 / 9}}), 'P'),
         (3 * math.cos(0.5), 3 * math.sin(0.5)))


def test_without_path_kind_any_conic_takes_the_parameter():
    d = by_k()
    at(d, 'P', 'q', 0.5)
    ev = native.evaluate(d.doc, inputs={'k': {'kind': 'number', 'value': -1 / 16}})
    near(value(ev, 'P'), (3 * math.cosh(0.5), 4 * math.sinh(0.5)))


def test_path_kind_on_other_paths_is_ignored():
    d = doc().at('A', 0, 0).at('B', 4, 0).segment('s', 'A', 'B')
    at(d, 'P', 's', 0.25, pathKind='parabola', branch=-1)
    near(value(native.evaluate(d.doc), 'P'), (1, 0))


@pytest.mark.parametrize('bad', ['circle', 'Ellipse', 1, None])
def test_path_kind_must_be_a_conic_kind(bad):
    d = ellipse(doc())
    at(d, 'P', 'e', 0.5)
    with pytest.raises(ValueError, match='pathKind'):
        native.evaluate(d.doc, inputs={'P': {'kind': 'pathParameter', 'value': 0.5, 'pathKind': bad}})


def test_a_degenerate_conic_leaves_the_point_upstream():
    d = ellipse(doc())
    at(d, 'P', 'e', 0.5)
    ev = native.evaluate(d.doc, inputs={'e_p': {'kind': 'point', 'value': [4, 0]}})
    assert ev.elements['e']['state'] == 'undefined'
    assert ev.elements['P']['reason'] == 'upstream'


# ── graphs ────────────────────────────────────────────────────────────────

def square(d, el_id='f', lo=None, hi=None):
    return d.graph(el_id, op('^', X, n(2)), lo=lo, hi=hi)


def test_graph_parameter_is_the_abscissa():
    d = square(doc())
    at(d, 'P', 'f', 1.5)
    near(value(native.evaluate(d.doc), 'P'), (1.5, 2.25))
    checks_pass(d)


@pytest.mark.parametrize('t,want', [(0.5, (0.5, 0.25)), (3.0, (2.0, 4.0)), (-5.0, (-1.0, 1.0)),
                                    (2.0, (2.0, 4.0)), (-1.0, (-1.0, 1.0))])
def test_a_domain_clamps_the_parameter_to_its_ends(t, want):
    d = square(doc(), lo=-1, hi=2)
    at(d, 'P', 'f', t)
    near(value(native.evaluate(d.doc), 'P'), want)
    checks_pass(d)


def test_piecewise_branches_and_a_gap():
    # x < 0: −x; 0 ≤ x < 1: no value; x ≥ 1: x − 1 (a jump at 0 into a gap, a new branch at 1)
    cond = {'if': [{'cmp': '<', 'args': [X, n(0)]}, op('-', n(0), X),
                   {'if': [{'cmp': '>=', 'args': [X, n(1)]}, op('-', X, n(1))]}]}
    d = doc().graph('f', cond)
    for t, want in ((-2.0, (-2.0, 2.0)), (1.0, (1.0, 0.0)), (3.0, (3.0, 2.0))):
        at(d, 'P', 'f', t)
        near(value(native.evaluate(d.doc), 'P'), want)
    at(d, 'P', 'f', 0.5)
    assert value(native.evaluate(d.doc), 'P') == 'out_of_domain'


def test_a_pole_has_no_point():
    d = doc().graph('f', op('/', n(1), X))
    at(d, 'P', 'f', 0.0)
    assert value(native.evaluate(d.doc), 'P') == 'out_of_domain'
    at(d, 'P', 'f', 0.5)
    near(value(native.evaluate(d.doc), 'P'), (0.5, 2.0))


# ── the kernel helpers ────────────────────────────────────────────────────

def test_frames_of_the_new_paths():
    ev = native.evaluate(hyperbola(square(doc())).doc)
    f = paths.frame('conic', ev.elements['h']['value'])
    assert f.kind == 'conic' and f.curve['kind'] == 'hyperbola'
    assert paths.parameter_range(f) == (None, None)
    assert paths.outside(f) == 'none'
    g = paths.frame('function', ev.elements['f']['value'])
    assert g.kind == 'graph' and paths.parameter_range(g) == (None, None) and paths.outside(g) == 'none'
    e = paths.frame('conic', native.evaluate(ellipse(doc()).doc).elements['e']['value'])
    assert paths.parameter_range(e) == (0.0, 2 * math.pi) and paths.outside(e) == 'wrap'
    d = paths.frame('function', native.evaluate(square(doc(), lo=-1, hi=2).doc).elements['f']['value'])
    assert paths.parameter_range(d) == (-1, 2) and paths.outside(d) == 'clamp'


def test_distance_to_the_new_paths():
    ev = native.evaluate(hyperbola(square(doc())).doc)
    assert paths.distance_to_path(3, 0, 'conic', ev.elements['h']['value']) == pytest.approx(0)
    assert paths.distance_to_path(2, 0, 'conic', ev.elements['h']['value']) > 0
    assert paths.distance_to_path(2, 4, 'function', ev.elements['f']['value']) == pytest.approx(0)
    assert paths.distance_to_path(2, 5, 'function', ev.elements['f']['value']) == pytest.approx(1)
