"""Tests for geometric element classes (lib_elements.py).

Covers: Point, Line, Segment, Ray, Angle, Polygon, Circle, Arc, CircleSector, Vector.
Focus: construction, properties, style initialization, edge cases.
"""
import numpy as np
import pytest

from animageo.geo.lib_elements import (
    Point, Line, Segment, Ray, Angle, Polygon, Circle, Arc, CircleSector, Vector,
    Element, interpolate, a_to_cpx, cpx_to_a, vector_perp_rot,
)


# ── Point ──────────────────────────────────────────────────────────────

class TestPoint:
    def test_create(self):
        p = Point([3, 4])
        assert np.allclose(p.coords, [3, 4])

    def test_style_initialized(self):
        p = Point([0, 0])
        assert isinstance(p.style, dict)
        assert 'label_visible' in p.style

    def test_translate(self):
        p = Point([1, 2])
        p.translate(np.array([3, 4]))
        assert np.allclose(p.coords, [4, 6])

    def test_scale(self):
        p = Point([2, 3])
        p.scale(2)
        assert np.allclose(p.coords, [4, 6])

    def test_equivalent(self):
        p1 = Point([1, 2])
        p2 = Point([1, 2])
        p3 = Point([1, 3])
        assert p1.equivalent(p2)
        assert not p1.equivalent(p3)

    def test_repr(self):
        p = Point([1.5, 2.5])
        assert 'Point' in repr(p)


# ── Line ───────────────────────────────────────────────────────────────

class TestLine:
    def test_create_normalized(self):
        line = Line([3.0, 4.0], 10.0)
        assert np.isclose(np.linalg.norm(line.normal), 1)
        assert np.isclose(np.dot(line.normal, [3, 4]) / np.linalg.norm([3, 4]), 1)

    def test_style_initialized(self):
        line = Line([1.0, 0.0], 0.0)
        assert isinstance(line.style, dict)
        assert 'z_index' in line.style

    def test_perpendicular_vector(self):
        line = Line([1.0, 0.0], 0.0)
        assert np.isclose(np.dot(line.normal, line.direction), 0)

    def test_contains(self):
        line = Line([0.0, 1.0], 3.0)  # y = 3
        assert line.contains(np.array([5, 3]))
        assert not line.contains(np.array([5, 4]))

    def test_equivalent(self):
        l1 = Line([0.0, 1.0], 3.0)
        l2 = Line([0.0, 2.0], 6.0)  # same line, different representation
        l3 = Line([0.0, -1.0], -3.0)  # same line, opposite normal
        assert l1.equivalent(l2)
        assert l1.equivalent(l3)

    def test_get_endpoints(self):
        line = Line([0.0, 1.0], 0.0)  # y = 0, horizontal line
        corners = [(-10, -10), (10, 10)]
        endpoints = line.get_endpoints(corners)
        assert endpoints is not None
        assert len(endpoints) == 2


# ── Segment ────────────────────────────────────────────────────────────

class TestSegment:
    def test_create(self):
        s = Segment(np.array([0.0, 0.0]), np.array([3.0, 4.0]))
        assert np.isclose(s.length, 5)
        assert len(s.endpoints) == 2

    def test_style_initialized(self):
        s = Segment(np.array([0.0, 0.0]), np.array([1.0, 0.0]))
        assert isinstance(s.style, dict)

    def test_contains(self):
        s = Segment(np.array([0.0, 0.0]), np.array([4.0, 0.0]))
        assert s.contains(np.array([2, 0]))
        assert not s.contains(np.array([5, 0]))

    def test_get_endpoints(self):
        s = Segment(np.array([1.0, 2.0]), np.array([3.0, 4.0]))
        endpoints = s.get_endpoints(None)
        assert np.allclose(endpoints, [[1, 2], [3, 4]])


# ── Ray ────────────────────────────────────────────────────────────────

class TestRay:
    def test_create(self):
        r = Ray(np.array([0, 0]), np.array([1, 0]))
        assert np.allclose(r.start, [0, 0])

    def test_contains(self):
        r = Ray(np.array([0, 0]), np.array([1, 0]))
        assert r.contains(np.array([5, 0]))
        assert not r.contains(np.array([-5, 0]))
        assert r.contains(np.array([0, 0]))  # start point


# ── Angle ──────────────────────────────────────────────────────────────

class TestAngle:
    def test_right_angle(self):
        a = Angle(np.array([0, 0]), np.array([1, 0]), np.array([0, 1]))
        assert np.isclose(a.size, np.pi / 2)

    def test_style_initialized(self):
        a = Angle(np.array([0, 0]), np.array([1, 0]), np.array([0, 1]))
        assert isinstance(a.style, dict)
        assert 'tick_count' in a.style
        assert 'arc_shift_px' in a.style

    def test_full_angle(self):
        a = Angle(np.array([0, 0]), np.array([1, 0]), np.array([-1, 0]))
        assert np.isclose(a.size, np.pi)

    def test_equivalent(self):
        from animageo.geo.lib_vars import AngleSize
        a1 = Angle(np.array([0, 0]), np.array([1, 0]), np.array([0, 1]))
        a2 = Angle(np.array([0, 0]), np.array([2, 0]), np.array([0, 2]))
        a3 = Angle(np.array([0, 0]), np.array([1, 0]), np.array([-1, 0]))
        assert a1.equivalent(a2)
        assert not a1.equivalent(a3)
        assert a1.equivalent(AngleSize(np.pi / 2))
        assert not a1.equivalent(AngleSize(np.pi))


