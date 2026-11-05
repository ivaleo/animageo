"""Export scale invariant: every decoration of the file is its style value in
px times the export scale ``S`` (``reference`` canvas → ``export.scale`` of
``fit: "manual"``, or the ``contain`` fit of a larger canvas), and the
geometry scales with it. «Крупность» (``content.prominence``) multiplies only
the decorations; ``decoration_scale_source: "output"`` pins them to their style
px whatever ``S`` is (needs manim and LaTeX)."""
import re

import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

from animageo import native  # noqa: E402
from tests.native.conftest import DocBuilder  # noqa: E402

REFERENCE = {'width': 800, 'height': 600}

# the order of the paths in the SVG of ``scene()``
ARC, S1, TICK1_A, TICK1_B, S2, TICK2_A, TICK2_B, DASHED, A_DOT, A_TEXT, B_DOT, B_TEXT, C_DOT, C_TEXT = range(14)


def scene():
    b = DocBuilder('export_scale', registry_version='1.5', bounds=(-6, -4, 6, 4))
    b.free('A', -4, -2).free('B', 4, -2).free('C', 0, 3)
    b.segment('s1', 'A', 'B').segment('s2', 'A', 'C').segment('s3', 'B', 'C')
    b.equal_segments('m1', 's1', 's2', count=2)
    b.angle('ang', 'B', 'A', 'C')
    b.doc['appearance'] = {
        's3': {'overrides': {'stroke_dash_ratio': 0.5, 'stroke_dash_period_px': 10, 'stroke_width_px': 3}},
        'A': {'overrides': {'size_px': 8, 'font_size_px': 20, 'label_radial_offset_px': 12},
              'label': {'mode': 'name'}},
        'B': {'label': {'mode': 'name'}}, 'C': {'label': {'mode': 'name'}},
        'ang': {'overrides': {'arc_size_px': 30, 'stroke_width_px': 2}},
        'm1': {'overrides': {'tick_length_px': 12, 'tick_width_px': 2}},
    }
    return b.doc


def paths(svg):
    """Per ``<path>``: bbox in px (canvas centre at 0, 0), stroke width and dash in px."""
    size = re.search(r'width="([\d.]+)" height="([\d.]+)"', svg)
    cx, cy = float(size.group(1)) / 2, float(size.group(2)) / 2
    out = []
    for m in re.finditer(r'<path ([^>]*?)/>', svg):
        attrs = m.group(1)
        nums = [float(x) for x in re.findall(r'-?\d+\.?\d*(?:e-?\d+)?', re.search(r' d="([^"]*)"', attrs).group(1))]
        tm = re.search(r'transform="matrix\(([^)]*)\)"', attrs)
        sx, _, _, sy, tx, ty = [float(v) for v in tm.group(1).split(',')] if tm else (1, 0, 0, 1, 0, 0)
        xs = [x * sx + tx - cx for x in nums[0::2]]
        ys = [y * sy + ty - cy for y in nums[1::2]]
        sw = re.search(r'stroke-width="([^"]*)"', attrs)
        da = re.search(r'stroke-dasharray="([^"]*)"', attrs)
        out.append({'box': (min(xs), min(ys), max(xs), max(ys)),
                    'stroke': float(sw.group(1)) * abs(sx) if sw else 0.0,
                    'dash': [float(v) * abs(sx) for v in da.group(1).replace(',', ' ').split()] if da else []})
    return out


def render(tmp_path, name, export, content=None, reference=REFERENCE):
    layout = {'reference': {'size': reference}, 'export': export}
    if content:
        layout['content'] = content
    native.render(scene(), export_layout=layout, out=tmp_path / f'{name}.svg', report=False)
    return paths((tmp_path / f'{name}.svg').read_text(encoding='utf-8'))


def manual(scale, size):
    return {'size': list(size), 'fit': 'manual', 'scale': scale, 'anchor': 'center'}


def assert_scaled(base, other, factor, tol=0.01):
    """Everything — boxes (geometry and marks hanging on it), stroke widths, dashes — is ``factor`` times."""
    assert len(base) == len(other) == 14
    for i, (a, b) in enumerate(zip(base, other)):
        for u, v in zip(a['box'], b['box']):
            assert v == pytest.approx(u * factor, abs=tol + 0.002 * abs(u * factor)), (i, 'box')
        assert b['stroke'] == pytest.approx(a['stroke'] * factor, abs=tol), (i, 'stroke')
        for u, v in zip(a['dash'], b['dash']):
            assert v == pytest.approx(u * factor, abs=tol), (i, 'dash')


