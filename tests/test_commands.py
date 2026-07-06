"""Tests for geometric commands (lib_commands.py).

Covers: basic operations, intersections, boolean tests, transformations.
"""
import numpy as np
import pytest

from animageo.geo.lib_elements import (
    Point, Line, Segment, Ray, Angle, Polygon, Circle, Arc, CircleSector, Vector,
    Conic,
)
from animageo.geo.lib_vars import Measure, AngleSize, Boolean
from animageo.geo.lib_commands import (
    Command, strFullCommand, strParams, strCommand,
    midpoint_pp, distance_pp, distance_pl, distance_ps, distance_pc,
    segment_pp, line_pp,
    circle_ppp, circle_pp, intersect_ll, intersect_lc, intersect_cc,
    intersect_Cri, intersect_Csi,
    angle_ppp, angle_size_ppp, circumcircle_arc_ppp,
    polygon, area_P, area_K, length_s, radius_K, perimeter_P, circumference_c,
    point_K, point_r, point_C,
    are_collinear_ppp, are_parallel_ll, are_perpendicular_ll,
    mirror_pl, rotate_pAp, rotate_vap, incircle_ppp,
    isogonal_conjugation_pppp, trilinear_pppiii,
    line_bisector_pp, angular_bisector_ppp,
    add_pp, sub_pp, mult_pi,
    slope_l, direction_l, direction_s, unit_vector_v, unit_vector_s,
    perpendicular_vector_v, perpendicular_vector_l,
    unit_perpendicular_vector_s, dot_vv, cross_vv,
    affine_ratio_ppp, cross_ratio_pppp, midpoint_K, center_K, conic_iiiiii,
    ray_pv, point_pv,
    closest_point_lp, closest_point_sp, closest_point_rp, closest_point_cp,
    dilate_pi, dilate_pip, dilate_pm, dilate_ci, dilate_sip, dilate_Pi,
    dilate_li, polar_lK, polar_Kl, polar_pK,
    tangent_lK, tangent_Kl, tangent_pF, tangent_iF, tangent_mF, tangent_cc,
)
from animageo.geo.lib_function import Function as _Fn


# ── Command dispatch ───────────────────────────────────────────────────

class TestCommandDispatch:
    def test_str_command_camel_to_snake(self):
        assert strCommand('AreCollinear') == 'are_collinear'
        assert strCommand('Midpoint') == 'midpoint'

    def test_str_params(self):
        params = [Point([0, 0]), Point([1, 1])]
        assert strParams(params) == 'pp'

    def test_str_full_command(self):
        params = [Point([0, 0]), Point([1, 1])]
        assert strFullCommand('Midpoint', params) == 'midpoint_pp'

    def test_command_func_found(self):
        cmd = Command('Midpoint', [Point([0, 0]), Point([1, 1])], ['M'])
        f = cmd.func()
        assert f is not None
        assert f.__name__ == 'midpoint_pp'

    def test_command_func_not_found(self):
        cmd = Command('NonExistentCommand', [Point([0, 0])], ['X'])
        f = cmd.func()
        assert f is None

    def test_missing_dispatch_emits_warning(self, caplog):
        """Silent None-fallback was masking typos; there must be a log trail.

        A bogus command name used to produce no output at all — elements
        were silently left unbuilt. The warning now names the command,
        the input types, and the affected outputs so the caller can trace
        back to the offending DSL line.
        """
        import logging
        cmd = Command('NonExistentCommand', [Point([0, 0])], ['X'])
        with caplog.at_level(logging.WARNING, logger='animageo.geo.lib_commands'):
            f = cmd.func()
        assert f is None
        assert any("NonExistentCommand" in rec.message for rec in caplog.records)
        assert any("Point" in rec.message for rec in caplog.records)

    def test_are_congruent_aa_works(self):
        """Regression: used ``.angle`` attribute which doesn't exist on
        Angle (it has ``.size`` / ``.value``). Raised AttributeError
        instead of returning Boolean."""
        a = Angle(np.array([0, 0]), np.array([1, 0]), np.array([0, 1]))
        b = Angle(np.array([0, 0]), np.array([2, 0]), np.array([0, 3]))
        from animageo.geo.lib_commands import are_congruent_aa, are_complementary_aa
        result = are_congruent_aa(a, b)
        assert bool(result.value) is True
        c = Angle(np.array([0, 0]), np.array([1, 0]), np.array([-1, 1e-6]))
        # 90° + ~180° ≈ not complementary (would sum to ~270°, not 180°)
        # Use safer check: 90° + 90° = 180° — congruent (not complementary).
        result = are_complementary_aa(a, b)
        # a+b ≈ π/2 + π/2 = π → matches "sum mod 2π ≈ π" → True
        assert bool(result.value) is True

    def test_command_registry_populated(self):
        """The explicit COMMAND_REGISTRY replaces ``globals()`` dispatch —
        verifies it contains the common commands and has sensible size."""
        from animageo.geo.lib_commands import COMMAND_REGISTRY, list_commands
        # Core commands reachable through dispatch.
        for name in ('midpoint_pp', 'intersect_ll', 'angle_ppp', 'polygon',
                     'distance_pp', 'line_pp', 'circle_pp'):
            assert name in COMMAND_REGISTRY, f"missing: {name}"
        # Size sanity — lib_commands has ~300 functions, dispatch registry
        # should be most of them (~290).
        assert len(COMMAND_REGISTRY) > 200
        # list_commands returns sorted names.
        names = list_commands()
        assert names == sorted(names)
        assert len(names) == len(COMMAND_REGISTRY)

    def test_polygon_dispatch_special(self):
        """polygon command with only points should dispatch to 'polygon' (no type suffix)."""
        params = [Point([0, 0]), Point([1, 0]), Point([0, 1])]
        assert strFullCommand('Polygon', params) == 'polygon'

    def test_geogebra_public_name_aliases_dispatch(self):
        p1 = Point([0, 0])
        p2 = Point([1, 0])
        p3 = Point([0, 1])
        line = Line([0, 1], 0)

        cases = [
            ('PerpendicularLine', [p1, line], 'perpendicular_line_pl'),
            ('PerpendicularBisector', [p1, p2], 'perpendicular_bisector_pp'),
            ('Reflect', [p3, line], 'reflect_pl'),
            ('CircularArc', [p1, p2, p3], 'circular_arc_ppp'),
            ('CircularSector', [p1, p2, p3], 'circular_sector_ppp'),
            ('CircumcircularArc', [p1, p2, p3], 'circumcircular_arc_ppp'),
            ('CircumcircularSector', [p1, p2, p3], 'circumcircular_sector_ppp'),
        ]
        for command_name, inputs, impl_name in cases:
            f = Command(command_name, inputs, ['out']).func()
            assert f is not None
            assert f.__name__ == impl_name


