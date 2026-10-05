"""Geometry of ``fill_pattern`` (kernel spec §9.1): :mod:`animageo.hatch`.

Pure functions, no manim: the renderer and the TikZ exporter draw exactly
these segments and dots (``tests/test_hatch_render.py``).
"""
import math

import pytest

from animageo.hatch import (
    HATCH_DEFAULTS, MAX_LINES, hatch_dots, hatch_segments, hatch_spec, pattern_segments,
)

SQUARE = {'polygon': [(0, 0), (4, 0), (4, 4), (0, 4)]}


def _length(segs):
    return sum(math.hypot(x1 - x0, y1 - y0) for x0, y0, x1, y1 in segs)


def _area_by_cavalieri(region, angle, spacing=0.002):
    """The hatched length times the spacing tends to the area."""
    return _length(hatch_segments(region, angle, spacing, phase=spacing / 2)) * spacing


class TestLineFamily:
    def test_horizontal_lines_across_a_square(self):
        segs = hatch_segments(SQUARE, 0.0, 1.0, phase=0.5)
        assert [(round(x0, 9), round(y0, 9), round(x1, 9), round(y1, 9)) for x0, y0, x1, y1 in segs] == [
            (0, 0.5, 4, 0.5), (0, 1.5, 4, 1.5), (0, 2.5, 4, 2.5), (0, 3.5, 4, 3.5)]

    def test_vertical_lines_across_a_square(self):
        segs = hatch_segments(SQUARE, math.pi / 2, 1.0, phase=0.5)
        xs = sorted(round(x0, 9) for x0, _, _, _ in segs)
        assert xs == [0.5, 1.5, 2.5, 3.5]
        assert all(abs(abs(y1 - y0) - 4) < 1e-9 for _, y0, _, y1 in segs)

    def test_the_lines_are_anchored_in_the_plane(self):
        # moving the region by a whole spacing along the normal moves the
        # same lines with it: the hatching stays put, like in GeoGebra
        angle, spacing = math.radians(30), 0.7
        n = (-math.sin(angle), math.cos(angle))
        dx, dy = 3 * spacing * n[0], 3 * spacing * n[1]
        moved = {'polygon': [(x + dx, y + dy) for x, y in SQUARE['polygon']]}
        a = hatch_segments(SQUARE, angle, spacing)
        b = hatch_segments(moved, angle, spacing)
        assert len(a) == len(b)
        for s, t in zip(a, b):
            assert t == pytest.approx((s[0] + dx, s[1] + dy, s[2] + dx, s[3] + dy), abs=1e-9)

    def test_a_vertex_on_a_line_counts_once(self):
        diamond = {'polygon': [(0, -1), (1, 0), (0, 1), (-1, 0)]}
        segs = hatch_segments(diamond, 0.0, 1.0)          # the lines y = −1, 0, 1 hit vertices
        assert all(x0 <= x1 for x0, _, x1, _ in segs)
        middle = [s for s in segs if abs(s[1]) < 1e-12]
        assert middle == [pytest.approx((-1, 0, 1, 0))]

    def test_even_odd_for_a_self_crossing_ring(self):
        bowtie = {'polygon': [(0, 0), (2, 2), (2, 0), (0, 2)]}
        segs = hatch_segments(bowtie, 0.0, 1.0, phase=0.5)
        assert len(segs) == 4                             # two lines, each through both lobes
        assert _length(segs) == pytest.approx(2.0)

    @pytest.mark.parametrize('angle_deg', [0, 17, 45, 90, 133])
    def test_polygon_area(self, angle_deg):
        triangle = {'polygon': [(0, 0), (3, 0), (1, 2)]}
        assert _area_by_cavalieri(triangle, math.radians(angle_deg)) == pytest.approx(3.0, rel=2e-3)

    @pytest.mark.parametrize('angle_deg', [0, 45, 100])
    def test_disc_area_and_endpoints_on_the_circle(self, angle_deg):
        disc = {'circle': (1.0, -2.0, 1.5)}
        assert _area_by_cavalieri(disc, math.radians(angle_deg)) == pytest.approx(math.pi * 2.25, rel=2e-3)
        for x0, y0, x1, y1 in hatch_segments(disc, math.radians(angle_deg), 0.3):
            assert math.hypot(x0 - 1, y0 + 2) == pytest.approx(1.5)
            assert math.hypot(x1 - 1, y1 + 2) == pytest.approx(1.5)

    @pytest.mark.parametrize('a0, a1', [
        (0.0, math.pi / 2),                   # quarter
        (0.3, 0.3 + math.pi),                 # half
        (1.0, 1.0 + 1.5 * math.pi),           # reflex
        (-2.0, -2.0 + 2 * math.pi),           # whole disc
    ])
    @pytest.mark.parametrize('angle_deg', [0, 60])
    def test_sector_area(self, a0, a1, angle_deg):
        r = 2.0
        sector = {'sector': (0.5, 0.5, r, a0, a1)}
        assert _area_by_cavalieri(sector, math.radians(angle_deg)) == pytest.approx(
            r * r * (a1 - a0) / 2, rel=3e-3)

    def test_reflex_sector_splits_a_line_around_the_hole(self):
        # three quarters without the first quadrant: y = 0.5 crosses the
        # disc left of the centre only
        sector = {'sector': (0.0, 0.0, 2.0, math.pi / 2, 2 * math.pi)}
        segs = hatch_segments(sector, 0.0, 1.0, phase=0.5)
        upper = [s for s in segs if s[1] > 0]
        assert len(upper) == 2                            # y = 0.5 and y = 1.5
        assert all(max(s[0], s[2]) == pytest.approx(0.0) for s in upper)
        lower = [s for s in segs if s[1] < 0]
        assert all(abs(s[2] - s[0]) == pytest.approx(2 * math.sqrt(4 - s[1] ** 2)) for s in lower)

    def test_an_empty_sector_has_no_lines(self):
        assert hatch_segments({'sector': (0, 0, 1, 1.0, 1.0)}, 0.0, 0.1) == []

    def test_crosshatch_is_two_families(self):
        a = hatch_segments(SQUARE, 0.3, 0.5)
        b = hatch_segments(SQUARE, 0.3 + math.pi / 2, 0.5)
        assert pattern_segments(SQUARE, 'crosshatch', 0.3, 0.5) == a + b
        assert pattern_segments(SQUARE, 'hatch', 0.3, 0.5) == a
        assert pattern_segments(SQUARE, 'dots', 0.3, 0.5) == []

    @pytest.mark.parametrize('spacing', [0.0, -1.0, float('nan'), float('inf')])
    def test_a_bad_spacing_is_an_error(self, spacing):
        with pytest.raises(ValueError):
            hatch_segments(SQUARE, 0.0, spacing)

    def test_too_many_lines_is_an_error(self):
        with pytest.raises(ValueError, match=str(MAX_LINES)):
            hatch_segments(SQUARE, 0.0, 4.0 / (MAX_LINES + 10))


