"""1.10.0a2: the frame of TikZ/TeX is the frame of SVG (G1-D of the web, decision 2).

``native.render(fmt="tikz" | "tex", export_layout=…)`` clips the picture to
the export canvas of the same layout — the canvas of SVG, PNG, PDF and EPS —
and takes it as the bounding box of the ``tikzpicture``. Before, the clip was
the manim camera frame (16:9): the height was right, the width was not.
The classic ``exportTikZ`` keeps the camera frame unless asked
(``TikZOptions(frame="export")``).
"""
import re
import shutil
import subprocess
import zlib
from pathlib import Path

import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

from animageo import AnimaGeoScene, native  # noqa: E402
from tests.native.conftest import DocBuilder, ref  # noqa: E402

LAYOUTS = {
    'source': None,
    'web_exact_frame': {'content': {'source': 'rendered_bounds', 'padding': 40},
                        'export': {'size': {'width': 1600, 'height': 1000}, 'fit': 'contain'}},
    'wide': {'export': {'size': {'width': 2000, 'height': 600}, 'fit': 'contain'}},
    'portrait': {'content': {'source': 'rendered_bounds', 'padding': 20},
                 'export': {'size': {'width': 600, 'height': 900}}},
    'reference': {'reference': {'size': {'width': 400, 'height': 400}},
                  'export': {'size': {'width': 800, 'height': 600}}},
}


def frame_doc():
    """A triangle with labels, a line across the view and a hatched polygon."""
    b = DocBuilder('frame', registry_version='1.5', bounds=(-6, -4, 6, 4))
    b.free('A', -3, -2).free('B', 3, -2).free('C', 0, 2.5)
    b.op('op_t', 'polygon.by_points', {'vertices': {'kind': 'list', 'items': [ref('A'), ref('B'), ref('C')]}},
         [('polygon', 't', 'polygon')])
    b.line('g', 'A', 'C')
    b.doc['appearance'] = {'t': {'overrides': {'fill_pattern': 'hatch'}}}
    return b.doc


CLIP = re.compile(r'\\clip \((-?[\d.]+),(-?[\d.]+)\) rectangle \((-?[\d.]+),(-?[\d.]+)\);')
BBOX = re.compile(r'\\useasboundingbox \((-?[\d.]+),(-?[\d.]+)\) rectangle \((-?[\d.]+),(-?[\d.]+)\);')


def _unit_cm(body: str) -> float:
    m = re.search(r'\[x=([\d.]+)cm, y=([\d.]+)cm', body)
    assert m and m.group(1) == m.group(2)
    return float(m.group(1))


def _svg_size(text: str):
    w = re.search(r'<svg[^>]* width="([\d.]+)', text).group(1)
    h = re.search(r'<svg[^>]* height="([\d.]+)', text).group(1)
    box = [float(v) for v in re.search(r'viewBox="([^"]+)"', text).group(1).split()]
    return float(w), float(h), box


@pytest.fixture(scope='module')
def rendered(tmp_path_factory):
    out = tmp_path_factory.mktemp('frame')
    cache = {}

    def run(name, fmt):
        if (name, fmt) not in cache:
            result = native.render(frame_doc(), fmt=fmt, out=out / f'{name}.{fmt}', export_layout=LAYOUTS[name])
            cache[(name, fmt)] = (Path(result.path).read_text(encoding='utf-8'), result.report)
        return cache[(name, fmt)]
    return run


@pytest.mark.parametrize('fmt', ('tikz', 'tex'))
@pytest.mark.parametrize('name', sorted(LAYOUTS))
def test_the_clip_is_the_svg_frame(rendered, name, fmt):
    svg, report = rendered(name, 'svg')
    body, tex_report = rendered(name, fmt)
    width, height, box = _svg_size(svg)
    assert box == [0, 0, width, height]
    assert tex_report['canvas'] == report['canvas']
    x0, y0, x1, y1 = (float(v) for v in CLIP.search(body).groups())
    cm = _unit_cm(body)
    px = cm / 2.54 * 96                       # one world unit in pixels at 96 dpi (the SVG pixel)
    assert (x1 - x0) * px == pytest.approx(width, abs=0.05)
    assert (y1 - y0) * px == pytest.approx(height, abs=0.05)
    # the same place: the top-left corner of the clip is the pixel (0, 0) of the SVG
    unit = report['canvas']['unit']
    ox, oy = report['canvas']['origin']
    assert px == pytest.approx(unit, rel=1e-5)
    assert x0 == pytest.approx(-ox / unit, abs=1e-4) and y1 == pytest.approx(oy / unit, abs=1e-4)
    # the picture is the frame: the bounding box and the background are the clip
    assert BBOX.search(body).groups() == CLIP.search(body).groups()
    rect = '({},{}) rectangle ({},{})'.format(*CLIP.search(body).groups())
    assert f'\\fill[agc0] {rect};' in body