# ── Basic operations ───────────────────────────────────────────────────

class TestBasicOperations:
    def test_midpoint(self):
        m = midpoint_pp(Point([0, 0]), Point([4, 6]))
        assert np.allclose(m.coords, [2, 3])

    def test_distance(self):
        d = distance_pp(Point([0, 0]), Point([3, 4]))
        assert isinstance(d, Measure)
        assert np.isclose(d.value, 5)

    def test_distance_point_line_segment_circle(self):
        p = Point([3, 4])
        line = Line([0, 1], 0)
        seg = Segment(np.array([0, 0]), np.array([2, 0]))
        circle = Circle([0, 0], 5)

        assert np.isclose(distance_pl(p, line).value, 4)
        assert np.isclose(distance_ps(p, seg).value, np.sqrt(17))
        assert np.isclose(distance_pc(p, circle).value, 0)

    def test_segment(self):
        s = segment_pp(Point([1, 2]), Point([4, 6]))
        assert isinstance(s, Segment)
        assert np.isclose(s.length, 5)

    def test_line_from_two_points(self):
        l = line_pp(Point([0, 0]), Point([1, 0]))
        assert isinstance(l, Line)
        assert l.contains(np.array([5, 0]))

    def test_point_on_hyperbola_conic(self):
        c = Conic.from_coeffs(a=1 / 4, c=-1 / 9, f=-1)
        p1 = point_K(c, (1, 0))
        p2 = point_K(c, (-1, 0))

        assert isinstance(p1, Point)
        assert isinstance(p2, Point)
        assert np.allclose(p1.coords, [2, 0])
        assert np.allclose(p2.coords, [-2, 0])

    def test_point_on_ray_with_tparam(self):
        ray = Ray(np.array([1.0, 2.0]), np.array([3.0, 0.0]))
        p = point_r(ray, 2.0)
        assert isinstance(p, Point)
        assert ray.contains(p.coords)
        assert np.allclose(p.coords, [3.0, 2.0])

    def test_point_on_arc_with_absolute_angle_tparam(self):
        arc = Arc([0, 0], 2, [0, np.pi])
        p = point_C(arc, np.pi / 2)
        assert isinstance(p, Point)
        assert arc.contains(p.coords)
        assert np.allclose(p.coords, [0, 2], atol=1e-12)


