"""Kinds of marks in the TikZ and the JSXGraph export: the same geometry as
the renderer (``animageo/mark_shapes.py``), explicit TikZ paths, JSXGraph
natives where it has them and static decorations elsewhere."""
import json
import math
import re
import shutil
import subprocess
import textwrap

import pytest

pytest.importorskip('manim')

from animageo.animageo import AnimaGeoScene  # noqa: E402

PT = 80.0


def framed(code, style=None):
    s = AnimaGeoScene()
    s.putCode(textwrap.dedent(code))
    s.applyStyle(style=style, export={'size': {'width': 480, 'height': 400}})
    exp = s.style.export
    exp.update(ptUnit=PT, ptUnit_style=PT, ptUnit_ggb=PT, ptWidth=480, ptHeight=400, ptXZero=120, ptYZero=340)
    s._set_camera_from_export(exp)
    return s


def angle_code(c=(1, 2), extra=''):
    return f'A = Point(0, 0)\nB = Point(3, 0)\nC = Point({c[0]}, {c[1]})\na = Angle(B, A, C)\n' + extra


SEG = 's = Segment(B, C)\n'
DEFAULTS = """
a.style.arc_style = 'solid'
a.style.arc_tick_count = 0
a.style.arrow_head = 'none'
s.style.arrow_head = 'none'
s.style.parallel_count = 0
A.style.point_fill = 'solid'
"""


def tikz(code, **kw):
    return framed(code).exportTikZ(**kw)


def spec(code):
    return json.loads(framed(code).exportJSXGraph(output='spec'))


def coverage(sp):
    return {c['name']: (c['kind'], c['detail']) for c in sp['coverage']}


def element(sp, name):
    (el,) = [e for e in sp['elements'] if e.get('name') == name]
    return el


class TestTikZ:
    def test_default_values_export_as_before(self):
        assert tikz(angle_code() + SEG) == tikz(angle_code() + SEG + DEFAULTS)

    def test_wave_samples(self):
        tex = tikz(angle_code(extra="a.style.arc_style = 'wave'\na.style.tick_count = 2\n"))
        plots = re.findall(r'plot coordinates \{(.*?)\};', tex)
        assert len(plots) == 2
        periods = max(1, round((17 + 3.5) * math.atan2(2, 1) / 6))
        assert plots[0].count('(') == 16 * periods + 1

    def test_dashed_arc_is_fitted(self):
        tex = tikz(angle_code(extra="a.style.arc_style = 'dashed'\n"))
        (line,) = [ln for ln in tex.splitlines() if 'arc (' in ln and 'dash pattern' in ln]
        on = float(re.search(r'on ([\d.]+)pt', line).group(1))
        assert on == pytest.approx(2 * 0.75, rel=0.25)                # 2 px at 96 dpi, fitted

    def test_ticks_and_heads(self):
        tex = tikz(angle_code(extra="a.style.arc_tick_count = 3\na.style.arrow_head = 'both'\n"))
        assert len([ln for ln in tex.splitlines() if ln.strip().startswith('\\draw') and 'line cap=butt' in ln
                    and 'arc (' not in ln]) == 3
        assert len([ln for ln in tex.splitlines() if ln.strip().startswith('\\fill') and '-- cycle' in ln]) == 2

    def test_a_decorated_right_angle_is_arcs(self):
        square = tikz(angle_code((0, 2)))
        arcs = tikz(angle_code((0, 2), 'a.style.arc_tick_count = 1\n'))
        forced = tikz(angle_code((0, 2), 'a.style.arc_tick_count = 1\na.style.right_angle_marker = True\n'))
        assert 'arc (' not in square and 'arc (' in arcs and 'arc (' not in forced

    def test_hatch(self):
        tex = tikz(angle_code(extra="a.style.fill_pattern = 'hatch'\n"))
        assert any(ln.count(' -- ') >= 3 and 'arc' not in ln for ln in tex.splitlines())

    def test_label_clears_the_decoration(self):
        def node(extra):
            tex = tikz(angle_code(extra='a.style.label_visible = True\n' + extra))
            x, y = re.search(r'\\node\[[^\]]*\] at \(([-\d.]+),([-\d.]+)\)', tex).groups()
            return math.hypot(float(x), float(y)) * PT
        assert node('a.style.arc_tick_count = 1\n') - node('') == pytest.approx(4.5, abs=0.01)

    def test_hollow_point_on_a_solid_sheet(self):
        tex = tikz("A = Point(1, 1)\nA.style.point_fill = 'hollow'\nA.style.size_px = 8\n")
        assert re.search(r'\\fill\[fill=agc\d\] \(1,1\) circle \(1\.5pt\);', tex)   # 8/4 px at 0.75 pt/px

    def test_hollow_point_on_a_transparent_sheet(self):
        code = "A = Point(0, 0)\nB = Point(3, 0)\ns = Segment(A, B)\nP = Point(1.5, 0)\nP.style.point_fill = 'hollow'\n"
        tex = tikz(code, background=False)
        assert '\\begin{scope}[even odd rule]' in tex and 'circle (1.125pt)' in tex
        assert not re.search(r'\\fill\[fill=agc\d\] \(1\.5,0\) circle', tex)
        assert 'even odd rule' not in tikz(code)
        assert 'even odd rule' not in tikz(angle_code(), background=False)

    def test_segment_heads_and_chevrons(self):
        tex = tikz(angle_code() + "s = Segment(A, B)\ns.style.arrow_head = 'end'\ns.style.parallel_count = 2\n")
        assert '(0,0) -- (2.8625,0)' in tex                            # the stem stops 11 px short
        assert len([ln for ln in tex.splitlines() if 'line join=miter' in ln]) == 2

    def test_chevrons_on_a_line(self):
        tex = tikz(angle_code() + "l = Line(A, C)\nl.style.parallel_count = 3\n")
        assert len([ln for ln in tex.splitlines() if 'line join=miter' in ln]) == 3

    @pytest.mark.skipif(shutil.which('pdflatex') is None, reason='pdflatex not installed')
    def test_compiles(self, tmp_path):
        s = framed(angle_code(extra="a.style.arc_style = 'wave'\na.style.tick_count = 2\n"
                                    "a.style.arc_tick_count = 1\na.style.arrow_head = 'end'\n"
                                    "a.style.fill_pattern = 'hatch'\na.style.label_visible = True\n")
                   + "b = Angle(C, B, A)\nb.style.arc_style = 'dashed'\n"
                   + "s = Segment(B, C)\ns.style.arrow_head = 'both'\ns.style.parallel_count = 2\n"
                   + "l = Line(A, C)\nl.style.parallel_count = 1\n"
                   + "P = Point(1.5, 0.5)\nP.style.point_fill = 'hollow'\nP.style.point_shape = 'triangle_up'\n")
        for name, kw in (('solid', {}), ('clear', {'background': False})):
            path = tmp_path / f'{name}.tex'
            s.exportTikZ(str(path), standalone=True, **kw)
            proc = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', path.name],
                                  cwd=tmp_path, capture_output=True, text=True)
            assert proc.returncode == 0, proc.stdout[-2000:]


