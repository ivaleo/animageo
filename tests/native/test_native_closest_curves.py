"""The closest point of a conic and of a graph: ``point.closest`` (registry 1.9;
docs/native/ops/point.closest.md)."""
import math
import random

import pytest

from animageo import native
from animageo.native.kernel import paths
from animageo.native.kernel.evaluate import evaluate as kernel_evaluate
from tests.native.conftest import ref
from tests.native.test_native_intersect_conics import X, checks_pass, n, op
from tests.native.test_native_path_curves import doc, ellipse, hyperbola, near, square, value


def closest(d, el_id, path, x, y):
    d.at(el_id + '_p', x, y)
    return d.op('op_' + el_id, 'point.closest', {'path': ref(path), 'point': ref(el_id + '_p')},
                [('foot', el_id, 'point')])


def foot(d, el_id, x, y):
    return value(native.evaluate(d.doc, inputs={el_id + '_p': {'kind': 'point', 'value': [x, y]}}), el_id)


def brute(curve, branches, ts, x, y):
    """The least distance from (x, y) to the samples of the curve."""
    best = math.inf
    for b in branches:
        for t in ts:
            p = paths.point_at(curve, t, b)
            best = min(best, math.hypot(p['x'] - x, p['y'] - y))
    return best


def spread(lo, hi, count):
    return [lo + (hi - lo) * k / count for k in range(count + 1)]


def test_a_conic_needs_registry_1_9():
    d = closest(ellipse(doc()), 'P', 'e', 6, 1)
    assert native.min_registry_version(d.doc) == '1.9'
    d.doc['operationRegistryVersion'] = '1.8'
    assert [i.code for i in native.validate(d.doc)] == ['needs_newer_registry']


# ── conics ────────────────────────────────────────────────────────────────

def test_ellipse_closest_points():
    d = closest(ellipse(doc()), 'P', 'e', 6, 0)
    near(foot(d, 'P', 6, 0), (5, 0))
    near(foot(d, 'P', 5 * math.cos(1), 3 * math.sin(1)), (5 * math.cos(1), 3 * math.sin(1)))
    near(foot(d, 'P', 0, -7), (0, -3))
    # inside, on the major axis before the centre of curvature: two feet, the side +n
    q = 5 / 16
    near(foot(d, 'P', 1, 0), (5 * q, 3 * math.sqrt(1 - q * q)))
    near(foot(d, 'P', -1, 0), (-5 * q, 3 * math.sqrt(1 - q * q)))
    near(foot(d, 'P', 0, 0), (0, 3))
    checks_pass(d)


def test_circle_conic_closest_point_is_radial():
    d = doc().five('k', (2, 0), (-2, 0), (0, 2), (0, -2), (math.sqrt(2), math.sqrt(2)))
    closest(d, 'P', 'k', 4, 4)
    near(value(native.evaluate(d.doc), 'P'), (math.sqrt(2), math.sqrt(2)))
    near(foot(d, 'P', 0, 0), (2, 0))


@pytest.mark.parametrize('kind', ['ellipse', 'turned', 'hyperbola', 'parabola'])
def test_conic_closest_point_beats_the_samples(kind):
    rng = random.Random(7)
    if kind == 'parabola':
        d = doc().parabola('q', focus=(1, 2), d1=(-3, -1), d2=(2, 0))
        branches, ts = (1,), spread(-12, 12, 24000)
    elif kind == 'hyperbola':
        d = hyperbola(doc(), 'q')
        branches, ts = (1, -1), spread(-4, 4, 16000)
    else:
        u = (math.cos(0.6), math.sin(0.6)) if kind == 'turned' else (1, 0)
        d = doc().ellipse('q', (1 - 4 * u[0], -1 - 4 * u[1]), (1 + 4 * u[0], -1 + 4 * u[1]),
                          (1 + 5 * u[0], -1 + 5 * u[1]))
        branches, ts = (1,), spread(0, 2 * math.pi, 20000)
    closest(d, 'P', 'q', 0, 0)
    curve = paths.frame('conic', native.evaluate(d.doc).elements['q']['value'])
    for _ in range(40):
        x, y = rng.uniform(-9, 9), rng.uniform(-9, 9)
        got = foot(d, 'P', x, y)
        assert paths.distance_to_path(*got, 'conic', curve.curve) < 1e-9
        assert math.hypot(got[0] - x, got[1] - y) <= brute(curve, branches, ts, x, y) + 1e-9


