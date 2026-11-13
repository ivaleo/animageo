"""Geometric fill domains and structural display ordering."""
import math

import pytest


def test_large_late_fill_precedes_small_early_fill():
    from animageo.fill_order import FillPart, order_fills
    parts = [FillPart('small', 0, (0, 0, 0), 1, .01, True),
             FillPart('large', 1, (0, 1, 0), 9, .01, True)]
    assert order_fills(parts, mode='area') == ('large', 'small')
    assert order_fills(parts, mode='construction') == ('small', 'large')
    assert parts[0].id == 'small'


def test_equality_groups_use_largest_reference_without_chaining():
    from animageo.fill_order import FillPart, order_fills
    parts = [FillPart('small', 0, (0,), 1 - 1.5e-9, .01, True),
             FillPart('near', 1, (1,), 1 - .75e-9, .01, True),
             FillPart('large', 2, (2,), 1, .01, True)]
    assert order_fills(parts, mode='area') == ('near', 'large', 'small')


def test_fixed_slots_and_nonfill_slots_keep_exact_effective_layers():
    from animageo.fill_order import FillPart, PaintPart, order_fills, order_paint_parts
    fills = [FillPart('small', 0, (0,), 1, .01, True),
             FillPart('fixed', 1, (1,), 100, .01, False),
             FillPart('large', 2, (3,), 9, .01, True),
             FillPart('above', 3, (4,), 1000, .0100000001, False)]
    order = order_fills(fills, mode='area')
    assert order == ('large', 'fixed', 'small', 'above')
    parts = [PaintPart('small', 'fill', .01, (0,)), PaintPart('fixed', 'fill', .01, (1,)),
             PaintPart('line', 'stroke', .01, (2,)), PaintPart('large', 'fill', .01, (3,)),
             PaintPart('above', 'fill', .0100000001, (4,))]
    assert order_paint_parts(parts, order) == (
        {'id': 'large', 'part': 'fill'}, {'id': 'fixed', 'part': 'fill'},
        {'id': 'line', 'part': 'stroke'}, {'id': 'small', 'part': 'fill'},
        {'id': 'above', 'part': 'fill'})


@pytest.mark.parametrize('rule,expected', [('nonzero', 4), ('evenodd', 0)])
def test_repeated_square_uses_painter_rule(rule, expected):
    from animageo.fill_order import polygon_area
    square = [(0, 0), (2, 0), (2, 2), (0, 2)]
    assert polygon_area(square * 2, rule=rule) == pytest.approx(expected)
    assert polygon_area(square + [square[0]] + list(reversed(square)), rule=rule) == 0


def test_self_intersections_and_degenerate_edges():
    from animageo.fill_order import polygon_area
    assert polygon_area([(0, 0), (2, 2), (0, 2), (2, 0)]) == pytest.approx(2)
    points = [(math.cos(i * 4 * math.pi / 5), math.sin(i * 4 * math.pi / 5)) for i in range(5)]
    assert polygon_area(points, rule='nonzero') > polygon_area(points, rule='evenodd') > 0
    assert polygon_area([(0, 0), (0, 0), (1, 0), (2, 0)]) == 0
    assert polygon_area([(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)]) == 3


def test_thin_and_major_circle_segments():
    from animageo.fill_order import circle_segment_area
    assert circle_segment_area(2, 1e-9) == pytest.approx(4e-27 / 12, rel=1e-12, abs=0)
    assert circle_segment_area(2, 3 * math.pi / 2) == pytest.approx(2 * (3 * math.pi / 2 + 1))
    assert circle_segment_area(2, 2 * math.pi) == pytest.approx(4 * math.pi)


def test_geometry_adapter_uses_ideal_domains_and_style_units():
    from types import SimpleNamespace
    from animageo.fill_order import fill_area
    from animageo.geo.lib_elements import Circle, CircleSector, CircleSegment, Arc, Polygon
    from animageo.geo.lib_conic import Conic
    scene = SimpleNamespace(style=SimpleNamespace(export={'ptUnit_style': 10, 'ptUnit': 999}))
    def area(data):
        return fill_area(scene, SimpleNamespace(data=data, style={}), mode='area')
    assert area(Circle([4, 5], 2)) == pytest.approx(400 * math.pi)
    assert area(Polygon([[0, 0], [2, 2], [0, 2], [2, 0]])) == 200
    assert area(Conic.from_string('x^2/4 + y^2 = 1')) == pytest.approx(200 * math.pi)
    assert area(CircleSector([0, 0], 2, [0, math.pi / 2])) == pytest.approx(100 * math.pi)
    assert area(CircleSegment([0, 0], 2, [0, math.pi / 2])) == pytest.approx(200 * (math.pi / 2 - 1))
    arc = Arc([0, 0], 2, [0, 2 * math.pi])
    arc.native_value = {'angles': [0, 2 * math.pi]}
    arc.angles = [0, 2 * math.pi]
    assert area(arc) == pytest.approx(400 * math.pi)
    assert fill_area(scene, SimpleNamespace(data=arc, style={}), mode='construction') == 0


def test_geometry_adapter_uses_actual_marker_extent():
    from types import SimpleNamespace
    from animageo.fill_order import fill_area
    from animageo.geo.lib_elements import Angle
    from animageo.style.config import StyleConfig
    cfg = StyleConfig.load({'defaults': {'angle': {'right_angle_size_px': 20}}})
    scene = SimpleNamespace(style_config=cfg, style=SimpleNamespace(export={'ptUnit_style': 10}, rendering={}))
    elem = SimpleNamespace(name='angle', data=Angle([0, 0], [1, 0], [0, 1]), style={})
    assert fill_area(scene, elem, mode='area') == pytest.approx(200)
    elem.style.update(right_angle_marker=False, arc_size_px=10, tick_count=3, arc_shift_px=2)
    assert fill_area(scene, elem, mode='area') == pytest.approx(14**2 * math.pi / 4)


@pytest.mark.parametrize('k', [.01, 1, 100])
def test_polygon_area_is_translation_rotation_and_unit_invariant(k):
    from animageo.fill_order import polygon_area
    points = [(0, 0), (3, 3), (0, 3), (3, 0)]
    a = math.radians(37)
    transformed = [(k*(x*math.cos(a)-y*math.sin(a))+7, k*(x*math.sin(a)+y*math.cos(a))-2) for x, y in points]
    assert polygon_area(transformed)/k**2 == pytest.approx(polygon_area(points), rel=1e-10)


def test_epsilon_boundary_is_inclusive_and_uses_construction_index():
    from animageo.fill_order import FillPart, order_fills
    ref = 1e9
    delta = 1.0
    small = ref - delta
    parts = [FillPart('z', 0, (0,), small, .01, True), FillPart('a', 1, (1,), ref, .01, True)]
    assert order_fills(parts, mode='area') == ('z', 'a')


@pytest.mark.parametrize('rule', ['nonzero', 'evenodd'])
def test_rotated_reverse_edges_cancel_exactly(rule):
    from animageo.fill_order import polygon_area
    a = .37
    points = [(math.cos(a)*x-math.sin(a)*y, math.sin(a)*x+math.cos(a)*y)
              for x, y in ((0, 0), (2, 0), (2, 2), (0, 2))]
    assert polygon_area(points + [points[0]] + list(reversed(points)), rule=rule) == 0
