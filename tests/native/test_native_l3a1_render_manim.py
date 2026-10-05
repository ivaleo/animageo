"""1.9.0a1: ``native.render`` to EPS, TikZ and standalone TeX, roles in the
picture and the report, a locus with breaks (needs manim and LaTeX)."""
import re
import shutil
import subprocess

import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

from animageo import AnimaGeoScene, native  # noqa: E402
from animageo.geo.lib_elements import LocusCurve  # noqa: E402
from tests.native.conftest import DocBuilder, path_input, ref  # noqa: E402

BOUNDS = (-6, -4, 6, 4)


def role_doc():
    b = DocBuilder('roles', registry_version='1.5', bounds=BOUNDS)
    b.free('A', -3, -2).free('B', 3, -2).free('C', 0, 2)
    b.op('op_t', 'polygon.by_points', {'vertices': {'kind': 'list', 'items': [ref('A'), ref('B'), ref('C')]}},
         [('polygon', 't', 'polygon')])
    b.segment('a', 'B', 'C')
    b.op('op_h', 'triangle.altitude', {'vertex': ref('A'), 'side': ref('a')},
         [('altitude', 'h', 'segment'), ('foot', 'H', 'point')])
    b.doc['appearance'] = {'h': {'role': 'sought'}, 'H': {'role': 'sought'}, 'a': {'role': 'aux'},
                           't': {'overrides': {'fill_pattern': 'hatch'}}}
    return b.doc


def locus_doc():
    b = DocBuilder('locus', registry_version='1.5', bounds=BOUNDS)
    b.free('O', 0, 0).free('R', 2, 0).free('B', -3, -1).free('C', 3, -1)
    b.circle('c', 'O', 'R').segment('s', 'B', 'C')
    b.op('op_P', 'point.on_path', {'path': ref('s')}, [('point', 'P', 'point')])
    b.doc['inputs']['P'] = path_input(0.5)
    b.op('op_v', 'line.perpendicular', {'point': ref('P'), 'base': ref('s')}, [('line', 'v', 'line')])
    b.op('op_X', 'intersect.line_circle', {'line': ref('v'), 'circle': ref('c')}, [('first', 'X', 'point')])
    b.op('op_g', 'locus.of_point', {'trace': ref('X'), 'mover': ref('P')}, [('locus', 'g', 'locus')])
    return b.doc


def test_render_eps_tikz_tex(tmp_path):
    doc = role_doc()
    eps = native.render(doc, fmt='eps', out=tmp_path / 'a.eps')
    assert open(eps.path, 'rb').read(4) == b'%!PS'
    tikz = native.render(doc, fmt='tikz', out=tmp_path / 'a.tikz', report=False)
    text = open(tikz.path, encoding='utf-8').read()
    assert '\\begin{tikzpicture}' in text and '\\documentclass' not in text
    tex = native.render(doc, fmt='tex', out=tmp_path / 'a.tex', report=False)
    assert '\\documentclass' in open(tex.path, encoding='utf-8').read()
    assert eps.report['fmt'] == 'eps'
    assert eps.report['elements']['h']['role'] == 'sought' and 'role' not in eps.report['elements']['A']


@pytest.mark.slow
@pytest.mark.skipif(shutil.which('pdflatex') is None, reason='pdflatex is not installed')
def test_standalone_tex_compiles(tmp_path):
    tex = native.render(role_doc(), fmt='tex', out=tmp_path / 'a.tex', report=False)
    run = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', 'a.tex'], cwd=tmp_path,
                         capture_output=True, timeout=180)
    assert run.returncode == 0, run.stdout[-2000:]
    assert (tmp_path / 'a.pdf').stat().st_size > 0


@pytest.mark.slow
@pytest.mark.skipif(shutil.which('gs') is None, reason='ghostscript is not installed')
def test_eps_opens_in_ghostscript(tmp_path):
    eps = native.render(role_doc(), fmt='eps', out=tmp_path / 'a.eps', report=False)
    run = subprocess.run(['gs', '-q', '-dNOPAUSE', '-dBATCH', '-sDEVICE=nullpage', eps.path],
                         capture_output=True, timeout=120)
    assert run.returncode == 0


def test_role_styles_the_drawing():
    from animageo.style.resolver import resolve
    scene = AnimaGeoScene()
    scene.loadDocument(role_doc())
    names = scene.native_names
    presets = scene.style_config.presets
    h = scene.geo.element(names.by_id['h'])
    a = scene.geo.element(names.by_id['a'])
    assert str(resolve(scene, h, 'stroke')).lower() == str(presets['color']['accent']).lower()
    assert float(resolve(scene, h, 'stroke_width_px')) == float(presets['line_width']['bold'])
    assert float(resolve(scene, a, 'stroke_dash_ratio')) == 0.5


def test_role_changes_the_svg(tmp_path):
    doc = role_doc()
    plain = role_doc()
    plain['appearance'] = {'t': {'overrides': {'fill_pattern': 'hatch'}}}
    a = open(native.render(doc, out=tmp_path / 'a.svg', report=False).path, encoding='utf-8').read()
    b = open(native.render(plain, out=tmp_path / 'b.svg', report=False).path, encoding='utf-8').read()
    assert a != b


def test_locus_curve_with_breaks_and_report_box(tmp_path):
    result = native.render(locus_doc(), out=tmp_path / 'l.svg')
    record = result.report['elements']['g']
    assert record['state'] == 'defined' and record['visible'] and record['box'] is not None
    ev = native.evaluate(locus_doc())
    pts = [p for p in ev.elements['g']['value']['points'] if p is not None]
    canvas = result.report['canvas']
    x0 = canvas['origin'][0] + canvas['unit'] * min(p[0] for p in pts)
    assert abs(record['box'][0] - round(x0, 3)) < 1e-6


def test_locus_curve_runs_draw_separately():
    scene = AnimaGeoScene()
    scene.loadDocument(locus_doc())
    elem = scene.geo.element(scene.native_names.by_id['g'])
    elem.data = LocusCurve([[0, 0], [1, 0], [3, 0], [4, 0]], breaks=[2])
    mobj = scene._render_locuscurve(elem, scene._build_render_ctx(elem, 0))
    assert len(mobj.submobjects) == 2
    assert [len(r) for r in elem.data.runs()] == [2, 2]
    elem.data = LocusCurve([[0, 0], [1, 0], [3, 0], [4, 0]])
    assert len(scene._render_locuscurve(elem, scene._build_render_ctx(elem, 0)).submobjects) == 1
    assert re.match(r'LocusCurve', repr(elem.data))