def test_the_web_frame_keeps_its_ratio(rendered):
    """The check of the web (``test_real_tex_frame_is_the_exact_frame``): w / h of the clip."""
    body, _ = rendered('web_exact_frame', 'tex')
    x0, y0, x1, y1 = (float(v) for v in CLIP.search(body).groups())
    assert (x1 - x0) / (y1 - y0) == pytest.approx(1600 / 1000, rel=0.001)


def test_hatching_reaches_tikz(rendered):
    body, report = rendered('web_exact_frame', 'tex')
    assert report['diagnostics'] == []
    hatch = [line for line in body.splitlines()
             if line.strip().startswith('\\draw') and line.count(' -- ') > 10 and 'cycle' not in line]
    assert len(hatch) == 1


def test_lines_still_reach_the_frame_edges(rendered):
    """A line is cut by the clip, not shortened to the frame: its ends lie outside it or on it."""
    body, _ = rendered('wide', 'tikz')
    x0, y0, x1, y1 = (float(v) for v in CLIP.search(body).groups())
    line = [ln for ln in body.splitlines() if ln.strip().startswith('\\draw') and ln.count(' -- ') == 1][-1]
    (ax, ay), (bx, by) = [(float(a), float(b)) for a, b in re.findall(r'\((-?[\d.]+),(-?[\d.]+)\)', line)]
    assert min(ay, by) <= y0 + 1e-3 and max(ay, by) >= y1 - 1e-3


def _classic_scene():
    scene = AnimaGeoScene()
    scene.putCode('A = Point(-3, -2)\nB = Point(3, -2)\nC = Point(0, 2.5)\nt = Polygon(A, B, C)\n')
    scene.applyStyle(export={'size': {'width': 1600, 'height': 1000}})
    return scene


def test_the_classic_export_keeps_the_camera_frame_unless_asked():
    scene = _classic_scene()
    camera = scene.exportTikZ()
    x0, y0, x1, y1 = (float(v) for v in CLIP.search(camera).groups())
    left, bottom, right, top = scene._get_scene_bounds(padding=0)
    assert (x0, y0, x1, y1) == pytest.approx((left, bottom, right, top), abs=1e-4)
    assert '\\useasboundingbox' not in camera
    exact = scene.exportTikZ(frame='export')
    x0, y0, x1, y1 = (float(v) for v in CLIP.search(exact).groups())
    export = scene.style.export
    assert (x1 - x0) / (y1 - y0) == pytest.approx(int(export['ptWidth']) / int(export['ptHeight']), rel=1e-4)
    assert BBOX.search(exact)
    with pytest.raises(ValueError):
        scene.exportTikZ(frame='nope')


def test_feature_flag():
    assert native.has('render.tikz_frame')


def _pdf_media_box(data: bytes) -> list:
    chunks = [data]
    for m in re.finditer(rb'stream\r?\n(.*?)\r?\nendstream', data, re.S):
        try:
            chunks.append(zlib.decompress(m.group(1)))
        except zlib.error:
            continue
    for chunk in chunks:
        match = re.search(rb'/MediaBox\s*\[\s*([-\d.\s]+)\]', chunk)
        if match:
            return [float(v) for v in match.group(1).split()]
    raise AssertionError('no MediaBox')


@pytest.mark.slow
@pytest.mark.skipif(shutil.which('pdflatex') is None, reason='pdflatex is not installed')
@pytest.mark.parametrize('name', ('web_exact_frame', 'wide'))
def test_the_compiled_tex_has_the_size_of_the_pdf(tmp_path, name):
    """The page of the compiled TeX is the page of ``render(fmt="pdf")`` (px · 0.75 bp)."""
    doc = frame_doc()
    native.render(doc, fmt='tex', out=tmp_path / 'a.tex', export_layout=LAYOUTS[name], report=False)
    run = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', 'a.tex'], cwd=tmp_path,
                         capture_output=True, timeout=180)
    assert run.returncode == 0, run.stdout[-2000:]
    tex_box = _pdf_media_box((tmp_path / 'a.pdf').read_bytes())
    pdf = native.render(doc, fmt='pdf', out=tmp_path / 'b.pdf', export_layout=LAYOUTS[name], report=False)
    pdf_box = _pdf_media_box(Path(pdf.path).read_bytes())
    assert tex_box[2] - tex_box[0] == pytest.approx(pdf_box[2] - pdf_box[0], abs=1.2)
    assert tex_box[3] - tex_box[1] == pytest.approx(pdf_box[3] - pdf_box[1], abs=1.2)