# ── Circle operations ─────────────────────────────────────────────────

class TestCircleOperations:
    def test_circle_from_two_points(self):
        # circle_pp(center, passing_point) — center is p1, radius = dist(p1, p2)
        c = circle_pp(Point([0, 0]), Point([4, 0]))
        assert isinstance(c, Circle)
        assert np.allclose(c.center, [0, 0])
        assert np.isclose(c.radius, 4)

    def test_circle_from_three_points(self):
        c = circle_ppp(Point([0, 0]), Point([4, 0]), Point([0, 4]))
        assert isinstance(c, Circle)

    def test_circumcircle_arc_passes_through_middle_point_across_zero_angle(self):
        a = Point([1.24, 0.28])
        middle = Point([2.2183178876022938, -1.43629687671735])
        b = Point([8.14, 0.28])

        arc = circumcircle_arc_ppp(a, middle, b)
        mid_angle = (arc.angles[0] + arc.angles[1]) / 2
        arc_midpoint = arc.center + arc.radius * np.array([np.cos(mid_angle), np.sin(mid_angle)])

        assert arc.contains(middle.coords)
        assert arc_midpoint[1] < a.coords[1]

    def test_intersect_arc_ray_indexed(self):
        arc = circumcircle_arc_ppp(
            Point([-6.93, -0.72]),
            Point([-4.21, -1.68]),
            Point([-2.07, -0.72]),
        )
        ray = Ray(np.array([-4.5, 5.12]), np.array([-5.31, -0.72]) - np.array([-4.5, 5.12]))

        p = intersect_Cri(arc, ray, 1)

        assert isinstance(p, Point)
        assert np.allclose(p.coords, [-5.427571172216735, -1.567673636723131], atol=1e-9)

    def test_intersect_arc_segment_indexed_filters_to_arc(self):
        arc = Arc([0, 0], 5, [np.pi, 2 * np.pi])
        segment = Segment(np.array([-6, 0]), np.array([6, 0]))

        p = intersect_Csi(arc, segment, 1)

        assert isinstance(p, Point)
        assert np.allclose(p.coords, [-5, 0])


# ── Intersection ───────────────────────────────────────────────────────

class TestIntersection:
    def test_intersect_two_lines(self):
        l1 = Line([0, 1], 0)   # y = 0
        l2 = Line([1, 0], 3)   # x = 3
        p = intersect_ll(l1, l2)
        assert isinstance(p, Point)
        assert np.allclose(p.coords, [3, 0])

    def test_intersect_line_circle(self):
        l = Line([0, 1], 0)  # y = 0
        c = Circle([0, 0], 5)
        result = intersect_lc(l, c)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_intersect_two_circles(self):
        c1 = Circle([0, 0], 5)
        c2 = Circle([6, 0], 5)
        result = intersect_cc(c1, c2)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_intersect_concentric_circles(self):
        """Concentric circles with different radii have no discrete intersection."""
        c1 = Circle([3, 4], 5)
        c2 = Circle([3, 4], 7)
        assert intersect_cc(c1, c2) is None

    def test_intersect_identical_circles(self):
        """Identical circles have no discrete intersection (infinite overlap)."""
        c1 = Circle([0, 0], 5)
        c2 = Circle([0, 0], 5)
        assert intersect_cc(c1, c2) is None

    def test_intersect_tangent_circles(self):
        """Externally tangent circles have exactly one intersection point."""
        c1 = Circle([0, 0], 3)
        c2 = Circle([5, 0], 2)
        result = intersect_cc(c1, c2)
        assert isinstance(result, Point)
        assert np.allclose(result.coords, [3, 0])

    def test_intersect_non_intersecting_circles(self):
        """Far apart circles have no intersection."""
        c1 = Circle([0, 0], 1)
        c2 = Circle([10, 0], 1)
        assert intersect_cc(c1, c2) is None

    def test_intersect_circle_segment_no_points_returns_none(self):
        c = Circle([0, 0], 1)
        s = Segment(np.array([3, 0]), np.array([4, 0]))
        from animageo.geo.lib_commands import intersect_cs
        assert intersect_cs(c, s) is None

    def test_intersect_function_segment_and_ray(self):
        from animageo.geo.lib_function import Function
        from animageo.geo.lib_commands import intersect_Fs, intersect_Fr

        f = Function.from_string('y = x')
        seg = Segment(np.array([-1.0, 0.0]), np.array([1.0, 0.0]))
        ray = Ray(np.array([0.0, 0.0]), np.array([1.0, 0.0]))

        p_seg = intersect_Fs(f, seg)
        p_ray = intersect_Fr(f, ray)

        assert isinstance(p_seg, Point)
        assert isinstance(p_ray, Point)
        assert np.allclose(p_seg.coords, [0, 0])
        assert np.allclose(p_ray.coords, [0, 0])

    def test_intersect_arc_circle_arc_and_conic(self):
        from animageo.geo.lib_commands import intersect_Cc, intersect_CC, intersect_CK

        arc1 = Arc([0, 0], 5, [0, np.pi])
        circle = Circle([3, 0], 4)
        arc2 = Arc([3, 0], 4, [np.pi / 2, np.pi])
        conic_circle = Conic.from_coeffs(a=1, c=1, d=-6, f=9 - 16)

        p1 = intersect_Cc(arc1, circle)
        p2 = intersect_CC(arc1, arc2)
        p3 = intersect_CK(arc1, conic_circle)

        assert isinstance(p1, list)
        assert all(arc1.contains(p.coords) and circle.contains(p.coords) for p in p1)
        assert isinstance(p2, list)
        assert all(arc1.contains(p.coords) and arc2.contains(p.coords) for p in p2)
        assert isinstance(p3, list)
        assert all(arc1.contains(p.coords) and conic_circle.contains(p.coords) for p in p3)