class TestDots:
    def test_grid_inside_a_square(self):
        dots = hatch_dots(SQUARE, 0.0, 1.0, phase=0.5)
        assert sorted((round(x, 9), round(y, 9)) for x, y in dots) == [
            (x + 0.5, y + 0.5) for x in range(4) for y in range(4)]

    def test_dots_lie_inside_the_disc(self):
        dots = hatch_dots({'circle': (0, 0, 1)}, 0.4, 0.1)
        assert all(math.hypot(x, y) <= 1 + 1e-12 for x, y in dots)
        assert len(dots) * 0.01 == pytest.approx(math.pi, rel=0.03)


class TestSpec:
    def _resolve(self, style):
        return lambda elem, key, default=None: style.get(key, default)

    def test_defaults(self):
        spec = hatch_spec(self._resolve({}), None, 2.0)
        assert spec['angle'] == pytest.approx(math.radians(HATCH_DEFAULTS['hatch_angle_deg']))
        assert spec['spacing_mu'] == pytest.approx(HATCH_DEFAULTS['hatch_spacing_px'] / 2.0)
        assert spec['dot_radius_mu'] == pytest.approx(HATCH_DEFAULTS['hatch_width_px'] / 2.0)
        assert spec['color'] is None                      # 'stroke': the stroke colour
        assert spec['opacity'] == 1.0

    def test_values_and_clamps(self):
        spec = hatch_spec(self._resolve({
            'hatch_angle_deg': 90, 'hatch_spacing_px': 12, 'hatch_width_px': -1,
            'hatch_color': '#ff0000', 'hatch_opacity': 7}), None, 4.0)
        assert spec['angle'] == pytest.approx(math.pi / 2)
        assert spec['spacing_mu'] == pytest.approx(3.0)
        assert spec['width_px'] == 0.0
        assert spec['color'] == '#ff0000'
        assert spec['opacity'] == 1.0

    @pytest.mark.parametrize('bad', [0, -3, 'wide', None])
    def test_a_bad_spacing_falls_back_to_the_default(self, bad):
        spec = hatch_spec(self._resolve({'hatch_spacing_px': bad}), None, 1.0)
        assert spec['spacing_px'] == HATCH_DEFAULTS['hatch_spacing_px']
