"""The value of a region (registry 1.9; docs/native/kernel.md §16): signed
areas of the pieces, flattening, the even-odd test and the label spot."""
import math

import pytest

from animageo.native.kernel import region as R


def circle_ring(cx, cy, r, kind='ccw'):
    p = [cx + r, cy]
    return [[p, p, [cx, cy, r]]], [[kind, 'inside.0']]       # one ring and its shape


def test_graph_xs_end_exactly():
    xs = R.graph_xs(-0.1, 0.7)
    assert len(xs) == R.GRAPH_STEPS + 1
    assert xs[0] == -0.1 and xs[-1] == 0.7
    assert xs[128] == pytest.approx(0.3)


def test_line_area_closes_a_square():
    sq = [[0, 0], [2, 0], [2, 2], [0, 2]]
    total = sum(R.line_area(sq[i], sq[(i + 1) % 4]) for i in range(4))
    assert total == pytest.approx(4.0)
    assert sum(R.line_area(sq[(i + 1) % 4], sq[i]) for i in range(4)) == pytest.approx(-4.0)


@pytest.mark.parametrize('cx, cy', [(0.0, 0.0), (3.0, -2.0)])
def test_arc_area_whole_circle(cx, cy):
    ring, shape = circle_ring(cx, cy, 2.0)
    assert R.arc_area(ring[0], 'ccw') == pytest.approx(math.pi * 4)
    assert R.arc_area(ring[0], 'cw') == pytest.approx(-math.pi * 4)


def test_arc_area_half_disc_with_its_diameter():
    # upper half disc: arc ccw from (1, 0) to (-1, 0), then the diameter back
    arc = [[1.0, 0.0], [-1.0, 0.0], [0.0, 0.0, 1.0]]
    total = R.arc_area(arc, 'ccw') + R.line_area([-1.0, 0.0], [1.0, 0.0])
    assert total == pytest.approx(math.pi / 2)
    # the same chord walked the other way round the lower half: clockwise arc
    assert R.arc_area(arc, 'cw') + R.line_area([-1.0, 0.0], [1.0, 0.0]) == pytest.approx(-math.pi / 2)


def test_arc_sweep_signs():
    arc = [[1.0, 0.0], [0.0, 1.0], [0.0, 0.0, 1.0]]
    assert R.arc_sweep(arc, 'ccw')[1] == pytest.approx(math.pi / 2)
    assert R.arc_sweep(arc, 'cw')[1] == pytest.approx(-3 * math.pi / 2)


def test_graph_area_simpson_is_exact_on_a_parabola():
    xs = R.graph_xs(-1.0, 1.0)
    pts = [[x, 1 - x * x] for x in xs]
    mids = [1 - ((a + (b - a) / 2) ** 2) for a, b in zip(xs, xs[1:])]
    # −∫ y dx from −1 to 1 of 1 − x² is −4/3
    assert R.graph_area(pts, mids) == pytest.approx(-4 / 3, abs=1e-14)


def _parabola_lobe():
    xs = R.graph_xs(1.0, -1.0)
    upper = [[x, 1 - x * x] for x in xs]
    axis = [[-1.0, 0.0], [1.0, 0.0]]
    return {'rings': [[axis, upper]], 'shape': [[['line', 'axis'], ['graph', 'first']]], 'area': 4 / 3}


def test_perimeter_and_flatten():
    v = _parabola_lobe()
    rings = R.flatten(v)
    assert len(rings) == 1 and len(rings[0]) == 1 + R.GRAPH_STEPS
    arc_len = 2 * 1.4789428575445975                 # ∫ sqrt(1 + 4x²) on [−1, 1]
    assert R.perimeter(v) == pytest.approx(2 + arc_len, rel=1e-5)


def test_flatten_arc_step_at_most_two_degrees():
    ring, shape = circle_ring(0.0, 0.0, 1.0)
    pts = R.flatten({'rings': [ring], 'shape': [shape]})[0]
    assert len(pts) == 180
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        assert math.atan2(x0 * y1 - x1 * y0, x0 * x1 + y0 * y1) == pytest.approx(math.radians(2))


def test_inside_even_odd_with_a_hole():
    outer, so = circle_ring(0.0, 0.0, 2.0, 'ccw')
    hole, sh = circle_ring(0.0, 0.0, 1.0, 'cw')
    rings = R.flatten({'rings': [outer, hole], 'shape': [so, sh]})
    assert R.inside(rings, 1.5, 0.1)
    assert not R.inside(rings, 0.2, 0.1)
    assert not R.inside(rings, 3.0, 0.0)


def test_label_anchor_centroid_inside():
    x, y = R.label_anchor(_parabola_lobe())
    assert x == pytest.approx(0.0, abs=1e-9)
    assert y == pytest.approx(0.4, abs=1e-4)          # centroid of the lobe of 1 − x²: 2/5


def test_label_anchor_annulus_moves_off_the_hole():
    outer, so = circle_ring(0.0, 0.0, 2.0, 'ccw')
    hole, sh = circle_ring(0.0, 0.0, 1.0, 'cw')
    x, y = R.label_anchor({'rings': [outer, hole], 'shape': [so, sh]})
    assert abs(y) < 1e-9
    assert abs(abs(x) - 1.5) < 1e-3