# ── Angle operations ──────────────────────────────────────────────────

class TestAngleOperations:
    def test_angle_from_three_points(self):
        a = angle_ppp(Point([1, 0]), Point([0, 0]), Point([0, 1]))
        assert isinstance(a, Angle)
        assert np.isclose(a.size, np.pi / 2)

    def test_angle_size_from_three_points(self):
        a = angle_size_ppp(Point([1, 0]), Point([0, 0]), Point([0, 1]))
        assert isinstance(a, AngleSize)


# ── Boolean tests ─────────────────────────────────────────────────────

class TestBooleanTests:
    def test_collinear(self):
        result = are_collinear_ppp(Point([0, 0]), Point([1, 1]), Point([2, 2]))
        assert isinstance(result, Boolean)
        assert result.value

    def test_not_collinear(self):
        result = are_collinear_ppp(Point([0, 0]), Point([1, 0]), Point([0, 1]))
        assert not result.value

    def test_parallel_lines(self):
        l1 = Line([0, 1], 0)  # y = 0
        l2 = Line([0, 1], 5)  # y = 5
        result = are_parallel_ll(l1, l2)
        assert result.value

    def test_perpendicular_lines(self):
        l1 = Line([0, 1], 0)  # y = 0
        l2 = Line([1, 0], 0)  # x = 0
        result = are_perpendicular_ll(l1, l2)
        assert result.value


# ── Polygon and area ──────────────────────────────────────────────────

class TestPolygon:
    def test_polygon_creation(self):
        p = polygon(Point([0, 0]), Point([4, 0]), Point([4, 3]), Point([0, 3]))
        # polygon returns [Polygon, Segment, Segment, ...]
        assert isinstance(p, list)
        assert isinstance(p[0], Polygon)

    def test_area(self):
        poly = Polygon([[0, 0], [4, 0], [4, 3], [0, 3]])
        a = area_P(poly)
        assert isinstance(a, Measure)
        assert np.isclose(a.value, 12)

    def test_length_radius_area_perimeter_circumference(self):
        seg = Segment(np.array([0, 0]), np.array([3, 4]))
        circle = Circle([0, 0], 2)
        conic_circle = Conic.from_coeffs(a=1, c=1, f=-4)
        poly = Polygon([[0, 0], [4, 0], [4, 3], [0, 3]])

        assert np.isclose(length_s(seg).value, 5)
        assert np.isclose(radius_K(conic_circle).value, 2)
        assert np.isclose(area_K(conic_circle).value, 4 * np.pi)
        assert np.isclose(perimeter_P(poly).value, 14)
        assert np.isclose(circumference_c(circle).value, 4 * np.pi)


# ── Transformations ───────────────────────────────────────────────────

