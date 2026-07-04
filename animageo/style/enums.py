"""Style vocabularies for AnimaGeo.

Finite sets of string values that appear in ``elem.style`` and in the user
JSON style schema. Kept as ``Literal`` aliases plus a matching runtime tuple
so both static checkers and parsers can validate.

The GGB ``pointStyle`` → elem.style decomposition table also lives here:
a single source of truth for how the eleven GGB presets split into the three
orthogonal axes (shape, fill, stroke) on the animageo side.
"""

from __future__ import annotations

from typing import Literal


PointShape = Literal[
    "circle",
    "square",
    "triangle_up",
    "triangle_down",
    "triangle_left",
    "triangle_right",
    "cross",
    "plus",
]
POINT_SHAPES: tuple[str, ...] = (
    "circle",
    "square",
    "triangle_up",
    "triangle_down",
    "triangle_left",
    "triangle_right",
    "cross",
    "plus",
)

AngleRange = Literal["minor", "reflex"]
ANGLE_RANGES: tuple[str, ...] = ("minor", "reflex")

TickStyle = Literal["line", "wave"]
TICK_STYLES: tuple[str, ...] = ("line", "wave")

PointDisplay = Literal["auto", "only_labels", "only_points"]
POINT_DISPLAYS: tuple[str, ...] = ("auto", "only_labels", "only_points")

LineCap = Literal["butt", "round", "square"]
LINE_CAPS: tuple[str, ...] = ("butt", "round", "square")

RightAngleJoint = Literal["auto", "bevel", "miter", "round"]
RIGHT_ANGLE_JOINTS: tuple[str, ...] = ("auto", "bevel", "miter", "round")

LabelAnchor = Literal[
    "TL", "TC", "TR",
    "ML", "MC", "MR",
    "BL", "BC", "BR",
]
LABEL_ANCHORS: tuple[str, ...] = (
    "TL", "TC", "TR",
    "ML", "MC", "MR",
    "BL", "BC", "BR",
)

Interpolation = Literal["linear", "smooth"]
INTERPOLATIONS: tuple[str, ...] = ("linear", "smooth")


# GGB pointStyle code → decomposition into independent (shape, fill, stroke) axes.
#
# Each entry yields a dict patch that the parser merges into ``elem.style``.
# Values marked ``<color>`` are placeholders filled in by the caller with the
# element's GGB ``objColor`` hex.
#
# Sources: observed GGB behaviour and current point-shape renderer snapshots.
_GGB_POINT_STYLE_PATCHES: dict[int, dict[str, object]] = {
    # 0: filled disc with black outline (GGB default)
    0: {
        "point_shape": "circle",
        "fill": "<color>",
        "fill_opacity": 1.0,
        "stroke": "#000000",
        "stroke_width_px": 1.0,
        "stroke_opacity": 1.0,
    },
    # 2: open circle (outline only, no fill)
    2: {
        "point_shape": "circle",
        "fill_opacity": 0.0,
        "stroke": "<color>",
        "stroke_width_px": 2.0,
        "stroke_opacity": 1.0,
    },
    # 10: filled disc, no outline
    10: {
        "point_shape": "circle",
        "fill": "<color>",
        "fill_opacity": 1.0,
        "stroke_opacity": 0.0,
    },
    # 4: filled square, no outline
    4: {
        "point_shape": "square",
        "fill": "<color>",
        "fill_opacity": 1.0,
        "stroke_opacity": 0.0,
    },
    # 5: open square (outline only)
    5: {
        "point_shape": "square",
        "fill_opacity": 0.0,
        "stroke": "<color>",
        "stroke_width_px": 2.0,
        "stroke_opacity": 1.0,
    },
    # 1: diagonal cross (×) — line geometry, no fill
    1: {
        "point_shape": "cross",
        "fill_opacity": 0.0,
        "stroke": "<color>",
        "stroke_width_px": 2.0,
        "stroke_opacity": 1.0,
    },
    # 3: plus (+) — line geometry, no fill
    3: {
        "point_shape": "plus",
        "fill_opacity": 0.0,
        "stroke": "<color>",
        "stroke_width_px": 2.0,
        "stroke_opacity": 1.0,
    },
    # 6–9: filled triangles (up/down/right/left), no outline
    6: {
        "point_shape": "triangle_up",
        "fill": "<color>",
        "fill_opacity": 1.0,
        "stroke_opacity": 0.0,
    },
    7: {
        "point_shape": "triangle_down",
        "fill": "<color>",
        "fill_opacity": 1.0,
        "stroke_opacity": 0.0,
    },
    8: {
        "point_shape": "triangle_right",
        "fill": "<color>",
        "fill_opacity": 1.0,
        "stroke_opacity": 0.0,
    },
    9: {
        "point_shape": "triangle_left",
        "fill": "<color>",
        "fill_opacity": 1.0,
        "stroke_opacity": 0.0,
    },
}


def ggb_point_style_to_elem_style(ggb_code: int, color_hex: str) -> dict[str, object]:
    """Decompose a GGB ``pointStyle`` code into an ``elem.style`` patch.

    ``ggb_code`` is the integer read from ``<pointStyle val="N"/>``; ``color_hex``
    is the element's ``objColor`` (``"#rrggbb"``). Returns a dict of elem.style
    keys to merge. Unknown codes fall back to preset 0 (filled disc).
    """
    patch = _GGB_POINT_STYLE_PATCHES.get(ggb_code, _GGB_POINT_STYLE_PATCHES[0])
    return {k: (color_hex if v == "<color>" else v) for k, v in patch.items()}
