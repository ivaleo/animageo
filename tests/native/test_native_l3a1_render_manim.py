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
from tests.native.test_native_render_manim import dsl_svg, no_labels, path_tags  # noqa: E402

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


# ── DSL pairs: the same picture drawn from the classic DSL ───────────────

def _lit(values, el_id):
    v = values[el_id]['value']
    return f'Point({v["x"]!r}, {v["y"]!r})'


def pair_altitude():
    """An acute altitude (no extension) and an obtuse one with its extension;
    the feet as literals of the native values."""
    b = DocBuilder('altitude', registry_version='1.5', bounds=BOUNDS)
    b.free('A', -4, -2).free('B', 0, -2).free('C', -1, 3).free('D', 3, 2)
    b.segment('s', 'A', 'B')
    b.op('op_h', 'triangle.altitude', {'vertex': ref('C'), 'side': ref('s')},
         [('altitude', 'h', 'segment'), ('foot', 'H', 'point'), ('extension', 'x', 'segment')])
    b.op('op_k', 'triangle.altitude', {'vertex': ref('D'), 'side': ref('s')},
         [('altitude', 'k', 'segment'), ('foot', 'K', 'point'), ('extension', 'e', 'segment')])
    values = native.evaluate(b.doc).elements
    assert values['x']['state'] == 'undefined' and values['e']['state'] == 'defined'
    return b.doc, ('A = Point(-4, -2)\nB = Point(0, -2)\nC = Point(-1, 3)\nD = Point(3, 2)\n'
                   f's = Segment(A, B)\nH = {_lit(values, "H")}\nh = Segment(C, H)\n'
                   f'K = {_lit(values, "K")}\nk = Segment(D, K)\ne = Segment(B, K)\n'), None


def pair_roles():
    """Roles give the drawing of the same keys written to the elements."""
    from animageo.style.schema import ROLE_DEFAULTS
    b = DocBuilder('role_pair', registry_version='1.5', bounds=BOUNDS)
    b.free('A', -4, -2).free('B', 4, -2).free('C', 1, 3)
    b.segment('s', 'A', 'B').segment('t', 'B', 'C')
    b.op('op_h', 'triangle.altitude', {'vertex': ref('C'), 'side': ref('s')},
         [('altitude', 'h', 'segment'), ('foot', 'H', 'point')])
    b.doc['appearance'] = {'s': {'role': 'given'}, 't': {'role': 'aux'}, 'h': {'role': 'sought'},
                           'H': {'role': 'sought'}, 'A': {'role': 'given'}}
    values = native.evaluate(b.doc).elements

    def keys(role, point=False):
        entry = ROLE_DEFAULTS[role]
        return dict(entry['point']) if point else {k: v for k, v in entry.items() if k != 'point'}
    style = {'s': keys('given'), 't': keys('aux'), 'h': keys('sought'), 'H': keys('sought', True),
             'A': keys('given', True)}
    return b.doc, ('A = Point(-4, -2)\nB = Point(4, -2)\nC = Point(1, 3)\ns = Segment(A, B)\n'
                   f't = Segment(B, C)\nH = {_lit(values, "H")}\nh = Segment(C, H)\n'), style


@pytest.mark.parametrize('pair', [pair_altitude, pair_roles], ids=['altitude', 'roles'])
def test_same_paths_as_the_dsl(pair, tmp_path):
    doc, code, style = pair()
    appearance = doc.get('appearance', {})
    no_labels(doc)
    for el_id, entry in appearance.items():
        doc['appearance'][el_id].update(entry)
    native.render(doc, out=tmp_path / 'native.svg', report=False)
    dsl_svg(code, BOUNDS, tmp_path / 'dsl.svg', style)
    native_paths, dsl_paths = path_tags(tmp_path / 'native.svg'), path_tags(tmp_path / 'dsl.svg')
    assert sum(native_paths.values()) > 0
    assert native_paths == dsl_paths


def test_locus_drawn_as_the_dsl_locus(tmp_path):
    """``ГМТ`` and the classic ``Locus``: the same paths but for their points
    (the native curve comes from the kernel's samples, the classic one from
    ``_build_locus``)."""
    b = DocBuilder('locus_pair', registry_version='1.5', bounds=BOUNDS)
    b.free('A', -4, -2).free('B', 4, -2).free('C', 1, 3)
    b.segment('s', 'A', 'B')
    b.op('op_P', 'point.on_path', {'path': ref('s')}, [('point', 'P', 'point')])
    b.doc['inputs']['P'] = path_input(0.25)
    b.midpoint('M', 'C', 'P')
    b.op('op_g', 'locus.of_point', {'trace': ref('M'), 'mover': ref('P')}, [('locus', 'g', 'locus')])
    b.doc['appearance'] = {'P': {'visible': False}, 'M': {'visible': False}}
    appearance = b.doc['appearance']
    no_labels(b.doc)
    for el_id, entry in appearance.items():
        b.doc['appearance'][el_id].update(entry)
    native.render(b.doc, out=tmp_path / 'native.svg', report=False)
    code = ('A = Point(-4, -2)\nB = Point(4, -2)\nC = Point(1, 3)\ns = Segment(A, B)\n'
            'P = Point(s)\nP.tparam = 0.25\nM = Midpoint(C, P)\ng = Locus(M, P)\n')
    dsl_svg(code, BOUNDS, tmp_path / 'dsl.svg', {'P': {'visible': False}, 'M': {'visible': False}})

    def shapes(path):
        return sorted(re.sub(r'\sd="[^"]*"', '', tag) for tag, n in path_tags(path).items() for _ in range(n))
    assert shapes(tmp_path / 'native.svg') == shapes(tmp_path / 'dsl.svg')
    no_locus = dict(b.doc, operations={k: v for k, v in b.doc['operations'].items() if k != 'op_g'},
                    elements={k: v for k, v in b.doc['elements'].items() if k != 'g'})
    native.render(no_locus, out=tmp_path / 'plain.svg', report=False)
    assert len(shapes(tmp_path / 'native.svg')) == len(shapes(tmp_path / 'plain.svg')) + 1
