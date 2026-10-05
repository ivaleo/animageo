"""Classic geometry fixes of L2 (§15 of the kernel spec): 1.8.1a1 — a circle
through collinear points and an angle bisector with a degenerate side are
undefined without an error; 1.8.1 — tangents from an inside point, a scaled
vector, a turned vector, the boundary of a sector, bisectors of parallel
lines, a line across a sector, signature aliases and the locus defaults."""
import logging
import warnings

import numpy as np
import pytest

from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command, angular_bisector_ppp, circle_ppp
from animageo.geo.lib_elements import Element, Point


def P(x, y):
    return Point(np.array([x, y], dtype=float))


def construction(points, *commands):
    c = Construction(seed=0)
    for name, xy in points.items():
        c.add(Element(name, Point(xy)))
    for cmd in commands:
        c.add_and_build(cmd)
    return c


class TestCirclePPP:
    @pytest.mark.parametrize('pts', [
        ((0, 0), (1, 1), (3, 3)),           # collinear
        ((0, 0), (0, 0), (2, 1)),           # two coincide
        ((1, 2), (1, 2), (1, 2)),           # all coincide
    ])
    def test_degenerate_is_none(self, pts):
        assert circle_ppp(*(P(*p) for p in pts)) is None

    def test_general_circle(self):
        c = circle_ppp(P(0, 0), P(4, 0), P(0, 3))
        assert tuple(c.center) == pytest.approx((2.0, 1.5)) and c.radius == pytest.approx(2.5)

    def test_no_error_in_the_log(self, caplog):
        with caplog.at_level(logging.WARNING):
            c = construction({'A': (0, 0), 'B': (1, 1), 'C': (3, 3)}, Command('Circle', ['A', 'B', 'C'], ['k']))
        assert c.element('k').data is None
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


class TestAngularBisectorPPP:
    @pytest.mark.parametrize('pts', [
        ((0, 0), (0, 0), (2, 1)),           # first side has zero length
        ((3, 1), (2, 5), (2, 5)),           # second side has zero length
        ((1, 1), (1, 1 + 1e-14), (4, 2)),   # zero up to rounding
    ])
    def test_degenerate_side_is_none(self, pts):
        with warnings.catch_warnings():
            warnings.simplefilter('error')      # no division by zero on the way
            assert angular_bisector_ppp(*(P(*p) for p in pts)) is None

    def test_general_bisector(self):
        line = angular_bisector_ppp(P(4, 0), P(0, 0), P(0, 4))
        n = line.normal / np.linalg.norm(line.normal)
        assert abs(float(np.dot(n, [1.0, 1.0]))) == pytest.approx(0.0, abs=1e-12)
        assert float(line.offset) == pytest.approx(0.0, abs=1e-12)


# ── 1.8.1: the classic fixes of §15 for registry 1.4 ─────────────────────

from animageo.geo.lib_commands import (  # noqa: E402
    angular_bisector_ll, intersect_Sl, rotate_vAp, signature_alias, tangent_pc, tangent_pci, vector_vi,
)
from animageo.geo.lib_conic import Conic  # noqa: E402
from animageo.geo.lib_elements import Circle, CircleSector, Line, LocusCurve, Ray, Segment, Vector  # noqa: E402
from animageo.geo.lib_vars import AngleSize  # noqa: E402


def S(a, b):
    return Segment(np.array(a, dtype=float), np.array(b, dtype=float))


def line_through(a, b):
    return S(a, b)        # a Segment is a Line with a normal and an offset


def carrier(seg):
    return Line(seg.normal, seg.offset)


class TestTangentFromInside:
    circle = Circle(np.array([0.0, 0.0]), 2.0)

    def test_inside_is_none(self):
        assert tangent_pc(P(0.5, 0.3), self.circle) is None
        assert tangent_pci(P(0.5, 0.3), self.circle, 1) is None
        assert tangent_pc(P(0, 0), self.circle) is None             # the centre

    def test_outside_two_tangents(self):
        lines = tangent_pc(P(4, 0), self.circle)
        assert len(lines) == 2
        for line in lines:
            n = line.normal / np.linalg.norm(line.normal)
            assert abs(float(line.offset) / np.linalg.norm(line.normal)) == pytest.approx(2.0)

    def test_on_the_circle_the_tangent_at_the_point(self):
        line = tangent_pc(P(0, 2), self.circle)
        assert line.contains(np.array([5.0, 2.0])) and line.contains(np.array([0.0, 2.0]))

    def test_construction_leaves_it_undefined(self, caplog):
        c = construction({'O': (0, 0), 'A': (2, 0), 'Q': (0.5, 0.5)},
                         Command('Circle', ['O', 'A'], ['k']), Command('Tangent', ['Q', 'k'], ['t1', 't2']))
        assert c.element('t1').data is None and c.element('t2').data is None