class TestJSXGraph:
    def test_default_values_export_as_before(self):
        assert spec(angle_code() + SEG) == spec(angle_code() + SEG + DEFAULTS)

    def test_segment_heads_are_native(self):
        sp = spec(angle_code() + SEG + "s.style.arrow_head = 'both'\n")
        attrs = element(sp, 's')['attrs']
        assert 'lastArrow' in attrs and 'firstArrow' in attrs
        sp = spec(angle_code() + SEG + "s.style.arrow_head = 'start'\n")
        attrs = element(sp, 's')['attrs']
        assert 'firstArrow' in attrs and 'lastArrow' not in attrs

    def test_hollow_point(self):
        sp = spec("A = Point(1, 1)\nA.style.point_fill = 'hollow'\nA.style.size_px = 8\n")
        attrs = element(sp, 'A')['attrs']
        assert attrs['fillColor'] == '#FFFFFF' and attrs['fillOpacity'] == 1
        assert attrs['strokeWidth'] == 2.0 and attrs['size'] == 3.0     # ring ρ/2 = 2, R − ρ/4 = 3

    def test_decorated_angle(self):
        sp = spec(angle_code(extra="a.style.arc_style = 'wave'\na.style.arc_tick_count = 1\n"
                                   "a.style.arrow_head = 'end'\na.style.fill_pattern = 'hatch'\n"))
        attrs = element(sp, 'a')['attrs']
        assert attrs['type'] == 'sector' and attrs['strokeOpacity'] == 0
        cov = coverage(sp)
        for name in ('__arcs_a', '__arcticks_a', '__heads_a_0'):
            assert cov[name][0] == 'static'
        assert cov['__hatch_a'][0] == 'skip'
        arcs = element(sp, '__arcs_a')
        assert arcs['engine'] == 'curve' and all(not isinstance(p, dict) for p in arcs['parents'])

    def test_one_dashed_arc_is_native(self):
        sp = spec(angle_code(extra="a.style.arc_style = 'dashed'\n"))
        attrs = element(sp, 'a')['attrs']
        assert attrs['dash'] == 1 and 'strokeOpacity' not in attrs
        assert '__arcs_a' not in coverage(sp)

    def test_decorated_right_angle_is_a_sector(self):
        sp = spec(angle_code((0, 2), 'a.style.arc_tick_count = 1\n'))
        assert element(sp, 'a')['attrs']['type'] == 'sector'
        assert 'type' not in element(spec(angle_code((0, 2))), 'a')['attrs']

    def test_chevrons_live_on_a_segment_static_on_a_line(self):
        sp = spec(angle_code() + SEG + 's.style.parallel_count = 2\nl = Line(A, C)\nl.style.parallel_count = 1\n')
        cov = coverage(sp)
        assert [n for n in cov if n.startswith('__parallel_s_') and cov[n][0] == 'live'] == \
            ['__parallel_s_0_0', '__parallel_s_0_1', '__parallel_s_1_0', '__parallel_s_1_1']
        assert cov['__parallel_l'][0] == 'static'

    def test_schema(self):
        jsonschema = pytest.importorskip('jsonschema')
        from animageo.exporters.jsxgraph.spec import load_schema
        sp = spec(angle_code(extra="a.style.arc_style = 'wave'\na.style.arc_tick_count = 2\n") + SEG
                  + "s.style.arrow_head = 'end'\ns.style.parallel_count = 3\nl = Line(A, C)\n"
                  + "l.style.parallel_count = 2\nA.style.point_fill = 'hollow'\n")
        jsonschema.validate(sp, load_schema())
