"""ImportPolicy — configurable GGB → import-style resolution.

An ImportPolicy decides, per property, how to derive the final rendered
style from a GeoGebra element's raw attributes. Each field can be:

- **None** — defer to the base mode (faithful → GGB, style_only → defaults).
- **scalar / bool / list / dict / tuple** — literal override.
- **Callable(raw, defaults, elem)** — user-supplied function.
- **str** — passed through `dsl.parse_directive` (``const:``, ``scale:``,
  ``quantize:``, ``remap:``, or a sentinel like ``match_element`` / ``auto``).

Resolution order:
  1. ``base`` starting state (faithful or style_only).
  2. Field resolvers that map GGB raw values (``point_size``,
     ``line_thickness``, ``obj_color.hex``...) into import-style keys.

Project-level styling by element type/name belongs to ``StyleConfig.overlay``.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Callable, Dict, Optional

from .ggb_resolver import resolve_ggb_style
from .dsl import parse_directive


# Mapping: policy field → (ggb_raw key, import-style key).
# The ggb_raw key feeds callables; the import-style key is where the resolved
# value lands in ``elem.ggb_style``. Field and style-key names match
# one-to-one in the schema.
_FIELD_MAP: Dict[str, tuple] = {
    'size_px':          ('point_size',      'size_px'),
    'stroke_width_px':  ('line_thickness',  'stroke_width_px'),
    'arc_size_px':      ('arc_size',        'arc_size_px'),
    'label_offset_px':  ('label_offset_px', 'label_offset_px'),
    'label_color':      ('obj_color.hex',   'label_color'),
    'label_visible':    ('show_label',      'label_visible'),
    'visible':          ('show_object',     'visible'),
    'label_text':       ('label_caption',   'label_text'),
    'label_mode':       ('label_mode',      'label_mode'),
    'label_value_precision': (None,         'label_value_precision'),
    'label_value_strip_zeros': (None,       'label_value_strip_zeros'),
    'label_angle_unit': (None,              'label_angle_unit'),
    'label_value_separator': (None,         'label_value_separator'),
    'angle_range':      ('angle_style',     'angle_range'),
    'tick_count':       ('decoration_lines','tick_count'),
    'font_size_px':     (None,              'font_size_px'),
    'stroke':           ('obj_color.hex',   'stroke'),
    'fill':             ('obj_color.hex',   'fill'),
    'fill_opacity':     ('obj_color.opacity','fill_opacity'),
    'point_shape':      ('point_style',     'point_shape'),   # int→string mapping in enums
    'stroke_opacity':   ('line_opacity',    'stroke_opacity'),
    'stroke_dash_ratio':('line_type',       'stroke_dash_ratio'),
    'stroke_linecap':   (None,              'stroke_linecap'),
}


@dataclass
class ImportPolicy:
    base: str = 'faithful'  # 'faithful' | 'style_only'

    size_px:         Any = None
    stroke_width_px: Any = None
    arc_size_px:     Any = None
    label_offset_px: Any = None
    label_color:     Any = None
    label_visible:   Any = None
    visible:         Any = None
    label_text:      Any = None
    label_mode:      Any = None
    label_value_precision: Any = None
    label_value_strip_zeros: Any = None
    label_angle_unit: Any = None
    label_value_separator: Any = None
    angle_range:     Any = None
    tick_count:      Any = None
    stroke:          Any = None
    fill:            Any = None
    fill_opacity:    Any = None

    font_size_px:    Any = None
    point_shape:     Any = None
    stroke_opacity:  Any = None
    stroke_dash_ratio: Any = None
    stroke_linecap:  Any = None

    def __post_init__(self):
        # Parse DSL strings eagerly so fields store resolved values (scalars
        # or callables) regardless of whether the policy came from Python or
        # JSON. Bare strings (hex colors, sentinels) pass through unchanged.
        for f in fields(self):
            if f.name == 'base':
                continue
            setattr(self, f.name, parse_directive(getattr(self, f.name)))

    # ── Factories ─────────────────────────────────────────────────────

    @classmethod
    def faithful(cls) -> 'ImportPolicy':
        """Preserve imported GGB visual values by default."""
        return cls(base='faithful')

    @classmethod
    def style_only(cls) -> 'ImportPolicy':
        """Ignore GGB sizes/colors; caller supplies ``defaults`` in resolve()."""
        return cls(base='style_only')

    @classmethod
    def from_dict(cls, d: dict) -> 'ImportPolicy':
        """Build an ImportPolicy from a JSON-style dict.

        Keys matching dataclass fields are parsed through :func:`parse_directive`.
        Unknown keys raise ``ValueError``; type/name styling belongs under
        the top-level ``overlay`` style section.
        """
        policy_fields = {f.name for f in fields(cls)}
        kwargs: Dict[str, Any] = {}

        for key, value in d.items():
            if key == 'preset':
                # "preset": "faithful"|"style_only"|"custom" — translate to base
                if value in ('faithful', 'style_only'):
                    kwargs['base'] = value
                continue
            if key == 'base':
                kwargs['base'] = value
                continue
            if key in policy_fields:
                kwargs[key] = parse_directive(value)
                continue
            raise ValueError(
                f"Unknown import.policy key {key!r}; use top-level overlay "
                "for type/name styling"
            )

        return cls(**kwargs)

    # ── Resolution ────────────────────────────────────────────────────

    def resolve(
        self,
        elem,
        defaults: Optional[dict] = None,
        ptUnit: float = 1.0,
    ) -> dict:
        """Compute the final import-style dict for a single geometry element.

        The output is a fresh dict; the caller decides how to merge it into
        ``elem.ggb_style`` or another diagnostics structure.
        """
        defaults = defaults or {}

        # 1. Base starting state.
        if self.base == 'style_only':
            style = dict(defaults)
        else:
            style = resolve_ggb_style(getattr(elem, 'ggb_raw', {}) or {})

        # 2. Field-by-field GGB raw → import-style overrides.
        for field_name, (raw_key, style_key) in _FIELD_MAP.items():
            policy_value = getattr(self, field_name)
            if policy_value is None:
                continue
            raw_value = None
            if raw_key is not None:
                raw_value = _get_raw_value(elem.ggb_raw or {}, raw_key)
            resolved = _apply_resolver(policy_value, raw_value, defaults, elem)
            if resolved is _DROP:
                style.pop(style_key, None)
            else:
                style[style_key] = resolved

        return style

    def resolve_overrides_only(
        self,
        elem,
        defaults: Optional[dict] = None,
        ptUnit: float = 1.0,
    ) -> dict:
        """Return only the style keys this policy actively overrides.

        Use when the caller already has a baseline ``elem.ggb_style`` and
        wants to layer policy-driven overrides on top without destroying
        non-policy fields.
        """
        defaults = defaults or {}
        overrides: Dict[str, Any] = {}

        for field_name, (raw_key, style_key) in _FIELD_MAP.items():
            policy_value = getattr(self, field_name)
            if policy_value is None:
                continue
            raw_value = None
            if raw_key is not None:
                raw_value = _get_raw_value(getattr(elem, 'ggb_raw', {}) or {}, raw_key)
            resolved = _apply_resolver(policy_value, raw_value, defaults, elem)
            if resolved is _DROP:
                continue
            overrides[style_key] = resolved

        return overrides


# Sentinel for "remove this style key" — reserved for future callers that
# want to drop e.g. label_visible rather than set it to False.
_DROP = object()


def _apply_resolver(policy_value, raw_value, defaults, elem):
    """Coerce a policy field value into a resolved style value."""
    if callable(policy_value):
        return policy_value(raw_value, defaults, elem)
    if isinstance(policy_value, str):
        # Strings may still be literal pass-throughs (e.g. "#000000").
        # from_dict already called parse_directive, so bare strings here
        # are just values; return unchanged.
        return policy_value
    return policy_value


def _get_raw_value(raw: dict, key_path: str):
    """Return a raw GGB value, supporting dotted paths such as obj_color.hex."""
    if key_path == 'obj_color':
        return _normalize_obj_color(raw.get('obj_color'))

    cur: Any = raw
    for part in key_path.split('.'):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if part == 'obj_color':
            cur = _normalize_obj_color(cur)
    return cur


def _normalize_obj_color(value):
    """Expose GGB objColor as r/g/b plus convenient hex/opacity aliases."""
    if not isinstance(value, dict):
        return value
    out = dict(value)
    if 'opacity' not in out and 'alpha' in out:
        out['opacity'] = out['alpha']
    if 'hex' not in out and all(k in out for k in ('r', 'g', 'b')):
        out['hex'] = '#%02x%02x%02x' % (
            int(out['r']),
            int(out['g']),
            int(out['b']),
        )
    return out
