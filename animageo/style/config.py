"""StyleConfig — unified style configuration with three independent layers.

Three layers of per-element styling, each with a single responsibility:

1. **defaults** (``DefaultsProfile``) — per-type baseline values in pixels.
   Never writes to ``elem.style``. Consulted by the resolver when neither
   an explicit user write, overlay override, nor enabled GGB import value is
   present.

2. **overlay** (``StyleOverlay``) — post-import stylization layer.
   Contains ``per_type``, ``per_name`` overrides plus automation flags
   (``angle_radius``, ``label_placement``). Applies uniformly to GGB-imported
   and DSL-built elements. Logically sits above the GGB import layer and is
   read lazily by the resolver.

3. **ggb** (``GGBImportPolicy``, pluggable) — GGB-only raw→import-style transforms.
   Used by the parser pipeline to convert ``elem.ggb_raw`` values into
   ``elem.ggb_style`` entries. Has no effect on DSL-built scenes.

Plus scene-level context:

- ``presets`` — semantic constants (colours, sizes, widths, structured tokens).
- ``reference`` — optional authoring reference metadata used by preview/export
  layout.
- ``rendering`` — low-level renderer flags (``line_cap``, ``right_angle_joint``…).

Loading merges a package-shipped ``builtin.json`` as the baseline with the
optional user JSON file on top — see :meth:`StyleConfig.load`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from .schema import validate_style_json

__all__ = [
    'DefaultsProfile',
    'StyleOverlay',
    'StyleConfig',
    'preset_ref_key',
    'resolve_preset_ref',
    'deep_merge',
    'BUILTIN_STYLE_PATH',
    'PRESETS_DIR',
    'available_style_presets',
    'resolve_style_input',
]


BUILTIN_STYLE_PATH: Path = Path(__file__).parent / 'builtin.json'
PRESETS_DIR: Path = Path(__file__).parent / 'presets'


def available_style_presets() -> list:
    """Names of the style presets shipped inside the package."""
    return sorted(p.stem for p in PRESETS_DIR.glob('*.json'))


def resolve_style_input(style):
    """Resolve a bare preset name to the packaged preset JSON path.

    ``style='default'`` (or any name from :func:`available_style_presets`)
    maps to ``animageo/style/presets/<name>.json``. Anything else — ``None``,
    dicts, :class:`StyleConfig`, existing file paths, strings containing a
    path separator or ``.json`` suffix — passes through unchanged, so an
    on-disk file with the same name always wins over a packaged preset.
    """
    if (
        isinstance(style, str)
        and style
        and '/' not in style and '\\' not in style
        and not style.endswith('.json')
        and not Path(style).exists()
    ):
        preset = PRESETS_DIR / (style + '.json')
        if preset.exists():
            return str(preset)
    return style


# ── Helpers ──────────────────────────────────────────────────────────────

def deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge ``overlay`` into a copy of ``base``.

    Dict values are merged key-by-key (recursively). Any other value type
    in ``overlay`` (scalar, list, None) replaces the corresponding value in
    ``base``. Lists are NOT concatenated — arrays are replacement values.

    Both inputs are treated as read-only; a fresh dict tree is returned.
    """
    result = _deep_copy_dict(base)
    for key, value in overlay.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = _deep_copy_value(value)
    return result


def _deep_copy_dict(d: dict) -> dict:
    return {k: _deep_copy_value(v) for k, v in d.items()}


def _deep_copy_value(v):
    if isinstance(v, dict):
        return _deep_copy_dict(v)
    if isinstance(v, list):
        return [_deep_copy_value(x) for x in v]
    return v


# ── Sub-configs ──────────────────────────────────────────────────────────

@dataclass
class DefaultsProfile:
    """Per-element-type default style values in pixel units.

    Accessed via :meth:`get` by the resolver. Never mutated by consumers
    during a scene's lifetime; instances are logically immutable after
    :meth:`StyleConfig.load` returns.
    """
    by_type: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def get(self, type_name: str, key: str, fallback: Any = None) -> Any:
        return self.by_type.get(type_name, {}).get(key, fallback)

    def for_type(self, type_name: str) -> Dict[str, Any]:
        """Return the full dict of defaults for a type (empty if unknown)."""
        return self.by_type.get(type_name, {})


