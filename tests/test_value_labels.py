"""Fast value labels: DecimalNumber-backed ``ValueLabel`` + ``resolve_label_spec``.

These cover the rendering-performance feature where a label that displays a
changing numeric value (angle measure, segment length, polygon area, …) is
drawn with a :class:`~manim.DecimalNumber` (cached digit glyphs) instead of a
fresh ``Tex`` per frame, so animating the value no longer triggers a LaTeX
recompile.
"""
import math

import numpy as np
import pytest

from animageo.geo.lib_elements import Angle, Element, Polygon, Segment
from animageo.labels import LabelSpec, resolve_label_spec, resolve_label_text


class _Scene:
    style_config = None


# ── resolve_label_spec ────────────────────────────────────────────────

class TestResolveLabelSpec:
    def test_label_only_has_no_dynamic_value(self):
        elem = Element("A", Segment(np.array([0, 0]), np.array([3, 4])))
        spec = resolve_label_spec(_Scene(), elem)
        assert isinstance(spec, LabelSpec)
        assert spec.mode == "label"
        assert spec.value is None
        assert spec.has_dynamic_value is False
        # text stays identical to resolve_label_text
        assert spec.text == resolve_label_text(_Scene(), elem) == "$A$"

    def test_segment_value_mode(self):
        elem = Element("AB", Segment(np.array([0, 0]), np.array([3, 4])))
        elem.style["label_mode"] = "value"
        spec = resolve_label_spec(_Scene(), elem)
        assert spec.mode == "value"
        assert spec.prefix_tex is None
        assert spec.value == 5.0
        assert spec.kind == "number"
        assert spec.suffix_tex is None
        assert spec.has_dynamic_value is True

    def test_segment_label_value_prefix(self):
        elem = Element("AB", Segment(np.array([0, 0]), np.array([3, 4])))
        elem.style["label_mode"] = "label_value"
        spec = resolve_label_spec(_Scene(), elem)
        assert spec.prefix_tex == "$AB = $"
        assert spec.value == 5.0
        assert spec.text == "$AB = 5$"

    def test_angle_degree_suffix_is_raised(self):
        elem = Element("a", Angle(np.array([0, 0]), np.array([1, 0]), np.array([0, 1])))
        elem.style["label_mode"] = "value"
        spec = resolve_label_spec(_Scene(), elem)
        assert spec.kind == "angle"
        assert spec.value == pytest.approx(90.0)
        assert spec.suffix_tex == r"^{\circ}"
        assert spec.suffix_raised is True

    def test_angle_radian_has_no_suffix(self):
        elem = Element("a", Angle(np.array([0, 0]), np.array([1, 0]), np.array([0, 1])))
        elem.style["label_mode"] = "value"
        elem.style["label_angle_unit"] = "radian"
        elem.style["label_value_precision"] = 3
        spec = resolve_label_spec(_Scene(), elem)
        assert spec.value == pytest.approx(math.pi / 2)
        assert spec.suffix_tex is None
        assert spec.num_decimal_places == 3

    def test_polygon_area_value(self):
        elem = Element("p", Polygon([[0, 0], [4, 0], [4, 3], [0, 3]]))
        elem.style["label_mode"] = "value"
        spec = resolve_label_spec(_Scene(), elem)
        assert spec.value == 12.0
        assert spec.has_dynamic_value is True

    def test_non_finite_value_falls_back_to_tex(self):
        # A segment of NaN length must not produce a DecimalNumber value.
        elem = Element("AB", Segment(np.array([0, 0]), np.array([np.nan, 0])))
        elem.style["label_mode"] = "value"
        spec = resolve_label_spec(_Scene(), elem)
        assert spec.has_dynamic_value is False

    def test_precision_respected(self):
        elem = Element("s", Segment(np.array([0, 0]), np.array([1, 1])))
        elem.style["label_mode"] = "value"
        elem.style["label_value_precision"] = 3
        spec = resolve_label_spec(_Scene(), elem)
        assert spec.num_decimal_places == 3


# ── ValueLabel mobject ────────────────────────────────────────────────