class TestTransformations:
    def test_mirror_point_over_line(self):
        p = Point([0, 2])
        l = Line([0, 1], 0)  # y = 0
        reflected = mirror_pl(p, l)
        assert isinstance(reflected, Point)
        assert np.allclose(reflected.coords, [0, -2])

    def test_rotation(self):
        p = Point([1, 0])
        center = Point([0, 0])
        angle = AngleSize(np.pi / 2)
        rotated = rotate_pAp(p, angle, center)
        assert isinstance(rotated, Point)
        assert np.allclose(rotated.coords, [0, 1], atol=1e-10)

    def test_rotate_vector_by_angle(self):
        vec = Vector([[0, 0], [1, 0]])
        angle = Angle(np.array([0, 0]), np.array([1, 0]), np.array([0, 1]))
        rotated = rotate_vap(vec, angle, Point([0, 0]))
        assert isinstance(rotated, Vector)
        assert np.allclose(rotated.direction, [0, 1], atol=1e-10)

    def test_incircle(self):
        circle = incircle_ppp(Point([0, 0]), Point([4, 0]), Point([0, 3]))
        assert isinstance(circle, Circle)
        assert np.allclose(circle.center, [1, 1])
        assert np.isclose(circle.radius, 1)

    def test_isogonal_conjugation_centroid_in_equilateral_triangle(self):
        a = Point([0, 0])
        b = Point([2, 0])
        c = Point([1, np.sqrt(3)])
        p = Point([1, np.sqrt(3) / 3])
        q = isogonal_conjugation_pppp(a, b, c, p)
        assert isinstance(q, Point)
        assert np.allclose(q.coords, p.coords)

    def test_trilinear_incenter(self):
        # 1:1:1 → incenter. 3-4-5 right triangle has inradius 1 at (1, 1).
        A, B, C = Point([0, 0]), Point([4, 0]), Point([0, 3])
        p = trilinear_pppiii(A, B, C, 1, 1, 1)
        assert isinstance(p, Point)
        assert np.allclose(p.coords, [1, 1])

    def test_trilinear_centroid(self):
        # 1/a : 1/b : 1/c → centroid (arithmetic mean of the vertices).
        A, B, C = Point([0, 0]), Point([4, 0]), Point([0, 3])
        a = np.linalg.norm(B.coords - C.coords)
        b = np.linalg.norm(C.coords - A.coords)
        c = np.linalg.norm(A.coords - B.coords)
        p = trilinear_pppiii(A, B, C, 1 / a, 1 / b, 1 / c)
        assert np.allclose(p.coords, (A.coords + B.coords + C.coords) / 3)

    def test_trilinear_circumcenter(self):
        # cos A : cos B : cos C → circumcenter (equidistant from vertices).
        A, B, C = Point([0, 0]), Point([4, 0]), Point([0, 3])

        def cos_at(v, u, w):
            e1, e2 = u.coords - v.coords, w.coords - v.coords
            return np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2))

        p = trilinear_pppiii(A, B, C, cos_at(A, B, C), cos_at(B, A, C),
                             cos_at(C, A, B))
        assert np.allclose(p.coords, [2, 1.5])

    def test_trilinear_accepts_measure_ratios(self):
        # Named-number ratios arrive as Measures — coerced via .value.
        A, B, C = Point([0, 0]), Point([4, 0]), Point([0, 3])
        p = trilinear_pppiii(A, B, C, Measure(1), 1, Measure(1))
        assert np.allclose(p.coords, [1, 1])

    def test_trilinear_degenerate_triangle_returns_none(self):
        # Collinear (zero-area) and coincident vertices are undefined.
        assert trilinear_pppiii(Point([0, 0]), Point([1, 0]),
                                Point([2, 0]), 1, 1, 1) is None
        assert trilinear_pppiii(Point([0, 0]), Point([0, 0]),
                                Point([2, 0]), 1, 1, 1) is None


# ── Line operations ───────────────────────────────────────────────────

class TestLineOperations:
    def test_line_bisector(self):
        l = line_bisector_pp(Point([0, 0]), Point([4, 0]))
        assert isinstance(l, Line)
        # bisector of (0,0)-(4,0) passes through (2,0)
        assert l.contains(np.array([2, 0]))

    def test_angular_bisector(self):
        l = angular_bisector_ppp(Point([1, 0]), Point([0, 0]), Point([0, 1]))
        assert isinstance(l, Line)


# ── Arithmetic on points ──────────────────────────────────────────────

class TestArithmetic:
    def test_add_points(self):
        result = add_pp(Point([1, 2]), Point([3, 4]))
        assert isinstance(result, Point)
        assert np.allclose(result.coords, [4, 6])

    def test_sub_points(self):
        # sub_pp returns Point (vector-like subtraction), not Vector
        result = sub_pp(Point([5, 6]), Point([1, 2]))
        assert isinstance(result, Point)
        assert np.allclose(result.coords, [4, 4])

    def test_mult_point_scalar(self):
        result = mult_pi(Point([2, 3]), 3)
        assert isinstance(result, Point)
        assert np.allclose(result.coords, [6, 9])