@dataclass
class StyleOverlay:
    """Post-import stylization layer — works for GGB and DSL equally.

    Attributes:
        per_type: ``{type_name: {style_key: value}}`` — override all elements
            of a type.
        per_name: ``{elem_name: {style_key: value}}`` — override a single
            named element (higher priority than ``per_type``).
        angle_radius: auto-scaling config for angle arc radii.
        label_placement: auto-placement config.
    """
    per_type: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    per_name: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    angle_radius: Dict[str, Any] = field(default_factory=dict)
    label_placement: Dict[str, Any] = field(default_factory=dict)

# ── Top-level config ─────────────────────────────────────────────────────

@dataclass
class StyleConfig:
    """Top-level style configuration loaded from JSON.

    Use :meth:`load` to construct an instance — it always merges the
    package ``builtin.json`` underneath any user-supplied JSON.

    Never construct directly unless you know that every downstream reader
    can tolerate empty ``defaults`` / ``presets`` / ``rendering``.
    """
    presets: Dict[str, Any] = field(default_factory=dict)
    reference: Dict[str, Any] = field(default_factory=dict)
    rendering: Dict[str, Any] = field(default_factory=dict)
    defaults: DefaultsProfile = field(default_factory=DefaultsProfile)
    overlay: StyleOverlay = field(default_factory=StyleOverlay)
    ggb: Any = None  # Optional[GGBImportPolicy], populated in Phase 5.

    # Raw source dict kept for debugging / introspection; callers should
    # not depend on it for correctness.
    source: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, user_path: Optional[Any] = None) -> 'StyleConfig':
        """Load builtin defaults; optionally deep-merge a user style on top.

        ``user_path`` accepts ``None``, a JSON path, a raw style dict, or an
        existing :class:`StyleConfig`.

        The returned config is the single source of truth for the new
        resolver path.
        """
        if isinstance(user_path, cls):
            return user_path
        user_path = resolve_style_input(user_path)
        builtin = _read_json(BUILTIN_STYLE_PATH)
        if user_path is None:
            merged = builtin
        elif isinstance(user_path, dict):
            validate_style_json(user_path)
            merged = deep_merge(builtin, user_path)
        elif user_path == '':
            merged = builtin
        else:
            user = _read_json(user_path)
            validate_style_json(user, file_hint=str(user_path))
            merged = deep_merge(builtin, user)
        return cls.from_dict(merged)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'StyleConfig':
        presets = _deep_copy_dict(d.get('presets', {})) if isinstance(d.get('presets'), dict) else {}
        reference = _deep_copy_dict(d.get('reference', {})) if isinstance(d.get('reference'), dict) else {}
        rendering = cls._resolve_refs_static(dict(d.get('rendering', {})), presets)

        validate_style_json(d)

        defaults_raw = _expand_includes_in_type_map(d.get('defaults', {}), presets)
        defaults = DefaultsProfile(
            by_type=cls._resolve_refs_static(_coerce_type_map(defaults_raw), presets)
        )

        overlay_raw = d.get('overlay', {}) or {}
        overlay_per_type = _expand_includes_in_type_map(overlay_raw.get('per_type', {}), presets)
        overlay_per_name = _expand_includes_in_type_map(overlay_raw.get('per_name', {}), presets)
        overlay = StyleOverlay(
            per_type=cls._resolve_refs_static(
                _coerce_type_map(overlay_per_type),
                presets,
            ),
            per_name=cls._resolve_refs_static(
                _coerce_type_map(overlay_per_name),
                presets,
            ),
            angle_radius=cls._resolve_refs_static(dict(overlay_raw.get('angle_radius', {})), presets),
            label_placement=cls._resolve_refs_static(dict(overlay_raw.get('label_placement', {})), presets),
        )

        return cls(
            presets=presets,
            reference=reference,
            rendering=rendering,
            defaults=defaults,
            overlay=overlay,
            ggb=None,
            source=d,
        )

    def resolve_ref(self, value: Any) -> Any:
        """Resolve style-token references.

        References may use either ``"presets.<group>.<name>"`` or the
        shorter ``"<group>.<name>"`` form.
        """
        return self._resolve_refs_static(value, self.presets)

    @staticmethod
    def _resolve_refs_static(value: Any, presets: Dict[str, Any]) -> Any:
        return _resolve_refs(value, presets)


# ── Internals ────────────────────────────────────────────────────────────

