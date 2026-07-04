import json

import numpy as np
import pytest

import animageo.animageo as animageo_module
from animageo.animageo import AnimaGeoScene
from animageo.constants import STROKE_WIDTH_SCALE
from animageo.geo.lib_elements import Angle as GeoAngle
from animageo.geo.lib_elements import Element
from animageo.geo.lib_elements import Point
from animageo.style.config import StyleConfig


def _source_scene():
    scene = AnimaGeoScene()
    scene.style.export.update({
        'ptUnit': 50,
        'ptWidth': 300,
        'ptHeight': 150,
        'ptXZero': 150,
        'ptYZero': 75,
        'ptUnit_ggb': 50,
    })
    return scene


def test_export_size_keeps_separate_style_scale():
    scene = _source_scene()
    scene.applyStyle(export={'size': [1200, 600]})

    assert scene.style.export['ptUnit'] == pytest.approx(200)
    assert scene.style.export['ptUnit_style'] == pytest.approx(50)
    assert scene.style.export['contentScale'] == pytest.approx(4)


def test_visual_px_values_resolve_against_reference_scale():
    scene = _source_scene()
    scene.applyStyle(export={'size': [1200, 600]})
    scene.putCode("A = Point(0, 0)\n")
    elem = scene.element('A')
    elem.style['stroke_width_px'] = 2
    elem.style['font_size_px'] = 20
    elem.style['size_px'] = 10

    ctx = scene._build_render_ctx(elem, z_auto=True)

    assert ctx.ptUnit == pytest.approx(200)
    assert ctx.ptUnit_style == pytest.approx(50)
    assert ctx.lw == pytest.approx(2 * STROKE_WIDTH_SCALE / 50)
    assert ctx.font_size == pytest.approx(20 * 100 / 50)


def test_default_export_uses_source_view_as_reference():
    scene = _source_scene()
    scene.applyStyle()

    assert scene.style.export['referenceWidth'] == pytest.approx(300)
    assert scene.style.export['referenceHeight'] == pytest.approx(150)
    assert scene.style.export['ptUnit_style'] == pytest.approx(50)
    assert scene.style.export['ptUnit'] == pytest.approx(50)


def test_style_reference_is_used_when_runtime_reference_omitted(tmp_path):
    style_path = tmp_path / 'style.json'
    style_path.write_text(json.dumps({
        'reference': {
            'size': {'width': 300, 'height': 150},
            'source': 'manual',
        },
    }))

    scene = _source_scene()
    scene.style.export['ptWidth'] = 600
    scene.style.export['ptHeight'] = 300
    scene.applyStyle(style=str(style_path), export={'size': [1200, 600]})

    assert scene.style.export['referenceWidth'] == pytest.approx(300)
    assert scene.style.export['referenceHeight'] == pytest.approx(150)
    assert scene.style.export['contentScale'] == pytest.approx(4)

    cfg = StyleConfig.load(str(style_path))
    assert cfg.reference['size']['width'] == 300