# ── Point on function graph ───────────────────────────────────────────

class TestPointOnFunction:
    def test_point_F_basic(self):
        from animageo.geo.lib_function import Function
        from animageo.geo.lib_commands import point_F
        f = Function("y = x^2")
        p = point_F(f, 1.5)
        assert np.allclose(p.coords, [1.5, 2.25])

    def test_point_F_default_x_zero(self):
        from animageo.geo.lib_function import Function
        from animageo.geo.lib_commands import point_F
        p = point_F(Function("y = x^2 + 1"))
        assert np.allclose(p.coords, [0.0, 1.0])

    def test_point_F_outside_domain_returns_none(self):
        from animageo.geo.lib_function import Function
        from animageo.geo.lib_commands import point_F
        assert point_F(Function("y = sqrt(x)"), -4.0) is None


# ── Tier A: vector / scalar / point helpers ───────────────────────────

class TestVectorScalarCommands:
    def test_slope(self):
        # line through (0,0),(1,2) has slope 2.
        line = Line(np.array([2.0, -1.0]), 0.0)  # 2x − y = 0 → y = 2x
        assert np.isclose(slope_l(line).value, 2.0)

    def test_slope_vertical_is_none(self):
        assert slope_l(Line(np.array([1.0, 0.0]), 3.0)) is None  # x = 3

    def test_direction_line_is_unit_and_parallel(self):
        line = Line(np.array([0.0, 1.0]), 0.0)  # y = 0 (x-axis)
        v = direction_l(line)
        assert isinstance(v, Vector)
        assert np.isclose(np.linalg.norm(v.direction), 1.0)
        assert np.isclose(v.direction[1], 0.0)  # parallel to x-axis

    def test_direction_segment_keeps_length(self):
        seg = Segment(np.array([0.0, 0.0]), np.array([3.0, 4.0]))
        assert np.isclose(np.linalg.norm(direction_s(seg).direction), 5.0)

    def test_unit_vector_normalizes(self):
        assert np.isclose(
            np.linalg.norm(unit_vector_v(Vector(([0, 0], [3, 4]))).direction), 1.0)
        seg = Segment(np.array([0.0, 0.0]), np.array([3.0, 4.0]))
        assert np.isclose(np.linalg.norm(unit_vector_s(seg).direction), 1.0)

    def test_perpendicular_vector_keeps_magnitude(self):
        pv = perpendicular_vector_v(Vector(([0, 0], [3, 4]))).direction
        assert np.isclose(np.linalg.norm(pv), 5.0)          # not normalized
        assert np.isclose(np.dot(pv, [3, 4]), 0.0)          # orthogonal

    def test_perpendicular_vector_line_is_normal(self):
        line = Line(np.array([0.0, 1.0]), 0.0)  # x-axis, normal (0,1)
        assert np.allclose(perpendicular_vector_l(line).direction, [0, 1])

    def test_unit_perpendicular_vector(self):
        seg = Segment(np.array([0.0, 0.0]), np.array([3.0, 4.0]))
        upv = unit_perpendicular_vector_s(seg).direction
        assert np.isclose(np.linalg.norm(upv), 1.0)
        assert np.isclose(np.dot(upv, [3, 4]), 0.0)

    def test_dot_and_cross(self):
        u, v = Vector(([0, 0], [1, 2])), Vector(([0, 0], [3, 4]))
        assert np.isclose(dot_vv(u, v).value, 11.0)
        assert np.isclose(cross_vv(Vector(([0, 0], [1, 0])),
                                   Vector(([0, 0], [0, 1]))).value, 1.0)

    def test_affine_ratio_manual_example(self):
        # GeoGebra: AffineRatio((-1,1),(1,1),(4,1)) = 2.5
        r = affine_ratio_ppp(Point([-1, 1]), Point([1, 1]), Point([4, 1]))
        assert np.isclose(r.value, 2.5)

    def test_affine_ratio_degenerate(self):
        assert affine_ratio_ppp(Point([0, 0]), Point([0, 0]), Point([1, 1])) is None

    def test_cross_ratio_manual_example(self):
        # GeoGebra: CrossRatio((-1,1),(1,1),(3,1),(4,1)) = 1.2
        r = cross_ratio_pppp(Point([-1, 1]), Point([1, 1]),
                             Point([3, 1]), Point([4, 1]))
        assert np.isclose(r.value, 1.2)

    def test_midpoint_conic_is_center_alias(self):
        assert midpoint_K is center_K
        conic = Conic.from_coeffs(1, 0, 1, 0, 0, -4)  # x²+y²=4, centre (0,0)
        assert np.allclose(midpoint_K(conic).coords, [0, 0])

    def test_conic_six_numbers_geogebra_order(self):
        # GeoGebra Conic(2,3,-1,4,2,-3): 2x²+4xy+3y²+2x-3y-1=0
        got = conic_iiiiii(2, 3, -1, 4, 2, -3)
        expected = Conic.from_coeffs(2, 4, 3, 2, -3, -1)
        assert np.allclose(got.matrix, expected.matrix)

    def test_ray_and_point_from_vector(self):
        r = ray_pv(Point([1, 1]), Vector(([0, 0], [2, 0])))
        assert isinstance(r, Ray)
        assert np.allclose(r.start, [1, 1])
        p = point_pv(Point([1, 1]), Vector(([0, 0], [2, 3])))
        assert np.allclose(p.coords, [3, 4])


