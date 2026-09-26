"""Style schema documentation and validation for AnimaGeo JSON style files.

Five top-level sections, each with a single responsibility:

- ``presets``   — semantic constants (colours, sizes, widths, structured tokens).
- ``defaults``  — per-element-type baseline, usually referencing ``presets``.
- ``reference`` — optional authoring reference metadata for previews/exports.
- ``rendering`` — pipeline/renderer settings (line caps, background).
- ``import``    — how to translate GGB XML values into ``elem.style``, including
                  the embedded :class:`ImportPolicy` directive block.

Runtime layout options live in the API-level ``content`` and ``export`` blocks,
not in style JSON. Top-level ``reference`` may describe the style-authoring
canvas, but physical export placement belongs to the caller.

JSON Style File Structure
=========================

{
    "name":    "style_name",
    "version": 0.1,

    "presets": {
        "color": {
            "main": "#hex", "bold": "#hex", "aux": "#hex",
            "background": "#hex", "strong": "#hex"
        },
        "point_size":   { "main": <float>, "bold": <float>, "aux": <float> },
        "line_width":   { "main": <float>, "bold": <float>, "aux": <float> },
        "angle_radius": { "main": <float>, "shift": <float>, "right": <float> },
        "tick": {
            "main": { "tick_length_px": <float>,
                      "tick_width_px":  <float>,
                      "tick_shift_px":  <float> }
        },
        "arrow": {
            "main": { "arrow_length_px": <float>,
                      "arrow_width_px":  <float> }
        },
        "font_size": { "main": <float>, "bold": <float>, "aux": <float> }
    },

    "defaults": {
        "point": {
            "size_px":      "point_size.main",
            "fill":         "color.strong",
            "font_size_px": "font_size.main"
        },
        "segment": {
            "$include":        "tick.main",
            "stroke_width_px": "line_width.main"
        },
        "vector": {
            "$include": ["tick.main", "arrow.main"]
        }
    },

    "overlay": {
        "per_type": {
            "<type>": { "<key>": <value> }
        },
        "per_name": {
            "<name>": { "<key>": <value> }
        },

        "angle_radius": { "enabled":          <bool>,
                          "exp":              <float>,
                          "pivot_rad":        <float>,
                          "min_px":           <float>,
                          "max_arm_fraction": <float>,
                          "apply_to_right":   <bool> },

        "label_placement": { "enabled":           <bool>,
                             "distance_px":       <int>,
                             "padding_px":        <int>,
                             "point_gap_px":      <float>,
                             "geom_gap_px":       <float>,
                             "angle_gap_arc_px":  <int>,
                             "angle_gap_sides_px":<int>,
                             "w_anchor":          <float>,
                             "w_label":           <float>,
                             "w_geom":            <float>,
                             "position_priority": null|"classic"|"perceptual"|"geogebra",
                             "w_pref":               <float>,
                             "soft_falloff_px":      <float>,
                             "w_soft":               <float>,
                             "repair_iterations":    <int>,
                             "consistent_placement": <bool>,
                             "cluster_consistency":  <bool>,
                             "compact_labels":       <bool>,
                             "compact_gap_px":       <float>,
                             "compact_max_push_px":  <float>,
                             "overlap_tol_px":       <float>,
                             "label_overflow":       <"overplot"|"leader">,
                             "leader_max_push_px":   <float>,
                             "leader_coincident_px": <float>,
                             "leader_min_clearance_px": <float>,
                             "leader_points_only":   <bool>,
                             "w_fill":               <float>,
                             "w_assoc":              <float>,
                             "dashed_overlap_factor": <float>,
                             "continuous_placement": <bool>,
                             "continuous_steps":     <int>,
                             "direction_tolerance":  <float|null>,
                             "angle_label_max_arm_fraction": <float|null>,
                             "point_bisector":       <bool>,
                             "respect_current_position": <bool>,
                             "keep_current_if_free": <bool>,
                             "w_inertia":            <float>,
                             "respect_min_offset_px": <float>,
                             "directional_placement": <bool>,
                             "directional_cap_px":   <float>,
                             "viewport_clamp":       <bool>,
                             "declutter_labels":     <bool>,
                             "label_gap_px":         <float>,
                             "dynamic_angles":       <bool>,
                             "keyframe_snapshots":   <bool>,
                             "canonicalize_anchor":  <bool>,
                             "interpolation":        "linear"|"smooth",
                             "ema_alpha":            <float>,
                             "anchor_flip_frames":   <int>,
                             "solver_every_n_frames":<int> }
    },

    "reference": {
        "size": {
            "width":  <float|"auto">,
            "height": <float|"auto">
        },
        "source": "manual"|"source_view"|"ggb_view"
    },

    "rendering": {
        "line_cap":               "butt"|"round"|"square",
        "dash_period_px":         <float>,        # default 10: dash + gap, px
        "background":             "color.background",
        "right_angle_joint":      "auto"|"bevel"|"miter"|"round",
        "polygon_boundary_layer": "top"|null,
        "points_display":         "auto"|"only_labels"|"only_points",
        "label_anchor":           "TL"|"TC"|"TR"|"ML"|"MC"|"MR"|"BL"|"BC"|"BR",
        "label_value_precision":  <int>,
        "fast_value_labels":      <bool>,         # default true
        "label_contrast":         "off"|"auto",   # default off (P1-C: recolour
                                                  # labels on low-contrast fills)
        "label_contrast_threshold": <float>       # default 0.35 luminance gap
    },

# rendering.fast_value_labels (default true): during animation, labels that show
# a numeric value (mode "value"/"label_value": angle measure, segment length,
# polygon area, …) are drawn with a manim DecimalNumber (cached digit glyphs)
# instead of recompiling a Tex every frame — ~80x faster per label. Static
# export keeps the Tex path (trailing-zero stripping). Set false to force Tex
# everywhere (fixed-decimal vs stripped output, slower on animated values).

    "import": {
        "enabled":    <bool>,
        "colors":     { "#hex [opacity]": "color.name|#hex [opacity]" },
        "point_size": { "N": "point_size.name" },
        "line_width": { "N": "line_width.name" },
        "policy": {
            "preset":          "faithful"|"style_only",
            "size_px":         <scalar|DSL-string>,
            "stroke_width_px": <scalar|DSL-string>,
            "arc_size_px":     <scalar|DSL-string>,
            "label_offset_px": <scalar|DSL-string>,
            "label_color":     <"#hex"|DSL-string>,
            "label_visible":   <bool|DSL-string>,
            "visible":         <bool|DSL-string>,
            "label_text":      <str|DSL-string>,
            "label_mode":      "label"|"value"|"label_value"|DSL-string,
            "label_value_precision": <int|DSL-string>,
            "label_value_strip_zeros": <bool|DSL-string>,
            "label_angle_unit": "degree"|"radian"|DSL-string,
            "label_value_separator": <str|DSL-string>,
            "angle_range":     "minor"|"reflex"|DSL-string,
            "tick_count":      <int|DSL-string>,
            "font_size_px":    <scalar|DSL-string>,
            "stroke":          <"#hex"|DSL-string>,
            "fill":            <"#hex"|DSL-string>,
            "fill_opacity":    <float|DSL-string>,
            "point_shape":     <str|DSL-string>,
            "stroke_opacity":  <float|DSL-string>,
            "stroke_dash_ratio": <float|DSL-string>,
            "stroke_dash_period_px": <float|DSL-string>,
            "stroke_linecap":  <str|DSL-string>
        }
    }
}


Units
=====
All visual ``*_px`` values in ``presets``, ``defaults``, ``overlay`` and
``elem.style`` are pixels. The renderer divides visual style sizes by
``ptUnit_style`` so the authored reference-canvas style scales together with
the final export.

Per-element ``elem.style`` keys (set by parser or user code)
============================================================
See ``animageo/style/proxy.pyi`` for the canonical typed list. Summary:

Visibility / labels
- ``visible``, ``label_visible``, ``label_text``, ``label_mode``,
  ``label_value_precision``, ``label_value_strip_zeros``,
  ``label_angle_unit``, ``label_value_separator``, ``label_color``,
  ``label_anchor``, ``label_placement_locked``

Stroke (SVG-compatible)
- ``stroke``, ``stroke_width_px``, ``stroke_opacity``,
  ``stroke_dash_ratio``, ``stroke_dash_period_px``, ``stroke_linecap``

Dashes: ``stroke_dash_ratio`` is the dash's share of one period (``None``/``0``
or ``>= 1`` = solid); ``stroke_dash_period_px`` is dash + gap in style pixels
(same unit as ``stroke_width_px``; falls back to ``rendering.dash_period_px``,
default 10). A 0.65 ratio at 10 px draws 6.5 px dashes and 3.5 px gaps. The
dashed stroke stays one path (SVG ``stroke-dasharray``).

Fill
- ``fill``, ``fill_opacity``

Points
- ``size_px`` (diameter, pixels)
- ``point_shape`` ("circle"|"square"|"diamond"|"triangle_up"|"triangle_down"|
                   "triangle_left"|"triangle_right"|"cross"|"plus")

Angles
- ``angle_range`` ("minor"|"reflex")
- ``arc_size_px`` (base arc radius, pixels)
- ``arc_shift_px`` (radial shift between concentric arcs)
- ``right_angle_size_px`` (right-angle marker size, pixels)
- ``right_angle_marker`` (bool)
- ``auto_radius`` (bool, opt-out from overlay.angle_radius)

Tick decorations (segments/vectors/angles)
- ``tick_count`` (int), ``tick_style`` ("line"|"wave"), ``tick_radius_px``
- ``tick_length_px``, ``tick_width_px``, ``tick_shift_px`` (pixels)

Arrow heads
- ``arrow_length_px``, ``arrow_width_px`` (pixels)

Positioning / layering
- ``label_offset_px`` ([dx, dy], GGB pixels)
- ``label_radial_offset_px`` (radial label offset for angles, pixels)
- ``font_size_px`` (pixel-invariant label font size)
- ``z_index``, ``z_index_fill`` (CircleSector)
"""

