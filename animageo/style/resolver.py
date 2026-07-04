"""Style resolver — single entry point for reading an element's visual properties.

The resolver walks a priority chain to answer "what is the value of style
key ``K`` for element ``E``?". The chain, from highest to lowest priority:

1. ``elem.style[K]``          — explicit user write (DSL/Python assignment).
2. ``overlay.per_name[name][K]``  — point-override for a named element.
3. ``overlay.per_type[type][K]``  — all-of-type override.
4. ``elem.ggb_style[K]``      — imported/adapted GeoGebra visual baseline,
   only when ``import.enabled`` is not ``false``.
5. ``defaults.by_type[type][K]``  — package / JSON per-type baseline.
6. Caller-supplied ``default``   — final fallback.

Consequence: DSL code like ``A.style.size_px = 99`` is never overridden by
``overlay.per_type.point.size_px`` in a style file, because step 1 wins.
GeoGebra parser values are not explicit writes; they live in the import layer
and are therefore overridden by overlay rules and ignored entirely when
``import.enabled`` is ``false``.

Style-token references (``"presets.color.main"`` or ``"color.main"``) are
resolved transparently via :meth:`StyleConfig.resolve_ref`.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


__all__ = [
    'resolve',
    'resolved_style',
    'etype_of',
    'trace',
]


_SENTINEL = object()


def etype_of(elem) -> str:
    """Return the canonical element-type name used as the overlay/defaults key.

    Uses the lowercase class name of ``elem.data``. Matches how the
    parser-side ``ggb_raw['elem_type']`` values are encoded (``'point'``,
    ``'segment'``, ``'angle'``, …) for the common cases; DSL-built elements
    also land on the same names because the geometry classes follow the
    GGB naming convention (``Point``, ``Segment``, ``Angle``, …).

    Elements whose ``.data`` is missing or has no ``__class__`` fall back
    to ``'unknown'`` so callers don't have to branch on the malformed case.
    """
    data = getattr(elem, 'data', None)
    if data is None:
        return 'unknown'
    return type(data).__name__.lower()


def resolve(scene, elem, key: str, default: Any = None) -> Any:
    """Resolve a style key for an element, walking the priority chain.

    Args:
        scene: Scene or any object exposing ``style_config``. Accepts a
            bare ``StyleConfig`` too, for unit-testing the chain without a
            full scene.
        elem: Element with ``.style`` dict and (indirectly) ``.data``.
        key: Style-key name (e.g. ``'size_px'``, ``'stroke'``).
        default: Value returned when no layer has the key.

    Returns:
        The resolved value, with preset references expanded.
    """
    if key == 'visible':
        return _resolve_visible(scene, elem, default)

    value = _resolve_key(scene, elem, key, default)

    # ``fill: "stroke"`` — the fill follows the element's OWN stroke colour
    # instead of a fixed palette slot. Used by the Basic 'Заливка фигур'
    # control so a shape is filled with a translucent tint of its own outline
    # colour (the opacity is set separately). Resolved here, after the priority
    # chain, so it works no matter which layer set the sentinel and so every
    # consumer stays consistent (manim render + TikZ/JSXGraph exporters all go
    # through this resolver). ``"stroke"`` is a single-word literal, so the
    # preset-ref expander leaves it untouched — safe as a sentinel.
    if key == 'fill' and isinstance(value, str) and value.strip().lower() == 'stroke':
        return resolve(scene, elem, 'stroke', default=default)
    return value


def _resolve_key(scene, elem, key: str, default: Any = None) -> Any:
    """Walk the style priority chain for ``key`` (no sentinel post-processing)."""
    if _has_explicit_style(elem, key):
        return _expand_ref(scene, elem.style[key])

    cfg = _config_of(scene)
    if cfg is None:
        return default

    name = getattr(elem, 'name', None)
    if name and name in cfg.overlay.per_name:
        if key in cfg.overlay.per_name[name]:
            return _expand_ref(cfg, cfg.overlay.per_name[name][key])

    etype = etype_of(elem)
    if etype in cfg.overlay.per_type and key in cfg.overlay.per_type[etype]:
        return _expand_ref(cfg, cfg.overlay.per_type[etype][key])

    if _import_enabled(cfg):
        ggb_style = getattr(elem, 'ggb_style', None)
        if ggb_style is not None and key in ggb_style:
            return _expand_ref(cfg, ggb_style[key])

    default_val = cfg.defaults.get(etype, key, _SENTINEL)
    if default_val is not _SENTINEL:
        return _expand_ref(cfg, default_val)

    if key in elem.style:
        return _expand_ref(scene, elem.style[key])

    return default


def resolved_style(scene, elem) -> Dict[str, Any]:
    """Materialise the complete resolved style for an element.

    Useful for snapshot testing and debugging ("what is the renderer
    actually going to see?"). Result contains every key present in any
    layer, with preset references expanded.

    Write order (lowest to highest priority):
        defaults → ggb_style → per_type → per_name → elem.style

    so the final dict already reflects the :func:`resolve` priority chain.
    """
    cfg = _config_of(scene)
    merged: Dict[str, Any] = {}
    if cfg is not None:
        etype = etype_of(elem)
        merged.update(cfg.defaults.for_type(etype))
        if _import_enabled(cfg):
            merged.update(getattr(elem, 'ggb_style', {}) or {})
        merged.update(cfg.overlay.per_type.get(etype, {}))
        name = getattr(elem, 'name', None)
        if name:
            merged.update(cfg.overlay.per_name.get(name, {}))
    intrinsic = {}
    explicit = {}
    for k, v in elem.style.items():
        if _has_explicit_style(elem, k):
            explicit[k] = v
        else:
            intrinsic[k] = v
    merged = {**intrinsic, **merged, **explicit}
    return {k: _expand_ref(cfg, v) for k, v in merged.items()}


def trace(scene, elem, key: str) -> tuple[str, Any]:
    """Return ``(source, value)`` for the key, or ``('missing', None)``.

    ``source`` is one of ``'elem.style'``, ``'overlay.per_name'``,
    ``'overlay.per_type'``, ``'ggb_style'``, ``'defaults'``,
    ``'intrinsic.style'``, ``'missing'``. For ``visible`` it may also be
    ``'elem.visible'``. Preset refs are expanded, just like :func:`resolve`.
    """
    if key == 'visible':
        return _trace_visible(scene, elem)

    if _has_explicit_style(elem, key):
        return 'elem.style', _expand_ref(scene, elem.style[key])
    cfg = _config_of(scene)
    if cfg is None:
        return 'missing', None
    name = getattr(elem, 'name', None)
    if name and key in cfg.overlay.per_name.get(name, {}):
        return 'overlay.per_name', _expand_ref(cfg, cfg.overlay.per_name[name][key])
    etype = etype_of(elem)
    if key in cfg.overlay.per_type.get(etype, {}):
        return 'overlay.per_type', _expand_ref(cfg, cfg.overlay.per_type[etype][key])
    if _import_enabled(cfg):
        ggb_style = getattr(elem, 'ggb_style', None)
        if ggb_style is not None and key in ggb_style:
            return 'ggb_style', _expand_ref(cfg, ggb_style[key])
    val = cfg.defaults.get(etype, key, _SENTINEL)
    if val is not _SENTINEL:
        return 'defaults', _expand_ref(cfg, val)
    if key in elem.style:
        return 'intrinsic.style', _expand_ref(scene, elem.style[key])
    return 'missing', None


# ── Internals ────────────────────────────────────────────────────────────

def _config_of(scene_or_cfg) -> Optional[Any]:
    """Return a StyleConfig from a scene, or pass through an already-bare config."""
    if scene_or_cfg is None:
        return None
    cfg = getattr(scene_or_cfg, 'style_config', None)
    if cfg is not None:
        return cfg
    # Allow passing a bare StyleConfig directly (useful for unit tests).
    if hasattr(scene_or_cfg, 'defaults') and hasattr(scene_or_cfg, 'overlay'):
        return scene_or_cfg
    return None


def _expand_ref(scene_or_cfg, value):
    """Expand style-token references via StyleConfig.resolve_ref."""
    if not isinstance(value, str):
        return value
    cfg = _config_of(scene_or_cfg)
    if cfg is None:
        return value
    if hasattr(cfg, 'resolve_ref'):
        return cfg.resolve_ref(value)
    return value


def _has_explicit_style(elem, key: str) -> bool:
    style = getattr(elem, 'style', {}) or {}
    if key not in style:
        return False
    checker = getattr(style, 'is_explicit', None)
    if checker is None:
        return True
    return bool(checker(key))


def _has_explicit_visible(elem) -> bool:
    return bool(getattr(elem, '_visible_explicit', False))


def _has_construction_visible(elem) -> bool:
    return bool(getattr(elem, '_visible_has_value', False))


def _resolve_visible(scene, elem, default: Any = None) -> bool:
    if _has_explicit_style(elem, 'visible'):
        return bool(_expand_ref(scene, elem.style['visible']))

    # Runtime visibility changes (Show/Hide/addAllGeometry(show=False)) are
    # construction state and must not be overwritten by style layers.
    if _has_explicit_visible(elem):
        return bool(getattr(elem, 'visible', True))

    cfg = _config_of(scene)
    if cfg is not None:
        name = getattr(elem, 'name', None)
        if name and 'visible' in cfg.overlay.per_name.get(name, {}):
            return bool(_expand_ref(cfg, cfg.overlay.per_name[name]['visible']))

        etype = etype_of(elem)
        if 'visible' in cfg.overlay.per_type.get(etype, {}):
            return bool(_expand_ref(cfg, cfg.overlay.per_type[etype]['visible']))

    # GeoGebra <show object> and ImportPolicy.visible are geometry-level import
    # state, not visual style. They are intentionally outside elem.ggb_style.
    if _has_construction_visible(elem):
        return bool(getattr(elem, 'visible', True))

    if cfg is not None:
        default_val = cfg.defaults.get(etype_of(elem), 'visible', _SENTINEL)
        if default_val is not _SENTINEL:
            return bool(_expand_ref(cfg, default_val))

    if hasattr(elem, 'visible'):
        return bool(getattr(elem, 'visible'))
    return bool(default)


def _trace_visible(scene, elem) -> tuple[str, Any]:
    if _has_explicit_style(elem, 'visible'):
        return 'elem.style', bool(_expand_ref(scene, elem.style['visible']))
    if _has_explicit_visible(elem):
        return 'elem.visible', bool(getattr(elem, 'visible', True))

    cfg = _config_of(scene)
    if cfg is not None:
        name = getattr(elem, 'name', None)
        if name and 'visible' in cfg.overlay.per_name.get(name, {}):
            return 'overlay.per_name', bool(_expand_ref(cfg, cfg.overlay.per_name[name]['visible']))
        etype = etype_of(elem)
        if 'visible' in cfg.overlay.per_type.get(etype, {}):
            return 'overlay.per_type', bool(_expand_ref(cfg, cfg.overlay.per_type[etype]['visible']))

    if _has_construction_visible(elem):
        return 'elem.visible', bool(getattr(elem, 'visible', True))

    if cfg is not None:
        val = cfg.defaults.get(etype_of(elem), 'visible', _SENTINEL)
        if val is not _SENTINEL:
            return 'defaults', bool(_expand_ref(cfg, val))
    return 'missing', None


def _import_enabled(cfg) -> bool:
    source = getattr(cfg, 'source', {}) or {}
    imp = source.get('import', {}) if isinstance(source, dict) else {}
    if isinstance(imp, dict) and imp.get('enabled') is False:
        return False
    return True
