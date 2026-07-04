"""P1-C (rendering half): contrast-aware label colour. A dark label that would
sit on a dense dark fill is recoloured to a readable black/white. Needs manim.
"""
import numpy as np
import pytest
from manim import ManimColor

from animageo.animageo import AnimaGeoScene


def _dark_triangle_scene(mode='auto'):
    sc = AnimaGeoScene()
    sc.style.export.update({
        'ptUnit': 50, 'ptWidth': 600, 'ptHeight': 400,
        'ptXZero': 300, 'ptYZero': 200, 'ptUnit_ggb': 50,
    })
    sc.putCode("A = Point(-2,-1)\nB = Point(2,-1)\nC = Point(0,2)\n"
               "t = Polygon(A, B, C)\nP = Point(0, 0.2)\n")
    sc.applyStyle(style={'rendering': {'label_contrast': mode},
                         'overlay': {'label_placement': {'enabled': True}}})
    t = sc.element('t')
    t.style['fill'] = '#101010'      # near-black, dense
    t.style['fill_opacity'] = 1.0
    return sc


class TestContrastMode:
    def test_default_off(self):
        sc = AnimaGeoScene()
        sc.applyStyle(style={})
        assert sc._label_contrast_mode() == 'off'

    def test_auto_from_config(self):
        sc = _dark_triangle_scene('auto')
        assert sc._label_contrast_mode() == 'auto'
        assert sc._label_contrast_threshold() == pytest.approx(0.35)


class TestBackgroundLuminance:
    def test_inside_dark_fill_is_dark(self):
        sc = _dark_triangle_scene()
        assert sc._label_background_luminance([0.0, 0.2]) < 0.2

    def test_outside_is_canvas_white(self):
        sc = _dark_triangle_scene()
        assert sc._label_background_luminance([5.0, 5.0]) == pytest.approx(1.0)


class TestContrastAdjustedColour:
    def test_dark_label_on_dark_fill_becomes_white(self):
        sc = _dark_triangle_scene()
        out = sc._contrast_adjusted_label_color(ManimColor('#202020'), [0.0, 0.2])
        assert out.to_hex().upper() == '#FFFFFF'

    def test_dark_label_on_white_kept(self):
        sc = _dark_triangle_scene()
        col = ManimColor('#202020')
        out = sc._contrast_adjusted_label_color(col, [5.0, 5.0])
        assert ManimColor(out).to_hex() == col.to_hex()

    def test_light_label_on_white_becomes_black(self):
        sc = _dark_triangle_scene()
        # a near-white label on the white canvas has poor contrast → switch black
        out = sc._contrast_adjusted_label_color(ManimColor('#f0f0f0'), [5.0, 5.0])
        assert out.to_hex().upper() == '#000000'


class TestLabelCenter:
    def test_offset_applied(self):
        sc = _dark_triangle_scene()
        from types import SimpleNamespace
        ctx = SimpleNamespace(label_offset_px=[50.0, 0.0],
                              ptUnit_ggb=50, ptUnit_style=50)
        c = sc._label_center_2d(np.array([0.0, 0.0, 0.0]), ctx)
        assert c[0] == pytest.approx(1.0)  # 50px / 50 ptUnit_ggb = 1.0 MU
        assert c[1] == pytest.approx(0.0)


def test_make_label_runs_in_auto_mode():
    sc = _dark_triangle_scene('auto')
    sc.element('P').style['label_visible'] = True
    mobj = sc.CreateMObject(sc.element('P'), z_auto=True)
    assert mobj is not None