from __future__ import annotations


NEW_TOP_KEYS = frozenset({'presets', 'defaults', 'reference', 'rendering', 'import', 'overlay'})
REMOVED_TOP_KEYS = frozenset({'style', 'technic', 'ggb_export', 'palette'})
AUTOMATION_RENDERING_KEYS = frozenset({'angle_radius', 'label_placement'})
REMOVED_RENDERING_KEYS = frozenset({'scale_export'})
REMOVED_STYLE_KEYS = frozenset({
    'line_width',
    'ang_width',
    'ang_rdefault',
    'ang_rshift',
    'ang_right',
    'strich_len',
    'strich_width',
    'strich_rshift',
    'strich_shift',
    'arrow_height',
    'label_r_offset',
    'font_size',
})
REMOVED_LABEL_PLACEMENT_KEYS = frozenset({'angle_gap_px'})
IMPORT_POLICY_KEYS = frozenset({
    'preset',
    'base',
    'size_px',
    'stroke_width_px',
    'arc_size_px',
    'label_offset_px',
    'label_color',
    'label_visible',
    'visible',
    'label_text',
    'label_mode',
    'label_value_precision',
    'label_value_strip_zeros',
    'label_angle_unit',
    'label_value_separator',
    'angle_range',
    'tick_count',
    'font_size_px',
    'stroke',
    'fill',
    'fill_opacity',
    'point_shape',
    'stroke_opacity',
    'stroke_dash_ratio',
    'stroke_dash_period_px',
    'stroke_linecap',
})


