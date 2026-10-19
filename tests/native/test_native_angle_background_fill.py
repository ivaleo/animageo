"""An angle filled with the background colour has no fill (1.11.0rc3).

The built-in style fills an angle with ``presets.color.background`` at
opacity 1. Drawn as is, the sector (and the square of a right angle) is an
opaque white wedge over the fill of the figure the angle sits in. As on the
canvas of the web app, a fill of the background colour is no fill: the
pixels inside the sector are those of the figure under it.
"""
import math

import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

from animageo import native  # noqa: E402
from animageo.style.colorspace import same_color  # noqa: E402
from tests.native.conftest import DocBuilder  # noqa: E402

FILL = '#4a90d9'
FILL_OPACITY = 0.35


def wedge(right=False):
    """A filled triangle ABC with the angles at A and B in the built-in style
    (the ``wedge`` scene of the paint fixtures); ``right`` makes the angle at A
    a right one."""
    b = DocBuilder('wedge', bounds=(-1, -1, 6, 4.5), registry_version='1.1')
    b.free('A', 0, 0).free('B', 5, 0).free('C', 0 if right else 1.5, 3.5)
    b.polygon('T', 'A', 'B', 'C', sides=[(1, 'a'), (2, 'b'), (3, 'c')])
    b.angle('alpha', 'B', 'A', 'C').angle('beta', 'C', 'B', 'A')
    b.doc['appearance'] = {e: {'label': {'mode': 'none'}} for e in b.doc['elements']}
    b.doc['appearance']['T']['overrides'] = {'fill': FILL, 'fill_opacity': FILL_OPACITY}
    return b.doc


def _px(report, x, y):
    canvas = report['canvas']
    return canvas['origin'][0] + canvas['unit'] * x, canvas['origin'][1] - canvas['unit'] * y


def _pixel(path, xy):
    from PIL import Image
    with Image.open(path) as image:
        return image.convert('RGB').getpixel((int(round(xy[0])), int(round(xy[1]))))


def _close(a, b, tol=2):
    return all(abs(int(p) - int(q)) <= tol for p, q in zip(a, b))


def test_same_color():
    assert same_color('#FFFFFF', '#ffffff')
    assert same_color('#fff', '#ffffff')
    assert not same_color('#fffffe', '#ffffff')
    assert not same_color(None, '#ffffff')
    assert not same_color('stroke', '#ffffff')


@pytest.mark.parametrize('right', [False, True])
def test_pixels_inside_the_sector_are_the_fill_of_the_triangle(tmp_path, right):
    pytest.importorskip('cairosvg')
    result = native.render(wedge(right), fmt='png', out=tmp_path / 'w.png')
    report = result.report
    # inside the arc of the angle at A (17 px of the style) on its bisector,
    # and inside the triangle far from any angle
    toward = math.atan2(3.5, 0 if right else 1.5) / 2
    at = _px(report, 0, 0)
    inside = (at[0] + 6 * math.cos(toward), at[1] - 6 * math.sin(toward))
    far = _px(report, 2.0 if not right else 1.5, 1.2)
    sector, triangle = _pixel(result.path, inside), _pixel(result.path, far)
    assert triangle != (255, 255, 255)
    assert _close(sector, triangle), (sector, triangle)


def test_an_explicit_fill_is_drawn(tmp_path):
    pytest.importorskip('cairosvg')
    doc = wedge()
    doc['appearance']['alpha']['overrides'] = {'fill': '#d05456', 'fill_opacity': 1}
    result = native.render(doc, fmt='png', out=tmp_path / 'w.png')
    report = result.report
    toward = math.atan2(3.5, 1.5) / 2
    at = _px(report, 0, 0)
    sector = _pixel(result.path, (at[0] + 6 * math.cos(toward), at[1] - 6 * math.sin(toward)))
    assert _close(sector, (0xd0, 0x54, 0x56), tol=6), sector


def test_tikz_has_no_fill_of_a_background_angle(tmp_path):
    doc = wedge()
    del doc['appearance']['T']['overrides']
    text = open(native.render(doc, fmt='tikz', out=tmp_path / 'w.tex', report=False).path,
                encoding='utf-8').read()
    fills = [line for line in text.splitlines() if line.lstrip().startswith('\\fill') and ' arc ' in line]
    assert fills == []
