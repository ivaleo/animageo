"""``fill_pattern`` and ``sector_sides`` in the renderer and in TikZ (require manim).

The renderer (SVG/PDF/PNG/EPS/video share its mobjects) and the TikZ exporter
draw the segments and dots of :mod:`animageo.hatch`; the geometry itself is
tested in ``tests/test_hatch.py``.
"""
import math
import re
import textwrap

import pytest

from animageo.animageo import AnimaGeoScene
from animageo import hatch

PT_UNIT = 60


def _scene(code):
    s = AnimaGeoScene()
    s.putCode(textwrap.dedent(code))
    s.applyStyle(export={"size": {"width": 600, "height": 600}})
    s.style.export.update(ptUnit=PT_UNIT, ptUnit_style=PT_UNIT, ptUnit_ggb=PT_UNIT,
                          ptWidth=600, ptHeight=600, ptXZero=150, ptYZero=450)
    s._set_camera_from_export(s.style.export)
    s.updateGeoElements()        # the pixel sizes follow the export layout
    return s


TRIANGLE = """
    A = Point(0, 0)
    B = Point(3, 0)
    C = Point(0, 3)
    p = Polygon(A, B, C)
"""


def _layers(s, name):
    return s.mobject(name).submobjects


def _subpaths(vm):
    return list(vm.gen_subpaths_from_points_2d(vm.points))


class TestRenderer:
    def test_solid_is_the_classic_fill(self):
        s = _scene(TRIANGLE)
        fill, stroke = _layers(s, 'p')[:2]
        assert type(fill).__name__ == 'Polygon' and fill.get_fill_opacity() > 0

    def test_hatch_replaces_the_fill_by_the_segments(self):
        s = _scene(TRIANGLE + "    p.style.fill_pattern = 'hatch'\n")
        fill = _layers(s, 'p')[0]
        expected = hatch.hatch_segments({'polygon': [(0, 0), (3, 0), (0, 3)]},
                                        math.radians(45), 6 / PT_UNIT)
        paths = _subpaths(fill)
        assert len(paths) == len(expected) > 10
        for path, (x0, y0, x1, y1) in zip(paths, expected):
            assert path[0][:2] == pytest.approx((x0, y0))
            assert path[-1][:2] == pytest.approx((x1, y1))
        assert fill.get_fill_opacity() == 0
        assert fill.get_stroke_color().to_hex().lower() == '#000000'     # the stroke colour

    def test_crosshatch_colour_width_and_opacity(self):
        s = _scene("""
            O = Point(1, 1)
            k = Circle(O, 1)
            k.style.fill_pattern = 'crosshatch'
            k.style.hatch_color = '#cc0000'
            k.style.hatch_opacity = 0.5
            k.style.hatch_width_px = 1.5
        """)
        fill = _layers(s, 'k')[0]
        n = len(hatch.pattern_segments({'circle': (1, 1, 1)}, 'crosshatch', math.radians(45), 0.1))
        assert len(_subpaths(fill)) == n
        assert fill.get_stroke_color().to_hex().lower() == '#cc0000'
        assert fill.get_stroke_opacity() == pytest.approx(0.5)
        # 1.5 px against the circle's 1.5 px stroke (presets.line_width.main)
        assert fill.get_stroke_width() == pytest.approx(_layers(s, 'k')[1].get_stroke_width())

    def test_dots_are_one_path_of_discs(self):
        s = _scene("""
            O = Point(0, 0)
            S1 = Point(2, 0)
            S2 = Point(0, 2)
            q = CircleSector(O, S1, S2)
            q.style.fill_pattern = 'dots'
        """)
        fill = _layers(s, 'q')[0]
        dots = hatch.hatch_dots({'sector': (0, 0, 2, 0, math.pi / 2)}, math.radians(45), 0.1)
        assert len(_subpaths(fill)) == len(dots) > 100
        assert fill.get_fill_opacity() == 1 and fill.get_stroke_width() == 0

    def test_none_keeps_the_layer_transparent(self):
        s = _scene(TRIANGLE + "    p.style.fill_pattern = 'none'\n")
        layers = _layers(s, 'p')
        assert layers[0].get_fill_opacity() == 0
        assert layers[1].get_stroke_width() > 0

    def test_switching_patterns_keeps_the_layers(self):
        s = _scene("""
            O = Point(0, 0)
            k = Circle(O, 2)
        """)
        k = s.geo.element('k')
        for pattern in ('hatch', 'dots', 'none', 'crosshatch', 'solid'):
            k.style['fill_pattern'] = pattern
            s.updateGeoElements(['k'])
            assert len(_layers(s, 'k')) == 2, pattern
        assert _layers(s, 'k')[0].get_fill_opacity() > 0

    def test_hatch_reaches_the_svg(self, tmp_path):
        s = _scene(TRIANGLE + "    p.style.fill_pattern = 'hatch'\n")
        svg = (tmp_path / 'h.svg')
        s.exportSVG(str(svg))
        text = svg.read_text()
        n = len(hatch.hatch_segments({'polygon': [(0, 0), (3, 0), (0, 3)]}, math.radians(45), 0.1))
        assert max(d.count('M') for d in re.findall(r' d="([^"]*)"', text)) >= n

    def test_sector_sides(self):
        code = """
            O = Point(0, 0)
            S1 = Point(2, 0)
            S2 = Point(0, 2)
            q = CircleSector(O, S1, S2)
        """
        assert type(_layers(_scene(code), 'q')[1]).__name__ == 'Arc'
        stroke = _layers(_scene(code + "    q.style.sector_sides = True\n"), 'q')[1]
        assert type(stroke).__name__ == 'Sector'
        xs = [round(float(p[0]), 6) for p in stroke.points]
        assert 0.0 in xs and 2.0 in xs                    # through the centre and both ends