# ── Tier B: ClosestPoint / Dilate / Polar ─────────────────────────────

class TestClosestPointDilatePolar:
    def test_closest_point_line(self):
        line = Line(np.array([0.0, 1.0]), 0.0)  # y = 0
        assert np.allclose(closest_point_lp(line, Point([3, 5])).coords, [3, 0])

    def test_closest_point_segment_clamps(self):
        seg = Segment(np.array([0.0, 0.0]), np.array([4.0, 0.0]))
        assert np.allclose(closest_point_sp(seg, Point([1, 9])).coords, [1, 0])
        assert np.allclose(closest_point_sp(seg, Point([99, 9])).coords, [4, 0])

    def test_closest_point_ray_clamps_behind_start(self):
        ray = Ray(np.array([0.0, 0.0]), np.array([1.0, 0.0]))  # +x ray
        assert np.allclose(closest_point_rp(ray, Point([-5, 3])).coords, [0, 0])
        assert np.allclose(closest_point_rp(ray, Point([5, 3])).coords, [5, 0])

    def test_closest_point_circle(self):
        circ = Circle(np.array([0.0, 0.0]), 2.0)
        assert np.allclose(closest_point_cp(circ, Point([10, 0])).coords, [2, 0])

    def test_dilate_point_from_origin(self):
        assert np.allclose(dilate_pi(Point([1, 1]), 2).coords, [2, 2])

    def test_dilate_point_about_center(self):
        assert np.allclose(
            dilate_pip(Point([3, 3]), 2, Point([1, 1])).coords, [5, 5])

    def test_dilate_measure_factor(self):
        assert np.allclose(dilate_pm(Point([1, 1]), Measure(3)).coords, [3, 3])

    def test_dilate_circle_scales_radius(self):
        assert np.isclose(dilate_ci(Circle(np.array([1.0, 0.0]), 2.0), 3).radius, 6)

    def test_dilate_segment_and_polygon(self):
        seg = Segment(np.array([1.0, 0.0]), np.array([2.0, 0.0]))
        d = dilate_sip(seg, 2, Point([0, 0]))
        assert np.allclose(d.endpoints, [[2, 0], [4, 0]])
        poly = Polygon([[0, 0], [1, 0], [0, 1]])
        assert np.allclose(dilate_Pi(poly, 2).vertices, [[0, 0], [2, 0], [0, 2]])

    def test_dilate_line_offset(self):
        line = Line(np.array([0.0, 1.0]), 1.0)  # y = 1
        assert np.isclose(dilate_li(line, 2).offset, 2.0)  # → y = 2

    def test_polar_line_conic_pole(self):
        conic = Conic.from_coeffs(1, 0, 1, 0, 0, -1)  # unit circle
        line = Line(np.array([1.0, 0.0]), 2.0)        # x = 2
        assert np.allclose(polar_lK(line, conic).coords, [0.5, 0])
        assert np.allclose(polar_Kl(conic, line).coords, [0.5, 0])

    def test_polar_reciprocity(self):
        conic = Conic.from_coeffs(1, 0, 1, 0, 0, -1)
        p = Point([0.5, 0.3])
        assert np.allclose(polar_lK(polar_pK(p, conic), conic).coords, p.coords)

    def test_polar_of_central_line_is_none(self):
        conic = Conic.from_coeffs(1, 0, 1, 0, 0, -1)
        line = Line(np.array([0.0, 1.0]), 0.0)  # x-axis through centre
        assert polar_lK(line, conic) is None  # pole at infinity


# ── Tier C: Tangent(Line, Conic) / Tangent(Point|x, Function) ─────────