def test_rendered_bounds_source_rect_uses_final_mobject_bounds(monkeypatch):
    scene = _source_scene()
    scene.geo.add(Element('A', Point(np.array([0, 0]))))
    scene.geo.add(Element('B', Point(np.array([2, 1]))))

    class FakeBoundsMobject:
        def __init__(self, left, bottom, right, top):
            self._left = left
            self._bottom = bottom
            self._right = right
            self._top = top

        def get_left(self):
            return np.array([self._left, 0, 0])

        def get_bottom(self):
            return np.array([0, self._bottom, 0])

        def get_right(self):
            return np.array([self._right, 0, 0])

        def get_top(self):
            return np.array([0, self._top, 0])

    def fake_create_mobject(elem, z_auto=False, debug=False):
        return {
            'A': FakeBoundsMobject(0, -1, 1, 0),
            'B': FakeBoundsMobject(1, 0, 2, 1),
        }[elem.name]

    monkeypatch.setattr(scene, 'CreateMObject', fake_create_mobject)

    scene.applyStyle(
        content={'source': 'rendered_bounds', 'padding': 10},
        export={'size': [240, 240]},
    )

    export = scene.style.export
    # rendered_bounds now crops TIGHT to the mobject bounds (100×100 px); the
    # content.padding=10 is no longer a source-crop expansion but a uniform
    # canvas-edge margin applied at the reference→export stage. So the reference
    # stays 100×100 and the content is fit into (240 − 2·10) and inset by 10px.
    assert export['source_rect'] == 'rendered_bounds'
    assert export['referenceWidth'] == pytest.approx(100)
    assert export['referenceHeight'] == pytest.approx(100)
    assert export['contentScale'] == pytest.approx(2.2)
    assert export['ptUnit_style'] == pytest.approx(50)
    assert export['ptUnit'] == pytest.approx(110)
    assert export['ptXZero'] == pytest.approx(10)
    assert export['ptYZero'] == pytest.approx(120)
    # source rect shifts in by the 10px canvas margin too (was 140/15 when
    # padding expanded the crop; now +10 for the uniform edge margin).
    assert export['sourceLeftPx'] == pytest.approx(150)
    assert export['sourceTopPx'] == pytest.approx(25)


def test_rendered_bounds_anchor_places_measured_rect(monkeypatch):
    class FakeBoundsMobject:
        def get_left(self):
            return np.array([0, 0, 0])

        def get_bottom(self):
            return np.array([0, -1, 0])

        def get_right(self):
            return np.array([2, 0, 0])

        def get_top(self):
            return np.array([0, 1, 0])

    def make_scene():
        scene = _source_scene()
        scene.geo.add(Element('A', Point(np.array([0, 0]))))
        monkeypatch.setattr(scene, 'CreateMObject', lambda *args, **kwargs: FakeBoundsMobject())
        return scene

    scene = make_scene()
    scene.applyStyle(
        content={'source': 'rendered_bounds'},
        export={'size': [300, 300], 'anchor': 'right'},
    )

    export = scene.style.export
    assert export['referenceWidth'] == pytest.approx(100)
    assert export['referenceHeight'] == pytest.approx(100)
    assert export['contentScale'] == pytest.approx(3)
    assert export['contentOffsetX'] == pytest.approx(0)

    scene = make_scene()
    scene.applyStyle(
        content={'source': 'rendered_bounds'},
        export={'size': [360, 300], 'anchor': 'right'},
    )

    export = scene.style.export
    assert export['contentScale'] == pytest.approx(3)
    assert export['referenceOffsetX'] == pytest.approx(60)
    assert export['ptXZero'] == pytest.approx(60)


def test_angle_label_radius_uses_reference_scale_once(monkeypatch):
    scene = _source_scene()
    scene.applyStyle(export={'size': [1200, 600]})

    elem = Element(
        'alpha',
        GeoAngle(
            np.array([0, 0]),
            np.array([10, 0]),
            np.array([0, 10]),
        ),
    )
    elem.style['label_visible'] = True
    elem.style['label_text'] = r'\alpha'
    elem.style['arc_size_px'] = 50
    elem.style['label_radial_offset_px'] = 10
    elem.style['tick_count'] = 1
    elem.style['auto_radius'] = False
    elem.style['right_angle_marker'] = False

    class FakeMobject:
        def set_z_index(self, *args, **kwargs):
            return self

        def rotate(self, *args, **kwargs):
            return self

        def shift(self, *args, **kwargs):
            return self

    class FakeLine(FakeMobject):
        def __init__(self, *args, **kwargs):
            pass

    class FakeAnnularSector(FakeMobject):
        def __init__(self, *args, **kwargs):
            pass

    class FakeAngle(FakeMobject):
        def __init__(self, *args, radius=None, **kwargs):
            self.radius = radius

        def point_from_proportion(self, proportion):
            return [self.radius, proportion, 0]

    class FakeVGroup(FakeMobject):
        def __init__(self, *args, **kwargs):
            self.items = args

    captured = {}

    def fake_make_label(elem, pos, ctx):
        captured['pos'] = pos
        return FakeMobject()

    monkeypatch.setattr(animageo_module, 'Line', FakeLine)
    monkeypatch.setattr(animageo_module, 'AnnularSector', FakeAnnularSector)
    monkeypatch.setattr(animageo_module, 'Angle', FakeAngle)
    monkeypatch.setattr(animageo_module, 'VGroup', FakeVGroup)
    monkeypatch.setattr(scene, '_make_label', fake_make_label)

    ctx = scene._build_render_ctx(elem, z_auto=True)
    scene._render_angle(elem, ctx)

    assert captured['pos'][0] == pytest.approx((50 + 10) / 50)

