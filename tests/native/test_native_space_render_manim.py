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