class TestValueLabel:
    def test_parts_present(self):
        from animageo.ui import ValueLabel

        vl = ValueLabel(value=90.0, prefix_tex=r"$\alpha = $",
                        suffix_tex=r"^{\circ}", suffix_raised=True,
                        num_decimal_places=1, font_size=40)
        assert vl.prefix is not None
        assert vl.suffix is not None
        assert vl.get_value() == pytest.approx(90.0)

    def test_value_only_has_no_prefix_suffix(self):
        from animageo.ui import ValueLabel

        vl = ValueLabel(value=5.0, num_decimal_places=1, font_size=40)
        assert vl.prefix is None
        assert vl.suffix is None

    def test_set_value_updates_display(self):
        from animageo.ui import ValueLabel

        vl = ValueLabel(value=0.0, prefix_tex=r"$x = $", num_decimal_places=1, font_size=40)
        vl.set_value(42.5)
        assert vl.get_value() == pytest.approx(42.5)

    def test_set_value_does_not_compile_new_glyphs(self):
        """The whole point: changing the value reuses cached digit glyphs and
        never compiles new LaTeX."""
        from manim.mobject.text.numbers import string_to_mob_map

        from animageo.ui import ValueLabel, prewarm_decimal_glyphs

        prewarm_decimal_glyphs()
        vl = ValueLabel(value=0.0, num_decimal_places=2, font_size=40)
        before = set(string_to_mob_map.keys())
        # Every digit, '.', '-' is already cached, so a brand-new value adds
        # nothing to the glyph map.
        for v in (7654.32, -10.09, 3.14, 88.88, 0.01):
            vl.set_value(v)
        after = set(string_to_mob_map.keys())
        assert after == before

    def test_digit_size_matches_tex(self):
        from manim import Tex

        from animageo.ui import RusTex, ValueLabel

        vl = ValueLabel(value=5, num_decimal_places=0, font_size=48)
        tx = Tex(r"$5$", tex_template=RusTex).set(font_size=48)
        assert vl.value.height == pytest.approx(tx.height, rel=1e-3)
        assert vl.value.width == pytest.approx(tx.width, rel=1e-3)


# ── Renderer integration ──────────────────────────────────────────────

class TestRendererIntegration:
    def _angle_scene(self, mode="label_value"):
        from animageo.animageo import AnimaGeoScene

        scene = AnimaGeoScene()
        scene.putCode(f"""
A = Point(0,0)
B = Point(3,0)
C = Point(0,2)
a = Angle(B, A, C)
a.style.label_visible = True
a.style.label_mode = '{mode}'
""")
        return scene

    def test_static_uses_tex(self):
        from manim import Tex

        scene = self._angle_scene()
        mob = scene.CreateMObject(scene.geo.element("a"))
        assert isinstance(mob[-1], Tex)

    def test_dynamic_uses_value_label(self):
        from animageo.ui import ValueLabel

        scene = self._angle_scene()
        scene._value_labels_dynamic = True
        mob = scene.CreateMObject(scene.geo.element("a"))
        assert isinstance(mob[-1], ValueLabel)
        assert mob[-1].get_value() == pytest.approx(90.0)

    def test_fast_switch_off_forces_tex(self):
        from manim import Tex

        scene = self._angle_scene()
        scene._value_labels_dynamic = True
        scene.style_config.rendering["fast_value_labels"] = False
        mob = scene.CreateMObject(scene.geo.element("a"))
        assert isinstance(mob[-1], Tex)

    def test_label_only_never_uses_value_label(self):
        from manim import Tex

        scene = self._angle_scene(mode="label")
        scene._value_labels_dynamic = True
        mob = scene.CreateMObject(scene.geo.element("a"))
        # No numeric value to track -> plain Tex even in dynamic mode.
        assert isinstance(mob[-1], Tex)

    def test_dynamic_context_manager_toggles_flag(self):
        scene = self._angle_scene()
        assert scene._value_labels_dynamic is False
        with scene._dynamic_value_labels():
            assert scene._value_labels_dynamic is True
        assert scene._value_labels_dynamic is False

    def test_become_tex_to_value_label_is_geometry_identical(self):
        """The first animated frame ``become``s a static Tex label into the
        ValueLabel structure; the drawn result must match a fresh ValueLabel."""
        scene = self._angle_scene()
        static = scene.CreateMObject(scene.geo.element("a"))
        scene._value_labels_dynamic = True
        fresh = scene.CreateMObject(scene.geo.element("a"))
        static.become(fresh)
        assert np.allclose(static.get_corner([-1, -1, 0]), fresh.get_corner([-1, -1, 0]))
        assert np.allclose(static.get_corner([1, 1, 0]), fresh.get_corner([1, 1, 0]))

    def test_addupdater_enables_dynamic_labels(self):
        scene = self._angle_scene()
        x = scene.addVar("x", 0)
        scene.addUpdater(x)
        assert scene._value_labels_dynamic is True
        scene.clearUpdater(x)
        assert scene._value_labels_dynamic is False