class TestTikZ:
    def _tikz(self, code):
        return _scene(code).exportTikZ()

    def test_solid_draws_no_pattern(self):
        tex = self._tikz(TRIANGLE)
        draws = [l for l in tex.splitlines() if l.strip().startswith('\\draw')]
        assert all('cycle' in l or 'circle' in l for l in draws)   # the outline and point markers only

    def test_hatch_segments(self):
        tex = self._tikz(TRIANGLE + "    p.style.fill_pattern = 'hatch'\n")
        line = next(l for l in tex.splitlines() if l.strip().startswith('\\draw') and 'cycle' not in l)
        n = len(hatch.hatch_segments({'polygon': [(0, 0), (3, 0), (0, 3)]}, math.radians(45), 0.1))
        assert line.count(' -- ') == n
        assert 'line width=' in line
        assert '-- cycle' in tex                          # the stroke stays
        assert not any(l.strip().startswith('\\fill[') and 'cycle' in l for l in tex.splitlines())

    def test_dots_one_fill(self):
        tex = self._tikz("""
            O = Point(1, 1)
            k = Circle(O, 1)
            k.style.fill_pattern = 'dots'
            k.style.hatch_color = '#0000ff'
        """)
        n = len(hatch.hatch_dots({'circle': (1, 1, 1)}, math.radians(45), 0.1))
        line = max(tex.splitlines(), key=lambda l: l.count('circle'))
        assert line.count('circle') == n
        assert '0000FF' in tex.upper()

    def test_sector_sides(self):
        code = """
            O = Point(0, 0)
            S1 = Point(2, 0)
            S2 = Point(0, 2)
            q = CircleSector(O, S1, S2)
            q.style.fill_opacity = 0
        """
        assert '-- cycle' not in self._tikz(code)
        assert '(0,0) -- (2,0) arc (0:90:2) -- cycle' in self._tikz(code + "    q.style.sector_sides = True\n")


class TestDefaults:
    def test_builtin_keys(self):
        from animageo.style.config import StyleConfig
        cfg = StyleConfig.load()
        for etype in ('polygon', 'circle', 'circlesector', 'region'):
            for key, value in hatch.HATCH_DEFAULTS.items():
                assert cfg.defaults.get(etype, key) == value, (etype, key)
        assert cfg.defaults.get('circlesector', 'sector_sides') is False
        assert cfg.defaults.get('region', 'stroke_opacity') == 0
