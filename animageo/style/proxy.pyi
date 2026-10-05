"""Type stubs for StyleProxy — IDE autocomplete for ``elem.style.X``.

Declares every style key used across the codebase as a typed attribute.
The runtime class (in ``proxy.py``) is a plain ``dict`` subclass with
``__getattr__`` / ``__setattr__`` — it happily accepts any key. Stubs
exist purely to help the IDE suggest sensible property names.

Generated from analysis of:
  - ``lib_elements.py`` defaults set in each class ``__init__``
  - ``ggb_parser.py`` GGB → style mapping
  - ``label_placement.py`` runtime placement annotations
"""

from typing import Any, List


class StyleProxy(dict):
    """Dict subclass with attribute-style access. All keys optional."""

    # ── Visibility / labels (cross-type) ─────────────────────────
    visible: bool
    label_visible: bool
    label_text: str
    label_mode: str                    # 'label', 'value', 'label_value'
    label_value_precision: int
    label_value_strip_zeros: bool
    label_angle_unit: str              # 'degree' or 'radian'
    label_value_separator: str         # default ' = '
    label_color: str
    label_anchor: str                  # 'TL', 'TC', 'TR', 'ML', 'MC', ...
    label_placement_locked: bool
    _auto_placed: bool                 # internal: label layout wrote offsets

    # ── Layering ─────────────────────────────────────────────────
    z_index: float
    z_index_fill: float                # CircleSector fill layer

    # ── Label positioning ────────────────────────────────────────
    label_offset_px: List[float]       # [dx, dy] in GGB pixel units
    label_hint_px: List[float]         # [dx, dy] soft desired label centre, from the
                                       # element's anchor; read by auto-placement only
    label_radial_offset_px: float      # radial offset for angle labels

    # ── Stroke (lines / curves / boundaries) — SVG-compatible ────
    stroke: str                        # hex '#rrggbb'
    stroke_width_px: float             # line thickness, pixels
    stroke_opacity: float              # [0, 1]
    stroke_dash_ratio: float           # 0 = solid, 0 < x < 1 = dashed
    stroke_dash_period_px: float       # dash + gap, px (default rendering.dash_period_px = 10)
    stroke_linecap: str                # 'butt', 'round', 'square'
    right_angle_joint: str             # 'auto', 'bevel', 'miter', 'round'

    # ── Fill (polygons / sectors / arcs / angles) ────────────────
    fill: str                          # hex '#rrggbb'
    fill_opacity: float                # [0, 1]

    # ── Font ─────────────────────────────────────────────────────
    font_size: float                   # manim font_size units

    # ── Point-specific ───────────────────────────────────────────
    size_px: float                     # diameter in pixels
    point_shape: str                   # 'circle', 'square', 'diamond', 'triangle_up',
                                       # 'triangle_down', 'triangle_left',
                                       # 'triangle_right', 'cross', 'plus'

    # ── Angle-specific ───────────────────────────────────────────
    angle_range: str                   # 'minor' or 'reflex'
    arc_size_px: float                 # base arc radius in pixels
    arc_shift_px: float                # radial shift between concentric arcs
    right_angle_size_px: float         # right-angle marker size in pixels
    right_angle_marker: bool           # force right-angle square marker
    auto_radius: bool                  # honour overlay.angle_radius scaling

    # ── Tick marks (segments / vectors / angles) ─────────────────
    tick_count: int                    # number of ticks/concentric arcs
    tick_style: str                    # 'line' or 'wave'
    tick_radius_px: float              # wave rounding radius, pixels
    tick_length_px: float              # tick mark length, pixels
    tick_width_px: float               # tick mark stroke width, pixels
    tick_shift_px: float               # spacing between multiple ticks, pixels

    # ── Arrow heads ───────────────────────────────────────────────
    arrow_length_px: float             # vector arrow head length, pixels
    arrow_width_px: float              # vector arrow head width, pixels

    # ── Dict API — inherited from dict ───────────────────────────
    # __getitem__, __setitem__, __contains__, get, update, keys,
    # values, items, __len__, __iter__, __eq__, etc.
    # All work normally via dict.
    def __getattr__(self, name: str) -> Any: ...
    def __setattr__(self, name: str, value: Any) -> None: ...
    def __delattr__(self, name: str) -> None: ...
