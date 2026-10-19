"""The flat scene of ``animageo.native.space`` drawn by ``native.render``
(needs manim and LaTeX): the pieces hidden by a solid come out dashed in SVG
and TikZ."""
import re

import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

from animageo.native import space  # noqa: E402
from animageo.native.space import vec  # noqa: E402


def cube_scene():
    cube = space.cube(size=2)
    m = vec.lerp(cube.vertex('A'), cube.vertex('B'), 0.5)
    n = vec.lerp(cube.vertex('B'), cube.vertex('C'), 0.5)
    k = vec.lerp(cube.vertex('C'), cube.vertex('C_1'), 0.5)
    return space.SpaceScene(solids=[space.SceneSolid('cube', cube)],
                            sections=[space.SceneSection('cut', 'cube', space.Plane.through(m, n, k))])


def hidden_pieces(flat):
    return sum(p['visibility'] == 'hidden' for s in flat['strokes'] for p in s['pieces'])


@pytest.mark.parametrize('projection', ['orthographic', 'oblique', 'perspective'])
def test_svg_has_one_dashed_path_per_hidden_piece(tmp_path, projection):
    camera = space.Camera(projection=projection, azimuth_deg=-60, elevation_deg=22, target=(1, 1, 1),
                          distance=8)
    flat = space.flat_scene(cube_scene(), camera)
    assert hidden_pieces(flat) == 6               # three edges at D, three edges of the section
    result = space.render(flat, tmp_path / 'cube.svg', report=True)
    text = (tmp_path / 'cube.svg').read_text(encoding='utf-8')
    dashed = [tag for tag in re.findall(r'<path[^>]*>', text) if 'stroke-dasharray' in tag]
    assert len(dashed) == 6
    assert result.report['diagnostics'] == []
    width = result.report['canvas']['width']
    xmin, _, xmax, _ = flat['bounds']
    assert result.report['canvas']['unit'] == pytest.approx(width / (xmax - xmin))


def test_tikz_and_the_none_look(tmp_path):
    flat = space.flat_scene(cube_scene(), space.Camera(azimuth_deg=-60, elevation_deg=22, target=(1, 1, 1)))
    space.render(flat, tmp_path / 'cube.tex', fmt='tikz')
    tikz = (tmp_path / 'cube.tex').read_text(encoding='utf-8')
    assert len(re.findall(r'dash pattern', tikz)) == 6
    space.render(flat, tmp_path / 'plain.svg', look={'hidden': 'none', 'faces': 'none'})
    assert 'stroke-dasharray' not in (tmp_path / 'plain.svg').read_text(encoding='utf-8')


def test_native_render_draws_a_space_document(tmp_path):
    """``native.render`` hands a space document to the bridge: one path."""
    from animageo.native import render
    from animageo.native.space.build import SpaceBuilder

    b = SpaceBuilder('cube', camera={'azimuthDeg': -60, 'elevationDeg': 25, 'target': [1, 1, 1]})
    b.point('A', 0, 0, 0)
    b.point('B', 2, 0, 0)
    b.cube('K', 'A', 'B', vertices=['C', 'D', 'A_1', 'B_1', 'C_1', 'D_1'])
    out = render(b.data(), out=tmp_path / 'cube.svg', report=True)
    text = (tmp_path / 'cube.svg').read_text(encoding='utf-8')
    assert text.count('stroke-dasharray') >= 3          # the three hidden edges at D
    assert 'K_edge_3--1' in out.report['elements']
    with pytest.raises(NotImplementedError):
        render(b.data(), out=tmp_path / 'cube.mp4', fmt='mp4', timeline={})


# ── labels in pixels of the sheet (1.11.0rc7) ────────────────────────────

SHEET = {'export': {'size': [960, 540], 'fit': 'contain'},
         'content': {'source': 'rendered_bounds', 'padding': 27, 'label_bounds': 'reserve'}}


def _cut_document(far, azimuth=-60):
    """A cube cut by a plane through U, V, W — ``far`` times the near
    triangle, so the sheet of the plane grows with ``far``: the scenes
    ``section_cube_triangle`` (1) and ``section_cube_far_plane`` (3) of the
    space fixtures, the names of A, B and U shown."""
    from animageo.native.space.build import SpaceBuilder
    from animageo.native.space.fixtures import _cube

    b = SpaceBuilder('cut', camera={'projection': 'orthographic', 'azimuthDeg': azimuth, 'elevationDeg': 25,
                                    'target': [1, 1, 1]})
    _cube(b)
    for name, p in zip('UVW', ((far, 0, 0), (0, far, 0), (0, 0, 1.5 * far))):
        b.point(name, *p)
    b.plane('P', 'U', 'V', 'W')
    b.section('S', 'P', 'K')
    data = b.data()
    for el_id in ('A', 'B', 'U'):
        data.setdefault('appearance', {}).setdefault(el_id, {})['label'] = {'mode': 'name'}
    return data


def _decoration_px(report):
    """The width and height of the labels of A and U and the size of the point A, px."""
    out = []
    for el_id in ('A', 'U'):
        x0, y0, x1, y1 = report['elements'][el_id]['label']['box']
        out += [x1 - x0, y1 - y0]
    x0, _, x1, _ = report['elements']['A']['box']
    return out + [x1 - x0]


def test_labels_and_points_are_in_pixels_of_the_sheet(tmp_path):
    """The size of a label (and of a point) on the sheet does not depend on
    how far the frame reaches: a sheet of the plane three times as large, or
    another camera, leaves them as they are — the style pixels of the sheet,
    as drawn without a layout. Before, they followed the frame (``frame``
    decorations of a plane document whose source view is the extent of the
    picture): 6.8 px wide against 4.4 px."""
    from animageo.native import render

    plain = _decoration_px(render(_cut_document(1), out=tmp_path / 'plain.svg').report)
    for far, azimuth in ((1, -60), (3, -60), (1, 35)):
        got = _decoration_px(render(_cut_document(far, azimuth), out=tmp_path / f'{far}.svg',
                                    export_layout=SHEET).report)
        assert got == pytest.approx(plain, abs=3e-3), (far, azimuth)      # the report rounds to 0.001 px


def test_a_caller_drawing_the_plane_document_takes_the_sheet_layout(tmp_path):
    """The plane document of a flat scene drawn by ``native.render`` under
    ``space.sheet_layout`` is the drawing of ``space.render``; a layout that
    names its own decoration basis keeps it."""
    from animageo.native import render

    doc = _cut_document(3)
    flat = space.flat_scene(doc)
    plane = space.to_document(flat, doc)
    layout = space.sheet_layout(SHEET)
    assert layout['content']['decoration_scale_source'] == 'output'
    assert 'decoration_scale_source' not in SHEET['content']        # the layout of the caller is not changed
    own = render(plane, out=tmp_path / 'plane.svg', export_layout=layout).report
    assert _decoration_px(own) == pytest.approx(
        _decoration_px(render(doc, out=tmp_path / 'space.svg', export_layout=SHEET).report), abs=1e-9)
    framed = {**SHEET, 'content': {**SHEET['content'], 'decoration_scale_source': 'frame'}}
    assert space.sheet_layout(framed)['content']['decoration_scale_source'] == 'frame'
    assert space.sheet_layout(None) is None