class TestTangentTierC:
    def _signed_offset(self, line, axis):
        # offset with a canonical sign so ± tangents compare cleanly
        return line.offset if line.normal[axis] > 0 else -line.offset

    def test_tangent_line_conic_circle(self):
        # Unit circle; tangents parallel to the x-axis are y = ±1.
        conic = Conic.from_coeffs(1, 0, 1, 0, 0, -1)
        res = tangent_lK(Line(np.array([0.0, 1.0]), 0.0), conic)
        assert isinstance(res, list) and len(res) == 2
        assert np.allclose(sorted(self._signed_offset(l, 1) for l in res),
                           [-1, 1])

    def test_tangent_line_conic_ellipse(self):
        # x²/4 + y² = 1; tangents parallel to the y-axis are x = ±2.
        ell = Conic.from_coeffs(1, 0, 4, 0, 0, -4)
        res = tangent_Kl(ell, Line(np.array([1.0, 0.0]), 0.0))
        assert np.allclose(sorted(self._signed_offset(l, 0) for l in res),
                           [-2, 2])

    def test_tangent_line_conic_are_really_tangent(self):
        conic = Conic.from_coeffs(1, 0, 1, 0, 0, -1)
        res = tangent_lK(Line(np.array([1.0, -1.0]), 0.0), conic)  # 45°
        assert isinstance(res, list) and len(res) == 2
        for l in res:  # distance from centre (0,0) equals radius 1
            assert np.isclose(abs(l.offset) / np.linalg.norm(l.normal), 1.0)

    def test_tangent_point_function_parabola(self):
        # y = x²; tangent at x = 1 is y = 2x − 1 (point's y is ignored).
        t = tangent_pF(Point([1, 99]), _Fn("y = x^2"))
        assert isinstance(t, Line)
        assert t.contains(np.array([1.0, 1.0]))
        assert t.contains(np.array([2.0, 3.0]))
        assert np.isclose(t.normal[0] / (-t.normal[1]), 2.0)  # slope 2

    def test_tangent_x_value_and_measure_forms(self):
        f = _Fn("y = x^2")
        t_i = tangent_iF(0, f)                      # tangent at vertex, y = 0
        assert np.isclose(t_i.normal[0], 0.0)      # horizontal
        t_p = tangent_pF(Point([1, 0]), f)
        t_m = tangent_mF(Measure(1), f)
        assert np.allclose(t_m.normal, t_p.normal) and np.isclose(t_m.offset,
                                                                  t_p.offset)

    def test_tangent_point_function_outside_domain(self):
        assert tangent_pF(Point([-1, 0]), _Fn("y = sqrt(x)")) is None

    # ── Tangent(Circle, Circle) ──
    @staticmethod
    def _as_list(res):
        if res is None:
            return []
        return res if isinstance(res, list) else [res]

    def _assert_common_tangents(self, c1, c2, expected_count):
        lines = self._as_list(tangent_cc(c1, c2))
        assert len(lines) == expected_count
        for l in lines:  # every line touches both circles
            nn = np.linalg.norm(l.normal)
            d1 = abs(np.dot(l.normal, c1.center) - l.offset) / nn
            d2 = abs(np.dot(l.normal, c2.center) - l.offset) / nn
            assert np.isclose(d1, c1.radius) and np.isclose(d2, c2.radius)

    def test_tangent_circles_separated_gives_four(self):
        self._assert_common_tangents(Circle([0, 0], 1), Circle([6, 0], 2), 4)
        # equal radii → external tangents are parallel, still 4 total
        self._assert_common_tangents(Circle([0, 0], 1), Circle([4, 0], 1), 4)
        # off-axis configuration
        self._assert_common_tangents(Circle([0, 0], 1), Circle([5, 3], 2), 4)

    def test_tangent_circles_externally_tangent_gives_three(self):
        self._assert_common_tangents(Circle([0, 0], 1), Circle([3, 0], 2), 3)

    def test_tangent_circles_overlapping_gives_two(self):
        self._assert_common_tangents(Circle([0, 0], 2), Circle([2.5, 0], 2), 2)

    def test_tangent_circles_internally_tangent_gives_one(self):
        self._assert_common_tangents(Circle([0, 0], 3), Circle([1, 0], 2), 1)

    def test_tangent_circles_nested_or_concentric_gives_none(self):
        assert tangent_cc(Circle([0, 0], 5), Circle([1, 0], 1)) is None  # nested
        assert tangent_cc(Circle([0, 0], 3), Circle([0, 0], 1)) is None  # concentric
