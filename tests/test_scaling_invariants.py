"""Baseline regression tests for GGB → elem.ggb_style scaling formulas.

These tests lock in the CURRENT behavior of ggb_parser.parse_constr():
- pointSize × 2 → elem.ggb_style['size_px']
- thickness / 2 → elem.ggb_style['stroke_width_px']
- arcSize (unchanged) → elem.ggb_style['arc_size_px']
- labelOffset (x, y) → elem.ggb_style['label_offset_px'] = [x, -y]
- objColor rgb → elem.ggb_style['stroke'], 'fill', 'label_color'

Values are taken from examples/0_sample_scenes/scene.ggb (point A, segment c,
angle α) — stable fixture checked into the repo.

If any of these assertions fail after a refactor, something changed in the
parser's scaling pipeline and the snapshot in test_loadggb_snapshot.py will
also need to be reviewed.
"""
import os

import pytest

from animageo.geo.construction import Construction
from animageo.parsers import ggb_parser


FIXTURE = os.path.join(
    os.path.dirname(__file__),
    '..',
    'examples',
    '0_sample_scenes',
    'scene.ggb',
)


@pytest.fixture(scope='module')
def parsed_scene():
    if not os.path.isfile(FIXTURE):
        pytest.skip(f'Fixture not found: {FIXTURE}')
    c = Construction()
    view = {'ptUnit': 1, 'ptWidth': 640, 'ptHeight': 480, 'ptXZero': 0, 'ptYZero': 0}
    ggb_parser.load(c, view, FIXTURE, debug=False)
    return c


class TestPointSizeScaling:
    """pointSize in GGB XML is multiplied by 2 to produce ggb_style['size_px']."""

    def test_point_A_size(self, parsed_scene):
        # <pointSize val="5"/> → size = 5 * 2 = 10
        assert parsed_scene.element('A').ggb_style['size_px'] == 10

    def test_point_D_size(self, parsed_scene):
        # <pointSize val="4"/> → size = 4 * 2 = 8
        assert parsed_scene.element('D').ggb_style['size_px'] == 8


class TestLineThicknessScaling:
    """thickness attribute in lineStyle becomes stroke_width = thickness / 2."""

    def test_segment_c_stroke_width(self, parsed_scene):
        # <lineStyle thickness="5"/> → stroke_width = 5 / 2 = 2.5
        assert parsed_scene.element('c').ggb_style['stroke_width_px'] == 2.5

    def test_angle_alpha_stroke_width(self, parsed_scene):
        # <lineStyle thickness="4"/> → stroke_width = 4 / 2 = 2
        assert parsed_scene.element('α').ggb_style['stroke_width_px'] == 2


class TestArcSizeScaling:
    """arcSize is stored as-is in pixel units (no scaling applied at parse time)."""

    def test_angle_alpha_arc_size(self, parsed_scene):
        # <arcSize val="30"/> → arc_size_px = 30
        assert parsed_scene.element('α').ggb_style['arc_size_px'] == 30


class TestLabelOffset:
    """labelOffset x,y → [x, -y] (y inverted from GGB screen coords to math)."""

    def test_point_A_offset(self, parsed_scene):
        # <labelOffset x="-28" y="32"/> → [-28, -32]
        assert parsed_scene.element('A').ggb_style['label_offset_px'] == [-28, -32]

    def test_point_C_offset(self, parsed_scene):
        # <labelOffset x="4" y="32"/> → [4, -32]
        assert parsed_scene.element('C').ggb_style['label_offset_px'] == [4, -32]

    def test_point_D_offset(self, parsed_scene):
        # <labelOffset x="7" y="30"/> → [7, -30]
        assert parsed_scene.element('D').ggb_style['label_offset_px'] == [7, -30]

    def test_point_without_label_offset_defaults(self, parsed_scene):
        # Point B has no <labelOffset> in XML → default [0, 0]
        assert parsed_scene.element('B').ggb_style['label_offset_px'] == [0, 0]


class TestObjColor:
    """objColor rgb → hex stored in stroke/fill/label_color."""

    def test_point_A_colors(self, parsed_scene):
        # <objColor r="21" g="101" b="192"/> → #1565c0
        style = parsed_scene.element('A').ggb_style
        assert style['label_color'] == '#1565c0'
        assert style['fill'] == '#1565c0'

    def test_point_D_label_color(self, parsed_scene):
        # <objColor r="110" g="109" b="115"/> → #6e6d73
        assert parsed_scene.element('D').ggb_style['label_color'] == '#6e6d73'

    def test_segment_c_stroke(self, parsed_scene):
        # Segments get stroke from objColor + stroke_opacity from lineStyle.opacity
        style = parsed_scene.element('c').ggb_style
        assert style['stroke'] == '#1565c0'
        # opacity="204" → 204 / 255
        assert style['stroke_opacity'] == pytest.approx(204 / 255)


class TestPointShape:
    """GGB pointStyle is decomposed into ggb_style['point_shape'] + fill/stroke."""

    def test_point_A_point_shape(self, parsed_scene):
        # <pointStyle val="0"/> → shape='circle', fill=color, stroke=black
        style = parsed_scene.element('A').ggb_style
        assert style['point_shape'] == 'circle'
        assert style['stroke'] == '#000000'


class TestAngleRange:
    """angleStyle 1/2 is mapped to ggb_style['angle_range'] 'minor'/'reflex'."""

    def test_angle_alpha_angle_range(self, parsed_scene):
        # <angleStyle val="1"/> → 'minor'
        assert parsed_scene.element('α').ggb_style['angle_range'] == 'minor'