def _read_json(path) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _coerce_type_map(raw: Any) -> Dict[str, Dict[str, Any]]:
    """Normalise ``{type: {key: val}}`` dict, dropping non-dict entries.

    Defensive: tolerates ``None`` top-level and non-dict leaves (ignores
    them with no warning; schema validation is a separate concern).
    """
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for type_name, entries in raw.items():
        if isinstance(entries, dict):
            out[str(type_name)] = dict(entries)
    return out


def _resolve_refs(value: Any, presets: Dict[str, Any], seen=None) -> Any:
    """Resolve preset refs recursively."""
    if seen is None:
        seen = set()

    if isinstance(value, dict):
        return {k: _resolve_refs(v, presets, seen) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_refs(v, presets, seen) for v in value]
    if not isinstance(value, str):
        return value

    key = preset_ref_key(value, presets)
    if key is None:
        return value

    if key in seen:
        raise ValueError(f"Cyclic style preset reference: {value}")
    seen.add(key)
    resolved = resolve_preset_ref(value, presets, fallback=value)
    if resolved is value:
        seen.remove(key)
        return value
    out = _resolve_refs(_deep_copy_value(resolved), presets, seen)
    seen.remove(key)
    return out


def preset_ref_key(value: Any, presets: Dict[str, Any]) -> str | None:
    """Return a canonical key for a preset ref, or ``None`` for literals.

    Fully qualified refs keep working (``presets.color.main``). Short refs are
    accepted when their first path segment names an existing preset group
    (``color.main``, ``line_width.bold``, ``tick.main``). Single-word strings
    are intentionally left as literals here because many style values are enums
    or labels; context-specific callers may resolve those separately.
    """
    if not isinstance(value, str):
        return None
    parts = _preset_ref_parts(value, presets)
    if parts is None:
        return None
    return 'presets.' + '.'.join(parts)


def resolve_preset_ref(value: Any, presets: Dict[str, Any], fallback: Any = None) -> Any:
    """Resolve a fully qualified or short preset ref against ``presets``."""
    parts = _preset_ref_parts(value, presets)
    if parts is None:
        return fallback
    return _lookup_path(presets, parts, fallback=fallback)


def _preset_ref_parts(value: Any, presets: Dict[str, Any]) -> list[str] | None:
    if not isinstance(value, str):
        return None
    ref = value.strip()
    if not ref or any(ch.isspace() for ch in ref):
        return None
    parts = ref.split('.')
    if parts[0] == 'presets':
        return parts[1:] if len(parts) > 2 else None
    if len(parts) > 1 and isinstance(presets, dict) and parts[0] in presets:
        return parts
    return None


def _lookup_path(root: Dict[str, Any], parts: list[str], fallback: Any = None) -> Any:
    cur: Any = root
    for part in parts:
        if not isinstance(cur, dict) or part not in cur:
            return fallback
        cur = cur[part]
    return cur


def _expand_includes_in_type_map(raw: Any, presets: Dict[str, Any]) -> Dict[str, Any]:
    """Expand ``$include`` inside a ``{type: {key: value}}`` mapping."""
    if not isinstance(raw, dict):
        return {}
    return {
        str(type_name): _expand_includes(entries, presets)
        for type_name, entries in raw.items()
        if isinstance(entries, dict)
    }


def _expand_includes(entries: Dict[str, Any], presets: Dict[str, Any], seen=None) -> Dict[str, Any]:
    """Expand structural preset includes.

    ``{"$include": "presets.arrow.main", "x": 1}`` or
    ``{"$include": "arrow.main", "x": 1}`` merges the referenced
    dict first, then local keys on top. Included dicts may include other
    dicts. Scalar refs are ignored here; they are handled by normal reference
    resolution later.
    """
    if seen is None:
        seen = set()

    merged: Dict[str, Any] = {}
    include = entries.get('$include')
    include_refs = include if isinstance(include, list) else ([include] if include else [])

    for ref in include_refs:
        if not isinstance(ref, str):
            continue
        key = preset_ref_key(ref, presets)
        if key is None:
            continue
        if key in seen:
            raise ValueError(f"Cyclic style preset include: {ref}")
        seen.add(key)
        included = resolve_preset_ref(ref, presets, fallback=None)
        if isinstance(included, dict):
            merged = deep_merge(merged, _expand_includes(included, presets, seen))
        seen.remove(key)

    local = {k: v for k, v in entries.items() if k != '$include'}
    return deep_merge(merged, local)
