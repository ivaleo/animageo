"""geo/tparam.py: unified point <-> path-parameter math.

The five classic helpers moved here from ggb_parser (which re-exports them
for backward compatibility); the module also owns the function-graph helper
and the tparam_from_point_and_path dispatcher (later tasks).
"""
import numpy as np
import pytest

from animageo.geo.lib_elements import Point, Circle


def test_helpers_importable_from_new_module():
    from animageo.geo import tparam as tp
    for fn in ('get_tparam_from_point_and_circle',
               'get_tparam_from_point_and_line',
               'get_tparam_from_point_and_segment',
               'get_tparam_from_point_and_conic',
               'get_tparam_from_point_and_locus'):
        assert callable(getattr(tp, fn))


def test_parser_reexports_same_objects():
    """Old import path (used by external code and the TZ repro) still works
    and points at the very same functions."""
    from animageo.geo import tparam as tp
    from animageo.parsers import ggb_parser as gp
    assert gp.get_tparam_from_point_and_conic is tp.get_tparam_from_point_and_conic
    assert gp.get_tparam_from_point_and_circle is tp.get_tparam_from_point_and_circle
    assert gp.get_tparam_from_point_and_locus is tp.get_tparam_from_point_and_locus


def test_circle_helper_smoke():
    from animageo.geo.tparam import get_tparam_from_point_and_circle
    c = Circle([0.0, 0.0], 2.0)
    t = get_tparam_from_point_and_circle(Point([0.0, 2.0]), c)
    assert np.isclose(t, np.pi / 2)


class TestLocusSegmentProjection:
    def _locus(self):
        from animageo.geo.lib_elements import LocusCurve
        # Open polyline: 4 points, 3 segments, unit spacing on a square path
        return LocusCurve([[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]])

    def test_midpoint_of_first_segment(self):
        from animageo.geo.tparam import get_tparam_from_point_and_locus
        loc = self._locus()
        # (1, -0.1) projects onto segment 0 at fraction 0.5
        t = get_tparam_from_point_and_locus(Point([1.0, -0.1]), loc)
        assert np.isclose(t, 0.5 / 3)

    def test_roundtrip_with_point_at(self):
        from animageo.geo.tparam import get_tparam_from_point_and_locus
        loc = self._locus()
        t = get_tparam_from_point_and_locus(Point([2.1, 0.5]), loc)
        # foot of projection is (2, 0.5) on segment 1
        assert np.allclose(loc.point_at(t), [2.0, 0.5], atol=1e-9)

    def test_vertex_hits_exact_gridpoint(self):
        from animageo.geo.tparam import get_tparam_from_point_and_locus
        loc = self._locus()
        t = get_tparam_from_point_and_locus(Point([2.0, 2.0]), loc)
        assert np.isclose(t, 2 / 3)

    def test_clamps_beyond_ends(self):
        from animageo.geo.tparam import get_tparam_from_point_and_locus
        loc = self._locus()
        assert np.isclose(
            get_tparam_from_point_and_locus(Point([-5.0, 0.0]), loc), 0.0)
        assert np.isclose(
            get_tparam_from_point_and_locus(Point([-5.0, 2.0]), loc), 1.0)

    def test_degenerate_empty_and_single(self):
        from animageo.geo.lib_elements import LocusCurve
        from animageo.geo.tparam import get_tparam_from_point_and_locus
        assert get_tparam_from_point_and_locus(
            Point([0, 0]), LocusCurve(np.empty((0, 2)))) is None
        assert get_tparam_from_point_and_locus(
            Point([5, 5]), LocusCurve([[1.0, 1.0]])) == 0.0


class TestFunctionHelperAndDispatcher:
    def test_function_tparam_is_x(self):
        from animageo.geo.lib_function import Function
        from animageo.geo.tparam import get_tparam_from_point_and_function
        f = Function("y = x^2")
        assert get_tparam_from_point_and_function(Point([1.5, 2.25]), f) == 1.5
        # off-graph point projects along y: x is kept
        assert get_tparam_from_point_and_function(Point([1.5, 99.0]), f) == 1.5

    def test_dispatcher_all_types(self):
        from animageo.geo.lib_elements import (
            Circle, Line, Ray, Segment, LocusCurve)
        from animageo.geo.lib_conic import Conic
        from animageo.geo.lib_function import Function
        from animageo.geo.tparam import tparam_from_point_and_path

        # circle: angle
        t = tparam_from_point_and_path(
            Point([0.0, 2.0]), Circle([0.0, 0.0], 2.0))
        assert np.isclose(t, np.pi / 2)

        # segment: 0..1 (Segment subclasses Line - must dispatch as segment).
        # NB: Segment(p1, p2) requires numpy arrays (does p1 - p2 internally).
        seg = Segment(np.array([0.0, 0.0]), np.array([4.0, 0.0]))
        assert np.isclose(tparam_from_point_and_path(Point([1.0, 0.0]), seg), 0.25)

        # ellipse conic: x^2/9 + y^2/4 = 1 -> t of (0, 2) is pi/2
        ell = Conic.from_coeffs(a=1/9, c=1/4, f=-1.0)
        assert np.isclose(
            tparam_from_point_and_path(Point([0.0, 2.0]), ell), np.pi / 2)

        # hyperbola conic: x^2/4 - y^2/9 = 1 -> tuple (branch, t)
        hyp = Conic.from_coeffs(a=1/4, c=-1/9, f=-1.0)
        bt = tparam_from_point_and_path(Point([-2.0, 0.0]), hyp)
        assert isinstance(bt, tuple) and bt[0] == -1.0 and np.isclose(bt[1], 0.0)

        # locus
        loc = LocusCurve([[0.0, 0.0], [2.0, 0.0], [2.0, 2.0]])
        assert np.isclose(
            tparam_from_point_and_path(Point([2.0, 1.0]), loc), 1.5 / 2)

        # function
        f = Function("y = x^2")
        assert tparam_from_point_and_path(Point([1.5, 2.25]), f) == 1.5

        # unsupported path type -> None
        assert tparam_from_point_and_path(Point([0, 0]), object()) is None