def test_hyperbola_closest_point_takes_the_nearest_branch():
    d = closest(hyperbola(doc()), 'P', 'h', 5, 0)
    near(foot(d, 'P', 5, 0), (3, 0))
    near(foot(d, 'P', -5, 0), (-3, 0))
    # the conjugate axis: the branch +1; y = b²·Y/(a² + b²)
    y = 16 * 3 / 25
    near(foot(d, 'P', 0, 3), (3 * math.sqrt(1 + y * y / 16), y))
    # past the centre of curvature on the axis: two feet, the smaller parameter (below)
    x0 = 9 * 20 / 25
    near(foot(d, 'P', 20, 0), (x0, -4 * math.sqrt(x0 * x0 / 9 - 1)))
    near(foot(d, 'P', -20, 0), (-x0, -4 * math.sqrt(x0 * x0 / 9 - 1)))
    checks_pass(d)


def test_parabola_closest_point_on_the_axis():
    # focus (0, 1), directrix y = −1: y = x²/4, n = (−1, 0)
    d = closest(doc().parabola('q'), 'P', 'q', 0, -3)
    near(foot(d, 'P', 0, -3), (0, 0))
    near(foot(d, 'P', 0, 1.5), (0, 0))          # not past the centre of curvature (p = 2)
    near(foot(d, 'P', 0, 5), (2 * math.sqrt(3), 3))       # t = −√3: the side −n
    near(foot(d, 'P', -2, 1), (-2, 1))
    checks_pass(d)


def test_closest_records_its_decisions():
    d = closest(hyperbola(doc()), 'P', 'h', 0, 1)
    decisions = []
    kernel_evaluate(d.doc, _decisions=decisions)
    names = {name for _op, name, _v, _tol in decisions if _op == 'op_P'}
    assert names == {'closest_axis', 'closest_branch'}


# ── graphs ────────────────────────────────────────────────────────────────

def test_graph_closest_point():
    d = closest(square(doc()), 'P', 'f', 0, 3)
    got = foot(d, 'P', 0, 3)
    # d² = x² + (x² − 3)²: x² = 5/2, the smaller x first
    near(got, (-math.sqrt(2.5), 2.5), 1e-7)
    near(foot(d, 'P', 2, 4), (2, 4), 1e-7)
    near(foot(d, 'P', 0, -1), (0, 0), 1e-7)
    checks_pass(d)


def test_graph_closest_point_stays_in_the_domain():
    d = closest(square(doc(), lo=-1, hi=2), 'P', 'f', 5, 5)
    near(foot(d, 'P', 5, 5), (2, 4))
    near(foot(d, 'P', -5, 0), (-1, 1))
    near(foot(d, 'P', 100, 0), (2, 4))                 # far outside the window
    checks_pass(d)


def test_graph_closest_point_of_a_piecewise_graph():
    # x < 0: −x; 0 ≤ x < 1: no value; x ≥ 1: x − 1
    cond = {'if': [{'cmp': '<', 'args': [X, n(0)]}, op('-', n(0), X),
                   {'if': [{'cmp': '>=', 'args': [X, n(1)]}, op('-', X, n(1))]}]}
    d = closest(doc().graph('f', cond), 'P', 'f', 0.3, -0.5)
    near(foot(d, 'P', 0.3, -0.5), (0, 0), 1e-7)        # the open end of the left piece
    near(foot(d, 'P', 0.8, -0.5), (1, 0), 1e-7)        # the closed end of the right piece
    near(foot(d, 'P', 4, 0), (2.5, 1.5), 1e-7)


def test_a_graph_without_a_value_has_no_closest_point():
    d = closest(doc().graph('f', {'fn': 'sqrt', 'args': [X]}, lo=-5, hi=-1), 'P', 'f', 0, 0)
    assert value(native.evaluate(d.doc), 'P') == 'out_of_domain'


def test_graph_search_reads_the_window_of_the_document():
    # x > 50: y = 0, else y = 70; from (0, 0) the near piece starts at x = 50
    step = {'if': [{'cmp': '>', 'args': [X, n(50)]}, n(0), n(70)]}
    d = closest(doc().graph('f', step), 'P', 'f', 0, 0)
    d.doc['viewDefaults'] = {'bounds': [-10, -10, 10, 10]}      # the window B4: x in [−40, 40]
    near(value(native.evaluate(d.doc), 'P'), (0, 70), 1e-7)
    d.doc['viewDefaults'] = {'bounds': [-20, -10, 20, 10]}      # x in [−80, 80]
    near(value(native.evaluate(d.doc), 'P'), (50, 0), 1e-7)