class TestElementValueAccessor:
    """``Element.value()`` for wrapped Measure/AngleSize/Boolean/Angle/Segment.

    Regression: previously accessed ``.x`` on Measure/AngleSize — which is
    not a real attribute, so NameError leaked out (circular-import kept
    Measure out of lib_elements' globals) and silently produced
    AttributeError for Measure. Both are fixed: imports are local now,
    and the value attribute is named consistently."""

    def test_measure(self):
        from animageo.geo.lib_elements import Element
        from animageo.geo.lib_vars import Measure
        e = Element('m', Measure(3.14, 1))
        assert e.value() == pytest.approx(3.14)

    def test_angle_size(self):
        from animageo.geo.lib_elements import Element
        from animageo.geo.lib_vars import AngleSize
        e = Element('a', AngleSize(np.pi / 4))
        assert e.value() == pytest.approx(np.pi / 4)

    def test_boolean(self):
        from animageo.geo.lib_elements import Element
        from animageo.geo.lib_vars import Boolean
        e = Element('b', Boolean(True))
        assert e.value() == 1.0

    def test_angle_element(self):
        from animageo.geo.lib_elements import Element
        e = Element('A', Angle(np.array([0, 0]), np.array([1, 0]), np.array([0, 1])))
        assert e.value() == pytest.approx(np.pi / 2)

    def test_unbuilt_data_raises_clear_error(self):
        from animageo.geo.lib_elements import Element
        e = Element('X', None)
        with pytest.raises(AttributeError, match="unbuilt"):
            _ = e.length


# ── Polygon ────────────────────────────────────────────────────────────

class TestPolygon:
    def test_create(self):
        poly = Polygon([[0, 0], [1, 0], [0, 1]])
        assert len(poly.vertices) == 3

    def test_style_initialized(self):
        poly = Polygon([[0, 0], [1, 0], [0, 1]])
        assert isinstance(poly.style, dict)


# ── Circle ─────────────────────────────────────────────────────────────

class TestCircle:
    def test_create(self):
        c = Circle([0, 0], 5)
        assert c.radius == 5
        assert np.isclose(c.radius_squared, 25)

    def test_nonpositive_radius_is_not_asserted(self):
        # Since 1.8.0a2 the circle commands return None for r <= 0
        # (tests/test_classic_fixes_l1.py); the class itself does not assert.
        assert Circle([0, 0], 0).radius == 0
        assert Circle([0, 0], -1).radius == -1

    def test_style_initialized(self):
        c = Circle([0, 0], 1)
        assert isinstance(c.style, dict)

    def test_equivalent(self):
        c1 = Circle([0, 0], 5)
        c2 = Circle([0, 0], 5)
        c3 = Circle([1, 0], 5)
        assert c1.equivalent(c2)
        assert not c1.equivalent(c3)


# ── Arc ────────────────────────────────────────────────────────────────

class TestArc:
    def test_create(self):
        a = Arc([0, 0], 5, [0, np.pi / 2])
        assert a.radius == 5

    def test_style_initialized(self):
        a = Arc([0, 0], 5, [0, np.pi])
        assert isinstance(a.style, dict)

    def test_contains_point_on_wrapped_arc(self):
        a = Arc([0, 0], 5, [3 * np.pi / 4, -np.pi / 4])
        assert a.contains(np.array([-5, 0]))
        assert not a.contains(np.array([0, 5]))


# ── CircleSector ───────────────────────────────────────────────────────

class TestCircleSector:
    def test_create(self):
        cs = CircleSector([0, 0], 5, [0, np.pi / 2])
        assert cs.radius == 5

    def test_style_initialized(self):
        cs = CircleSector([0, 0], 5, [0, np.pi])
        assert isinstance(cs.style, dict)


# ── Vector ─────────────────────────────────────────────────────────────

class TestVector:
    def test_create(self):
        v = Vector([[0, 0], [3, 4]])
        assert np.allclose(v.direction, [3, 4])

    def test_style_initialized(self):
        v = Vector([[0, 0], [1, 0]])
        assert isinstance(v.style, dict)


# ── Element wrapper ────────────────────────────────────────────────────

class TestElement:
    def test_with_data(self):
        e = Element('A', Point([1, 2]))
        assert e.name == 'A'
        assert isinstance(e.style, dict)
        assert e.visible

    def test_without_data(self):
        """Element with data=None must still have style attribute."""
        e = Element('X', None)
        assert hasattr(e, 'style')
        assert isinstance(e.style, dict)

    def test_with_update_style_false(self):
        """Element with update_style=False must still have style attribute."""
        e = Element('X', Point([0, 0]), update_style=False)
        assert hasattr(e, 'style')
        assert isinstance(e.style, dict)

    def test_is_drawable(self):
        assert Element('A', Point([0, 0])).is_drawable()
        assert Element('s', Segment(np.array([0, 0]), np.array([1, 0]))).is_drawable()
        assert not Element('x', None).is_drawable()


# ── Utility functions ──────────────────────────────────────────────────

class TestUtils:
    def test_interpolate(self):
        assert np.isclose(interpolate(0, 10, 0.5), 5)

    def test_a_to_cpx_roundtrip(self):
        a = np.array([3.0, 4.0])
        assert np.allclose(cpx_to_a(a_to_cpx(a)), a)

    def test_vector_perp_rot(self):
        v = np.array([1.0, 0.0])
        perp = vector_perp_rot(v)
        assert np.isclose(np.dot(v, perp), 0)