class TestVectorScaled:
    def test_from_the_start(self):
        v = vector_vi(Vector([[1.0, 1.0], [4.0, 5.0]]), 10)
        assert v.endpoints[0].tolist() == [1.0, 1.0]
        assert v.endpoints[1] == pytest.approx([7.0, 9.0])


class TestRotateVector:
    def test_about_the_centre(self):
        v = rotate_vAp(Vector([[2.0, 0.0], [3.0, 0.0]]), AngleSize(np.pi / 2), P(1, 0))
        assert v.endpoints[0] == pytest.approx([1.0, 1.0])
        assert v.endpoints[1] == pytest.approx([1.0, 2.0])

    def test_about_the_start_keeps_the_start(self):
        v = rotate_vAp(Vector([[2.0, 0.0], [3.0, 0.0]]), AngleSize(np.pi), P(2, 0))
        assert v.endpoints[0] == pytest.approx([2.0, 0.0]) and v.endpoints[1] == pytest.approx([1.0, 0.0])


class TestSectorContains:
    sector = CircleSector(np.array([0.0, 0.0]), 4.0, [0.0, np.pi / 2])

    @pytest.mark.parametrize('x, inside', [
        ((4, 0), True), ((0, 4), True), ((4 / np.sqrt(2), 4 / np.sqrt(2)), True),    # the arc
        ((2, 0), True), ((0, 3), True), ((0, 0), True),                             # the radii, the centre
        ((-4, 0), False), ((0, -4), False), ((5, 0), False), ((1, 1), False),       # elsewhere
    ])
    def test_boundary(self, x, inside):
        assert self.sector.contains(np.array(x, dtype=float)) is inside


class TestBisectorsOfParallelLines:
    def test_parallel_is_none(self):
        assert angular_bisector_ll(carrier(S((0, 0), (4, 0))), carrier(S((0, 2), (4, 2)))) is None
        assert angular_bisector_ll(carrier(S((0, 0), (4, 0))), carrier(S((1, 0), (3, 0)))) is None

    def test_crossing_lines_two_bisectors(self):
        lines = angular_bisector_ll(carrier(S((0, 0), (4, 0))), carrier(S((0, 0), (0, 4))))
        assert len(lines) == 2


class TestLineAndSector:
    sector = CircleSector(np.array([0.0, 0.0]), 4.0, [0.0, np.pi / 2])

    def test_the_radii_too(self):
        points = intersect_Sl(self.sector, carrier(S((-5, 2), (5, 2))))       # y = 2
        coords = sorted(tuple(np.round(p.coords, 9)) for p in points)
        assert coords == [(0.0, 2.0), (round(np.sqrt(12), 9), 2.0)]

    def test_through_the_centre_once(self):
        points = intersect_Sl(self.sector, carrier(S((-1, -1), (1, 1))))      # y = x
        coords = sorted(tuple(np.round(p.coords, 9)) for p in points)
        r = round(4 / np.sqrt(2), 9)
        assert coords == [(0.0, 0.0), (r, r)]

    def test_misses(self):
        assert intersect_Sl(self.sector, carrier(S((-5, -2), (5, -2)))) is None


class TestSignatureAliases:
    def test_slope_of_a_segment(self):
        f = signature_alias('Slope', [S((0, 0), (2, 1))])
        assert f(S((0, 0), (2, 1))).value == pytest.approx(0.5)

    def test_tangents_to_a_circle_parallel_to_a_line(self):
        circle, line = Circle(np.array([0.0, 0.0]), 2.0), carrier(S((0, 5), (1, 5)))
        lines = signature_alias('Tangent', [line, circle])(line, circle)
        assert sorted(abs(float(l.offset)) / np.linalg.norm(l.normal) for l in lines) == pytest.approx([2.0, 2.0])

    def test_a_circle_by_its_equation_in_a_circle_command(self):
        k = Conic.from_coeffs(1, 0, 1, 0, 0, -4)          # x² + y² = 4
        image = signature_alias('Mirror', [P(3, 0), k])(P(3, 0), k)
        assert image.coords == pytest.approx([4 / 3, 0.0])

    def test_the_mirror_axis_only(self):
        assert signature_alias('Mirror', [S((0, 0), (1, 0)), P(0, 0)]) is None    # a segment object stays a segment
        assert signature_alias('Distance', [P(0, 0), S((0, 0), (1, 0))]) is None  # exact, no alias needed

    def test_slope_of_a_segment_in_a_construction(self):
        c = construction({'A': (0, 0), 'B': (2, 1)}, Command('Segment', ['A', 'B'], ['s']),
                         Command('Slope', ['s'], ['m']))
        assert c.var('m').data.value == pytest.approx(0.5)


class TestLocusDefaults:
    def test_builtin_has_locuscurve(self):
        from animageo.style.config import StyleConfig
        cfg = StyleConfig.load()
        assert cfg.defaults.get('locuscurve', 'stroke_width_px') == cfg.defaults.get('function', 'stroke_width_px')
        assert cfg.defaults.get('locuscurve', 'stroke') is not None