def test_runtime_reference_size_accepts_list_form():
    """reference={'size': [w, h]} must behave the same as the dict form.

    Regression: _reference_size_from_config used to accept only the dict
    shape and silently ignored the documented [w, h] list form, so
    ptUnit_style fell back to the source view scale.
    """
    scene_list = _source_scene()
    scene_list.applyStyle(reference={'size': [300, 150]},
                          export={'size': [1200, 600]})
    scene_dict = _source_scene()
    scene_dict.applyStyle(reference={'size': {'width': 300, 'height': 150}},
                          export={'size': [1200, 600]})

    for key in ('referenceWidth', 'referenceHeight', 'ptUnit', 'ptUnit_style'):
        assert scene_list.style.export[key] == pytest.approx(
            scene_dict.style.export[key]), key


class TestFitView:
    """scene.fitView() — canonical framing for DSL-built scenes."""

    CODE = (
        "A = Point(0, 0)\n"
        "B = Point(6, 0)\n"
        "C = Point(2, 4)\n"
        "tri, AB, BC, CA = Polygon(A, B, C)\n"
    )

    def _dsl_scene(self):
        scene = AnimaGeoScene()
        scene.putCode(self.CODE)
        return scene

    def test_matches_manual_double_pass(self):
        manual = self._dsl_scene()
        kw = dict(reference={'size': {'width': 800, 'height': 600}},
                  content={'source': 'rendered_bounds', 'padding': 30},
                  export={'size': {'width': 800, 'height': 600}})
        manual.applyStyle(**kw); manual.updateAllGeometry()
        manual.applyStyle(**kw); manual.updateAllGeometry()

        fitted = self._dsl_scene()
        fitted.fitView(800, 600, padding=30)

        for key in ('ptUnit', 'ptUnit_style', 'ptXZero', 'ptYZero',
                    'ptWidth', 'ptHeight'):
            assert fitted.style.export[key] == pytest.approx(
                manual.style.export[key]), key

    def test_scale_is_not_degenerate(self):
        scene = self._dsl_scene()
        scene.fitView(800, 600, padding=30)
        export = scene.style.export
        # A 6x4 MU triangle on an 800x600 canvas: tens of px per MU, and the
        # style scale matches the geometry scale up to the padding ratio.
        assert export['ptUnit'] > 30
        assert export['ptUnit'] <= export['ptUnit_style'] <= export['ptUnit'] * 1.3

    def test_preserves_current_style_config(self):
        scene = self._dsl_scene()
        scene.applyStyle(style={'presets': {'color': {'main': '#123456'}}})
        scene.fitView(800, 600)
        assert scene.style_config.presets['color']['main'] == '#123456'

    def test_style_argument_is_forwarded(self):
        scene = self._dsl_scene()
        scene.fitView(800, 600, style={'presets': {'color': {'main': '#654321'}}})
        assert scene.style_config.presets['color']['main'] == '#654321'

    def test_rejects_non_positive_passes(self):
        scene = self._dsl_scene()
        with pytest.raises(ValueError):
            scene.fitView(800, 600, passes=0)