def test_style_px_at_unit_scale(tmp_path):
    base = render(tmp_path, 's1', manual(1, (800, 600)))
    assert base[DASHED]['stroke'] == pytest.approx(3.0, abs=0.01)           # stroke_width_px
    assert sum(base[DASHED]['dash'][:2]) == pytest.approx(10.0, abs=0.1)           # stroke_dash_period_px
    assert base[ARC]['stroke'] == pytest.approx(2.0, abs=0.01)                     # arc stroke_width_px
    assert base[ARC]['box'][2] - base[ARC]['box'][0] > 0
    assert base[TICK1_A]['box'][3] - base[TICK1_A]['box'][1] == pytest.approx(12.0, abs=0.01)   # tick_length_px
    assert base[TICK1_A]['stroke'] == pytest.approx(2.0, abs=0.01)                 # tick_width_px
    assert base[A_DOT]['box'][2] - base[A_DOT]['box'][0] == pytest.approx(8.0, abs=0.01)        # size_px
    assert base[B_DOT]['box'][2] - base[B_DOT]['box'][0] == pytest.approx(6.0, abs=0.01)        # built-in point


@pytest.mark.parametrize('scale', [2, 0.5])
def test_marks_and_geometry_scale_with_export_scale(tmp_path, scale):
    base = render(tmp_path, 'b', manual(1, (800, 600)))
    other = render(tmp_path, 'o', manual(scale, (int(800 * scale), int(600 * scale))))
    assert_scaled(base, other, scale)


def test_contain_fit_of_a_larger_canvas_is_the_same_scale(tmp_path):
    manual2 = render(tmp_path, 'm', manual(2, (1600, 1200)))
    contain2 = render(tmp_path, 'c', {'size': [1600, 1200], 'fit': 'contain'})
    assert_scaled(manual2, contain2, 1.0)


def test_scale_is_against_the_reference_canvas_not_the_file_size(tmp_path):
    # reference 400x300 with S = 2 → the 800x600 file: marks ×2 of their style px
    small_ref = render(tmp_path, 'r', manual(2, (800, 600)), reference={'width': 400, 'height': 300})
    unit = render(tmp_path, 'u', manual(1, (800, 600)))
    assert small_ref[ARC]['stroke'] == pytest.approx(2 * unit[ARC]['stroke'], abs=0.01)
    assert small_ref[DASHED]['stroke'] == pytest.approx(2 * unit[DASHED]['stroke'], abs=0.01)
    assert small_ref[A_DOT]['box'][2] - small_ref[A_DOT]['box'][0] == pytest.approx(16.0, abs=0.01)


def test_prominence_scales_only_the_marks(tmp_path):
    base = render(tmp_path, 'b', manual(1, (800, 600)))
    big = render(tmp_path, 'p', manual(1, (800, 600)), {'prominence': 1.5})
    for i in (S1, S2):                                  # sides: geometry, but the width is a mark
        assert big[i]['box'] == pytest.approx(base[i]['box'], abs=0.01)
        assert big[i]['stroke'] == pytest.approx(1.5 * base[i]['stroke'], abs=0.01)
    assert big[DASHED]['stroke'] == pytest.approx(4.5, abs=0.01)
    assert big[TICK1_A]['box'][3] - big[TICK1_A]['box'][1] == pytest.approx(18.0, abs=0.01)
    assert big[A_DOT]['box'][2] - big[A_DOT]['box'][0] == pytest.approx(12.0, abs=0.01)


def test_output_basis_pins_marks_to_style_px_whatever_the_scale(tmp_path):
    base = render(tmp_path, 'b', manual(1, (800, 600)), {'decoration_scale_source': 'output'})
    big = render(tmp_path, 'o', manual(2, (1600, 1200)), {'decoration_scale_source': 'output'})
    for i in (DASHED, ARC, TICK1_A, S1):
        assert big[i]['stroke'] == pytest.approx(base[i]['stroke'], abs=0.01)
    assert big[A_DOT]['box'][2] - big[A_DOT]['box'][0] == pytest.approx(8.0, abs=0.01)
    assert big[S1]['box'][2] - big[S1]['box'][0] == pytest.approx(2 * (base[S1]['box'][2] - base[S1]['box'][0]),
                                                                abs=0.05)             # the geometry still scales
