import numpy as np

from animageo.geo.lib_elements import Angle, Element, Polygon, Segment
from animageo.labels import (
    geogebra_label_mode_to_style,
    resolve_label_text,
)
from animageo.style.ggb_resolver import resolve_ggb_style
from animageo.style.config import StyleConfig


class _Scene:
    style_config = None


def test_default_label_mode_preserves_existing_label_text_fallback():
    elem = Element("AB", Segment(np.array([0, 0]), np.array([3, 4])))
    assert resolve_label_text(_Scene(), elem) == "$AB$"


def test_segment_value_label_modes():
    elem = Element("AB", Segment(np.array([0, 0]), np.array([3, 4])))

    elem.style["label_mode"] = "value"
    assert resolve_label_text(_Scene(), elem) == "$5$"

    elem.style["label_mode"] = "label_value"
    assert resolve_label_text(_Scene(), elem) == "$AB = 5$"


def test_label_value_uses_custom_label_text():
    elem = Element("s", Segment(np.array([0, 0]), np.array([3, 4])))
    elem.style["label_text"] = "$d$"
    elem.style["label_mode"] = "label_value"

    assert resolve_label_text(_Scene(), elem) == "$d = 5$"


def test_label_value_precision_can_be_configured_per_element():
    elem = Element("s", Segment(np.array([0, 0]), np.array([1, 1])))
    elem.style["label_mode"] = "value"
    elem.style["label_value_precision"] = 3

    assert resolve_label_text(_Scene(), elem) == "$1.414$"


def test_label_value_precision_defaults_to_one_decimal():
    elem = Element("s", Segment(np.array([0, 0]), np.array([1, 1])))
    elem.style["label_mode"] = "value"

    assert resolve_label_text(_Scene(), elem) == "$1.4$"


def test_label_value_precision_can_be_configured_from_style_rendering():
    class Scene:
        style_config = StyleConfig.load({
            "rendering": {
                "label_value_precision": 3,
            },
        })

    elem = Element("s", Segment(np.array([0, 0]), np.array([1, 1])))
    elem.style["label_mode"] = "value"

    assert resolve_label_text(Scene(), elem) == "$1.414$"


def test_angle_value_is_degrees_by_default():
    elem = Element("alpha", Angle(np.array([0, 0]), np.array([1, 0]), np.array([0, 1])))
    elem.style["label_mode"] = "value"

    assert resolve_label_text(_Scene(), elem) == r"$90^{\circ}$"


def test_angle_value_matches_visible_minor_or_reflex_range():
    elem = Element("alpha", Angle(np.array([0, 0]), np.array([1, 0]), np.array([0, -1])))
    elem.style["label_mode"] = "value"

    assert resolve_label_text(_Scene(), elem) == r"$90^{\circ}$"

    elem.style["angle_range"] = "reflex"
    assert resolve_label_text(_Scene(), elem) == r"$270^{\circ}$"


def test_polygon_value_is_area():
    elem = Element("p", Polygon([[0, 0], [4, 0], [4, 3], [0, 3]]))
    elem.style["label_mode"] = "value"

    assert elem.value() == 12
    assert resolve_label_text(_Scene(), elem) == "$12$"


def test_geogebra_label_mode_mapping():
    assert geogebra_label_mode_to_style(0) == "label"
    assert geogebra_label_mode_to_style(1) == "label_value"
    assert geogebra_label_mode_to_style(2) == "value"
    assert geogebra_label_mode_to_style(3) == "label"
    assert geogebra_label_mode_to_style(9) == "label_value"


def test_resolve_ggb_style_mirrors_caption_label_modes():
    assert resolve_ggb_style({"label_mode": 0, "label_caption": "custom"}) == {
        "label_mode": "label",
        "label_offset_px": [0, 0],
    }
    assert resolve_ggb_style({"label_mode": 9, "label_caption": "custom"}) == {
        "label_mode": "label_value",
        "label_text": "$custom$",
        "label_offset_px": [0, 0],
    }