class RemovedStyleSchemaError(ValueError):
    """Raised when a style JSON uses a removed schema.

    Removed schemas are not accepted by the runtime loader. Style JSON must be
    authored directly in the canonical schema.
    """


class StyleSchemaError(ValueError):
    """Raised when a style JSON violates the canonical schema."""


def _detect_removed_schema(style_json: dict, file_hint: str | None = None) -> None:
    removed = REMOVED_TOP_KEYS & style_json.keys()
    if not removed:
        return
    where = f" in {file_hint!r}" if file_hint else ""
    keys = ', '.join(sorted(removed))
    raise RemovedStyleSchemaError(
        f"Removed style schema detected{where}: top-level key(s) {{{keys}}} "
        f"belong to a removed format and are not accepted. "
        f"Use the canonical top-level sections: presets, defaults, import, "
        f"overlay, rendering."
    )


def _error(message: str, file_hint: str | None = None) -> None:
    where = f" in {file_hint!r}" if file_hint else ""
    raise StyleSchemaError(f"{message}{where}")


def _validate_rendering(style_json: dict, file_hint: str | None = None) -> None:
    rendering = style_json.get('rendering', {})
    if not isinstance(rendering, dict):
        return
    misplaced = AUTOMATION_RENDERING_KEYS & rendering.keys()
    if misplaced:
        keys = ', '.join(f"rendering.{k}" for k in sorted(misplaced))
        _error(
            f"Automation setting(s) {keys} are not canonical; use "
            "overlay.angle_radius / overlay.label_placement",
            file_hint,
        )
    removed = REMOVED_RENDERING_KEYS & rendering.keys()
    if removed:
        keys = ', '.join(f"rendering.{k}" for k in sorted(removed))
        _error(
            f"Removed rendering setting(s) {keys}; configure output size "
            "with the runtime export block",
            file_hint,
        )


def _validate_style_key_map(raw: object, path: str, file_hint: str | None = None) -> None:
    if not isinstance(raw, dict):
        return
    for type_name, entries in raw.items():
        if not isinstance(entries, dict):
            continue
        removed = REMOVED_STYLE_KEYS & entries.keys()
        if removed:
            key = sorted(removed)[0]
            _error(
                f"Removed style key '{path}.{type_name}.{key}' is not canonical; "
                "use the corresponding *_px key",
                file_hint,
            )


def _validate_removed_style_keys(style_json: dict, file_hint: str | None = None) -> None:
    _validate_style_key_map(style_json.get('defaults', {}), 'defaults', file_hint)
    overlay = style_json.get('overlay', {})
    if not isinstance(overlay, dict):
        return
    _validate_style_key_map(overlay.get('per_type', {}), 'overlay.per_type', file_hint)
    _validate_style_key_map(overlay.get('per_name', {}), 'overlay.per_name', file_hint)
    label_placement = overlay.get('label_placement', {})
    if isinstance(label_placement, dict):
        removed = REMOVED_LABEL_PLACEMENT_KEYS & label_placement.keys()
        if removed:
            key = sorted(removed)[0]
            _error(
                f"Removed overlay.label_placement key '{key}'; use "
                "angle_gap_arc_px and angle_gap_sides_px",
                file_hint,
            )


def _looks_like_hex_color(value: str) -> bool:
    head = value.strip().split()[0] if value.strip() else ''
    if not head.startswith('#') or len(head) not in (4, 7):
        return False
    return all(ch in '0123456789abcdefABCDEF' for ch in head[1:])


def _is_bare_preset_name(value: str) -> bool:
    if not value:
        return False
    return all(ch.isalnum() or ch in ('_', '-') for ch in value)


def _is_preset_ref_head(value: str, group: str) -> bool:
    return (
        value.startswith(f'presets.{group}.')
        or value.startswith(f'{group}.')
        or _is_bare_preset_name(value)
    )


def _validate_import_refs(style_json: dict, file_hint: str | None = None) -> None:
    imp = style_json.get('import', {})
    if not isinstance(imp, dict):
        return

    colors = imp.get('colors', {})
    if isinstance(colors, dict):
        for source, target in colors.items():
            if not isinstance(target, str):
                continue
            head = target.strip().split()[0] if target.strip() else ''
            if _is_preset_ref_head(head, 'color') or _looks_like_hex_color(target):
                continue
            _error(
                f"import.colors[{source!r}] uses bare preset ref {target!r}; "
                "use color.<name>, presets.color.<name>, a bare color token, or a hex color",
                file_hint,
            )

    for section, prefix in (('point_size', 'presets.point_size.'), ('line_width', 'presets.line_width.')):
        group = section
        mapping = imp.get(section, {})
        if not isinstance(mapping, dict):
            continue
        for source, target in mapping.items():
            if not isinstance(target, str):
                continue
            if target.startswith(prefix) or target.startswith(f'{group}.') or _is_bare_preset_name(target):
                continue
            _error(
                f"import.{section}[{source!r}] uses bare preset ref {target!r}; "
                f"use {group}.<name>, {prefix}<name>, or a bare token",
                file_hint,
            )

    policy = imp.get('policy', {})
    if isinstance(policy, dict):
        unknown = set(policy) - IMPORT_POLICY_KEYS
        if unknown:
            key = sorted(unknown)[0]
            if key == 'font_size':
                _error(
                    "Removed import.policy.font_size is not canonical; use import.policy.font_size_px",
                    file_hint,
                )
            _error(
                f"Unknown import.policy key {key!r}; use top-level overlay for type/name styling",
                file_hint,
            )


def _validate_reference(style_json: dict, file_hint: str | None = None) -> None:
    ref = style_json.get('reference', {})
    if not isinstance(ref, dict):
        return

    source = ref.get('source')
    if source is not None and source not in {'manual', 'source_view', 'ggb_view'}:
        _error(
            "reference.source must be one of: manual, source_view, ggb_view",
            file_hint,
        )

    size = ref.get('size')
    if size is None:
        return
    if not isinstance(size, dict):
        _error("reference.size must be an object with width/height", file_hint)
    for key in ('width', 'height'):
        value = size.get(key)
        if value in (None, 'auto'):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            _error(f"reference.size.{key} must be positive number or 'auto'", file_hint)
        if numeric <= 0:
            _error(f"reference.size.{key} must be positive", file_hint)


def validate_style_json(style_json: dict, file_hint: str | None = None) -> list[str]:
    """Validate a parsed style JSON dict.

    Raises :class:`RemovedStyleSchemaError` on removed schema shapes.
    Otherwise returns a list of non-fatal warnings (missing recommended
    sections, unknown top-level keys).
    """
    _detect_removed_schema(style_json, file_hint)
    _validate_rendering(style_json, file_hint)
    _validate_removed_style_keys(style_json, file_hint)
    _validate_import_refs(style_json, file_hint)
    _validate_reference(style_json, file_hint)

    warnings: list[str] = []
    present = set(style_json.keys())

    unknown = present - NEW_TOP_KEYS - {'name', 'version'}
    for key in sorted(unknown):
        if key.startswith('_'):
            continue   # underscore keys are comments by convention
        warnings.append(f"Unknown top-level key '{key}' — ignored")

    presets = style_json.get('presets', {})
    colors = presets.get('color', {}) if isinstance(presets, dict) else {}
    for key in ('main', 'light', 'accent', 'accent_light'):
        if not isinstance(colors, dict) or key not in colors:
            warnings.append(f"Missing 'presets.color.{key}'")

    return warnings
