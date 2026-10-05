"""Keyframe animation system for AnimaGeo.

Converts a sequence of keyframes (time + independent values) into
manim animations that smoothly interpolate the construction state.

JSON format:
{
    "keyframes": [
        {
            "t": 0.0,
            "values": {"A": [2, 3], "x": 35, "D": {"tparam": 0.7}},
            "show": ["elem1"],
            "hide": ["elem2"],
            "easing": "smooth"
        },
        ...
    ]
}

The ``D: {"tparam": 0.7}`` form sets the curve/locus parameter for a
point constrained to a circle (angle in radians) or a segment/line/
ray (linear t).
"""

import logging
import math
import warnings
from dataclasses import dataclass

import numpy as np
from .geo.lib_elements import Point, Line, Segment, Ray, Circle
from .geo.lib_vars import Measure, AngleSize, Boolean
from .style.animatable import normalize_style_value, style_kind
from .style.colorspace import lerp_color, is_hex_color, normalize_hex

logger = logging.getLogger(__name__)

#--------------------------------------------------------------------------
# Easing functions (matching manim rate_functions) — animageo/easing.py
#--------------------------------------------------------------------------

from .easing import (  # noqa: F401  (re-exported: tests and callers import them from here)
    EASING_FUNCTIONS, _clamp01, _ease_in, _ease_in_cubic, _ease_in_out, _ease_in_out_cubic,
    _ease_in_out_sine, _ease_in_sine, _ease_linear, _ease_out, _ease_out_back, _ease_out_bounce,
    _ease_out_cubic, _ease_out_elastic, _ease_out_sine, _ease_rush_from, _ease_rush_into,
    _ease_smooth, _ease_smootherstep, _manim_smooth_sigmoid,
)

#--------------------------------------------------------------------------
# Visibility entrance/exit effects (v2)
#--------------------------------------------------------------------------

ENTER_EFFECTS = ('fade', 'none', 'create', 'grow', 'write')
EXIT_EFFECTS = ('fade', 'none', 'uncreate', 'shrink')
DEFAULT_EFFECT_DURATION = 0.4

#--------------------------------------------------------------------------
# Emphasis events (v2)
#--------------------------------------------------------------------------

EVENT_EFFECTS = ('indicate', 'flash', 'circumscribe')

#--------------------------------------------------------------------------
# @camera pseudo-element (v2)
#--------------------------------------------------------------------------

CAMERA_KEY = '@camera'


@dataclass
class EffectSpec:
    name: str
    kind: str        # 'fade' | 'none' | 'create' | 'grow' | 'uncreate' | 'shrink'
    start: float     # seconds from interval start
    duration: float
    direction: str   # 'in' (entrance) | 'out' (exit)


@dataclass
class EventSpec:
    effect: str
    targets: list
    start: float
    duration: float
    color: object = None      # hex str or None
    scale: float = 1.2

#--------------------------------------------------------------------------
# Interpolators
#--------------------------------------------------------------------------

class Interpolator:
    """Interpolates a single value between two keyframes."""

    __slots__ = ('name', 'kind', 'start', 'end', 'easing', 'angle_direction')

    def __init__(self, name, kind, start, end, easing=None, angle_direction='short'):
        self.name = name
        # Interpolator kind:
        #   'point'            — 2D coord lerp
        #   'tparam_circle'    — angular t on a circle/ellipse (uses angle_direction)
        #   'tparam_linear'    — scalar t on segment/line/ray/parabola/locus/function
        #   'tparam_hyperbola' — (branch, t): branch snaps at 0.5, t lerps
        #   'text_position'    — 2D coord lerp for free text objects
        #   'var' / 'bool'     — scalar var / boolean snap
        self.kind = kind
        self.start = start
        self.end = end
        self.easing = easing or _ease_smooth
        self.angle_direction = angle_direction  # 'short' | 'cw' | 'ccw' — only for tparam_circle

    @staticmethod
    def _hyperbola_pair(v):
        """Normalize a hyperbola tparam to (branch, t); bare scalars mean branch +1."""
        if isinstance(v, (tuple, list)):
            return (1.0 if float(v[0]) >= 0 else -1.0, float(v[1]))
        return (1.0, float(v))

    def at(self, t):
        """Return interpolated value at progress t ∈ [0, 1]."""
        et = self.easing(t)

        if self.kind == 'bool':
            return self.end if et >= 0.5 else self.start

        if self.kind in ('point', 'text_position'):
            return (1 - et) * self.start + et * self.end

        if self.kind == 'tparam_circle':
            return _interpolate_angle(self.start, self.end, et, self.angle_direction)

        if self.kind == 'tparam_hyperbola':
            b0, t0 = self._hyperbola_pair(self.start)
            b1, t1 = self._hyperbola_pair(self.end)
            branch = b0 if et < 0.5 else b1
            return (branch, (1 - et) * t0 + et * t1)

        # tparam_linear, var — scalar lerp
        return (1 - et) * self.start + et * self.end


class LabelOffsetInterpolator:
    """Interpolates a static label's (offset_x, offset_y) in ggb pixel units.

    Mirrors ``Interpolator`` but for label offsets: easing is applied to the
    same progress ``t`` used by geometry interpolators, so labels glide in
    sync with their anchor geometry between keyframe layouts.
    """
    __slots__ = ('name', 'start_offset', 'end_offset', 'easing')

    def __init__(self, name, start_offset, end_offset, easing=None):
        self.name = name
        self.start_offset = np.asarray(start_offset, dtype=float)
        self.end_offset = np.asarray(end_offset, dtype=float)
        self.easing = easing or _ease_smooth

    def at(self, t):
        et = self.easing(t)
        return (1.0 - et) * self.start_offset + et * self.end_offset


class StyleInterpolator:
    """Interpolates one ``elem.style`` key between two keyframes.

    Kind semantics (see ``style/animatable.py``): 'scalar' lerps floats,
    'color' lerps hex colors in ``color_space`` (Oklab default), 'offset2'
    lerps [x, y] pairs, 'dash' lerps when both endpoints are numbers and
    snaps otherwise, 'discrete' snaps to the end value at eased progress
    >= 0.5 (the CSS discrete rule — same convention as the 'bool'
    Interpolator kind), 'text' (label_text) never lerps and snaps at eased
    progress >= 0.5 like 'discrete'.
    """

    __slots__ = ('name', 'key', 'kind', 'start', 'end', 'easing', 'color_space')

    def __init__(self, name, key, kind, start, end, easing=None,
                 color_space='oklab'):
        self.name = name
        self.key = key
        self.kind = kind
        self.start = start
        self.end = end
        self.easing = easing or _ease_smooth
        self.color_space = color_space

    def at(self, t):
        """Return the interpolated value at progress t in [0, 1]."""
        et = self.easing(t)

        if self.kind == 'scalar':
            return (1 - et) * self.start + et * self.end

        if self.kind == 'color':
            return lerp_color(self.start, self.end, et, space=self.color_space)

        if self.kind == 'offset2':
            return [
                (1 - et) * self.start[0] + et * self.end[0],
                (1 - et) * self.start[1] + et * self.end[1],
            ]

        if self.kind == 'dash':
            if (isinstance(self.start, (int, float))
                    and isinstance(self.end, (int, float))):
                return (1 - et) * self.start + et * self.end
            return self.end if et >= 0.5 else self.start

        if self.kind == 'text':
            return self.end if et >= 0.5 else self.start

        # 'discrete' — snap at eased half
        return self.end if et >= 0.5 else self.start


class CameraInterpolator:
    """Interpolates the ``@camera`` pseudo-element between two keyframes.

    ``start``/``end`` are partial ``{center?, width?}`` dicts (fields
    absent from both endpoints stay absent in the result — the scene
    treats an absent field as "keep the current frame value").
    """
    __slots__ = ('start', 'end', 'easing')

    def __init__(self, start, end, easing=None):
        self.start = start
        self.end = end
        self.easing = easing or _ease_smooth

    def at(self, t):
        et = self.easing(t)
        out = {}
        if 'center' in self.start and 'center' in self.end:
            s, e = self.start['center'], self.end['center']
            out['center'] = [(1 - et) * s[0] + et * e[0], (1 - et) * s[1] + et * e[1]]
        elif 'center' in self.end:
            out['center'] = list(self.end['center'])
        if 'width' in self.start and 'width' in self.end:
            out['width'] = (1 - et) * self.start['width'] + et * self.end['width']
        elif 'width' in self.end:
            out['width'] = self.end['width']
        return out


def _interpolate_angle(start, end, t, direction='short'):
    """Interpolate angle in radians, respecting direction."""
    TWO_PI = 2 * np.pi

    if direction == 'short':
        diff = (end - start) % TWO_PI
        if diff > np.pi:
            diff -= TWO_PI
        return start + t * diff

    if direction == 'ccw':
        diff = (end - start) % TWO_PI
        return start + t * diff

    if direction == 'cw':
        diff = (start - end) % TWO_PI
        return start - t * diff

    return (1 - t) * start + t * end

#--------------------------------------------------------------------------
# Keyframe data structures
#--------------------------------------------------------------------------

def _normalize_effect(name, spec, valid_effects, phase_kw):
    """Normalize an enter/exit effect spec to {'effect','duration','at'}.

    ``spec`` may be a bare effect string ('fade') or a dict. Validates the
    effect name against ``valid_effects``.
    """
    if isinstance(spec, str):
        spec = {'effect': spec}
    if not isinstance(spec, dict):
        raise ValueError(f"{phase_kw}['{name}'] must be an effect name or object, got {spec!r}")
    effect = spec.get('effect', 'fade')
    if effect not in valid_effects:
        raise ValueError(
            f"{phase_kw}['{name}']: unknown {phase_kw} effect '{effect}'; "
            f"valid: {valid_effects}"
        )
    duration = float(spec.get('duration', DEFAULT_EFFECT_DURATION))
    at = float(spec.get('at', 0.0))
    return {'effect': effect, 'duration': duration, 'at': at}


def _validate_default_effect(spec, valid_effects, phase_kw):
    """Validate a top-level ``defaults.enter``/``defaults.exit`` spec.

    Unlike ``_normalize_effect`` (per-keyframe specs, always resolved to a
    complete ``{'effect', 'duration', 'at'}`` dict ready for playback),
    top-level defaults are a settings template: only the fields the caller
    actually provided are validated and stored, so ``defaults.enter`` echoes
    back exactly what was configured (missing fields fall back to
    ``DEFAULT_EFFECT_DURATION`` / ``at=0.0`` wherever a default is applied
    downstream, not baked in here).
    """
    if isinstance(spec, str):
        spec = {'effect': spec}
    if not isinstance(spec, dict):
        raise ValueError(f"defaults.{phase_kw} must be an effect name or object, got {spec!r}")
    effect = spec.get('effect', 'fade')
    if effect not in valid_effects:
        raise ValueError(
            f"defaults.{phase_kw}: unknown {phase_kw} effect '{effect}'; "
            f"valid: {valid_effects}"
        )
    return {**spec, 'effect': effect}


def _normalize_camera(spec, kf_index):
    """Validate and normalize an ``@camera`` spec to ``{center?, width?}``."""
    if not isinstance(spec, dict):
        raise ValueError(f"Keyframe {kf_index}: '@camera' must be an object, got {spec!r}")
    out = {}
    if 'center' in spec:
        c = spec['center']
        if (not isinstance(c, (list, tuple)) or len(c) != 2
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in c)):
            raise ValueError(f"Keyframe {kf_index}: '@camera' center must be [x, y] numbers, got {c!r}")
        out['center'] = [float(c[0]), float(c[1])]
    if 'width' in spec:
        w = spec['width']
        if isinstance(w, bool) or not isinstance(w, (int, float)) or w <= 0:
            raise ValueError(f"Keyframe {kf_index}: '@camera' width must be a positive number, got {w!r}")
        out['width'] = float(w)
    return out


def _normalize_event(spec, kf_index, construction):
    """Validate and normalize one per-keyframe ``events[]`` entry.

    Rejects unknown effects, the not-yet-implemented ``passing_flash``, and
    non-existent targets. Returns a plain dict (not ``EventSpec`` — the
    interval-relative ``start``/``duration`` clamping happens later in
    ``_build_intervals``, since this dict's ``at``/``duration`` are still
    keyframe-relative).
    """
    if not isinstance(spec, dict):
        raise ValueError(f"Keyframe {kf_index}: each event must be an object, got {spec!r}")
    effect = spec.get('effect', 'indicate')
    if effect == 'passing_flash':
        raise ValueError(
            f"Keyframe {kf_index}: 'passing_flash' event is not available yet")
    if effect not in EVENT_EFFECTS:
        raise ValueError(
            f"Keyframe {kf_index}: unknown event effect '{effect}'; valid: {EVENT_EFFECTS}")
    targets = spec.get('targets', [])
    if not isinstance(targets, (list, tuple)) or not targets:
        raise ValueError(f"Keyframe {kf_index}: event 'targets' must be a non-empty list")
    for name in targets:
        if construction.element(name) is None:
            raise ValueError(f"Keyframe {kf_index}: event target '{name}' not found")
    color = spec.get('color')
    if color is not None:
        color = normalize_hex(color)
    return {
        'effect': effect, 'targets': list(targets),
        'at': float(spec.get('at', 0.0)), 'duration': float(spec.get('duration', 0.6)),
        'color': color, 'scale': float(spec.get('scale', 1.2)),
    }


class Keyframe:
    """A single keyframe at time t."""
    __slots__ = ('t', 'values', 'show', 'hide', 'easing_name', 'styles',
                 'visible', 'enter', 'exit', 'camera', 'events')

    def __init__(self, t, values=None, show=None, hide=None, easing_name='smooth',
                 styles=None, visible=None, enter=None, exit=None, camera=None,
                 events=None):
        self.t = float(t)
        self.values = values or {}     # name -> value (raw from JSON)
        self.show = show or []
        self.hide = hide or []
        self.easing_name = easing_name
        self.styles = styles or {}     # name -> {style_key -> normalized value}
        self.visible = visible or {}   # name -> bool (absolute)
        self.enter = enter or {}       # name -> {'effect','duration','at'}
        self.exit = exit or {}         # name -> {'effect','duration','at'}
        self.camera = camera or {}     # {'center': [x, y], 'width': w} (partial)
        self.events = events or []     # list of normalized event dicts


class KeyframeInterval:
    """Interval between two adjacent keyframes with computed interpolators.

    ``label_interps`` and ``dynamic_angle_params`` are populated by
    ``KeyframeSequence.attach_label_layouts`` when keyframe-snapshot label
    placement is enabled. Empty by default.
    """
    __slots__ = ('start_t', 'end_t', 'duration', 'interpolators',
                 'show', 'hide', 'label_interps', 'dynamic_angle_params',
                 'easing_name', 'style_interps', 'style_finalizers',
                 'enter_effects', 'exit_effects', 'camera_interp', 'events')

    def __init__(self, start_t, end_t, interpolators, show=None, hide=None,
                 easing_name='smooth'):
        self.start_t = start_t
        self.end_t = end_t
        self.duration = end_t - start_t
        self.interpolators = interpolators
        self.show = show or []
        self.hide = hide or []
        self.easing_name = easing_name
        self.label_interps = []          # list[LabelOffsetInterpolator]
        self.dynamic_angle_params = {}   # dict[name, AngleParams]
        self.style_interps = []          # list[StyleInterpolator]
        self.style_finalizers = []       # ('set', name, key, value) | ('revert', name, key, had_explicit, explicit_val)
        self.enter_effects = []          # list[EffectSpec]
        self.exit_effects = []           # list[EffectSpec]
        self.camera_interp = None        # Optional[CameraInterpolator]
        self.events = []                 # list[EventSpec]


class KeyframeSequence:
    """Parsed and validated sequence of keyframes ready for playback."""

    def __init__(self, keyframes, intervals, element_info, version=1, defaults=None):
        self.keyframes = keyframes           # List[Keyframe]
        self.intervals = intervals           # List[KeyframeInterval]
        self.element_info = element_info     # dict from get_independents()
        self.version = version
        self.defaults = defaults or {}        # {'easing', 'enter', 'exit'}
        self.label_layouts = None            # Optional[list[dict[name, LabelPlacement]]]
        self.initial_visibility = {}         # dict[name, bool] from keyframe 0

    def has_style_tracks(self):
        """True if any keyframe carries a ``styles`` map."""
        return any(kf.styles for kf in self.keyframes)

    def has_visibility_effects(self):
        return any(iv.enter_effects or iv.exit_effects for iv in self.intervals)

    def has_events(self):
        return any(iv.events for iv in self.intervals)

    def bind_visibility(self, get_element=None):
        """Compile per-interval enter/exit EffectSpec lists from carry-forward
        visibility. Records keyframe-0 visibility in ``self.initial_visibility``.
        """
        DEFAULT_ENTER = self.defaults.get('enter', {'effect': 'fade', 'duration': DEFAULT_EFFECT_DURATION, 'at': 0.0})
        DEFAULT_EXIT = self.defaults.get('exit', {'effect': 'fade', 'duration': DEFAULT_EFFECT_DURATION, 'at': 0.0})

        self.initial_visibility = dict(self.keyframes[0].visible)
        running = dict(self.keyframes[0].visible)

        for i, interval in enumerate(self.intervals):
            interval.enter_effects = []
            interval.exit_effects = []
            kf = self.keyframes[i + 1]
            dur = interval.duration
            for name, new_vis in kf.visible.items():
                if name not in running:
                    elem = get_element(name) if get_element is not None else None
                    running[name] = bool(elem.visible) if elem is not None else True
                prev = running.get(name)
                running[name] = new_vis
                if prev == new_vis:
                    continue
                if dur <= 0:
                    continue
                if new_vis:      # entrance
                    spec = kf.enter.get(name, DEFAULT_ENTER)
                    at = min(max(float(spec.get('at', 0.0)), 0.0), dur)
                    edur = min(float(spec.get('duration', DEFAULT_EFFECT_DURATION)), dur - at)
                    interval.enter_effects.append(EffectSpec(
                        name=name, kind=spec['effect'], start=at,
                        duration=max(edur, 0.0), direction='in'))
                else:            # exit
                    spec = kf.exit.get(name, DEFAULT_EXIT)
                    at = min(max(float(spec.get('at', 0.0)), 0.0), dur)
                    edur = min(float(spec.get('duration', DEFAULT_EFFECT_DURATION)), dur - at)
                    interval.exit_effects.append(EffectSpec(
                        name=name, kind=spec['effect'], start=at,
                        duration=max(edur, 0.0), direction='out'))

    def attach_label_layouts(self, layouts):
        """Populate each interval with label interpolators from per-keyframe layouts.

        ``layouts[i]`` must correspond to ``self.keyframes[i]``. For each
        interval, static labels present at both endpoints get a
        ``LabelOffsetInterpolator``; dynamic-angle labels get an
        ``AngleParams`` entry (they skip offset interpolation — their offset
        is recomputed each frame from the live bisector).
        """
        if len(layouts) != len(self.keyframes):
            raise ValueError(
                f"attach_label_layouts: expected {len(self.keyframes)} layouts, "
                f"got {len(layouts)}"
            )
        self.label_layouts = list(layouts)

        for i, interval in enumerate(self.intervals):
            start_layout = layouts[i] or {}
            end_layout = layouts[i + 1] or {}
            easing_fn = EASING_FUNCTIONS[interval.easing_name]

            interval.label_interps = []
            interval.dynamic_angle_params = {}

            for name, end_pl in end_layout.items():
                if end_pl.kind == 'dynamic_angle':
                    interval.dynamic_angle_params[name] = end_pl.angle_params
                    continue
                start_pl = start_layout.get(name)
                # Label not placed at the start keyframe (element or label
                # hidden there): it appears during this interval, so it must
                # appear already placed — hold the end-keyframe offset for the
                # whole interval. Skipping left it at the unplaced default
                # (a segment label on the middle of its line) until the next
                # interval moved it.
                start_offset = end_pl.offset_ggb if start_pl is None else start_pl.offset_ggb
                interval.label_interps.append(LabelOffsetInterpolator(
                    name=name,
                    start_offset=start_offset,
                    end_offset=end_pl.offset_ggb,
                    easing=easing_fn,
                ))

    def drop_style_key(self, key):
        """Remove every style track (interpolators and finalizers) for *key*.

        For keys another mechanism owns during playback — label offsets once
        keyframe label snapshots are attached."""
        for interval in self.intervals:
            interval.style_interps = [
                si for si in getattr(interval, 'style_interps', []) if si.key != key]
            interval.style_finalizers = [
                fin for fin in getattr(interval, 'style_finalizers', []) if fin[2] != key]

    def bind_style_tracks(self, get_element, resolve, color_space='oklab'):
        """Compile per-keyframe ``styles`` into per-interval style tracks.

        Args:
            get_element: callable ``name -> Element | None``.
            resolve: callable ``(elem, key) -> current resolved value | None``
                (the scene passes the style resolver; keyframes.py stays
                manim-free by taking it as an injected function).
            color_space: 'oklab' | 'srgb' for color lerp.

        MUST be called before the first keyframe's styles are applied:
        baselines (revert targets and lazy track starts) are captured from
        the pre-animation state. Re-binding replaces previous tracks.
        """
        baseline = {}   # (name, key) -> resolved value at sequence start
        restore = {}    # (name, key) -> (had_explicit, explicit_val)
        current = {}    # (name, key) -> tracked value along the timeline

        def _ensure_baseline(name, key):
            k = (name, key)
            if k in baseline:
                return True
            elem = get_element(name)
            if elem is None:
                logger.warning(
                    "bind_style_tracks: element '%s' not found — skipping "
                    "style track '%s'", name, key,
                )
                return False
            baseline[k] = resolve(elem, key)
            restore[k] = (key in elem.style, elem.style.get(key))
            return True

        # Keyframe 0 styles are applied instantly before playback
        # (_apply_keyframe_state); here they only seed the tracked value.
        for name, props in self.keyframes[0].styles.items():
            for key, value in props.items():
                if not _ensure_baseline(name, key):
                    continue
                if value is not None:
                    current[(name, key)] = value

        for i, interval in enumerate(self.intervals):
            kf_next = self.keyframes[i + 1]
            easing_fn = EASING_FUNCTIONS[interval.easing_name]
            interval.style_interps = []
            interval.style_finalizers = []

            for name, props in kf_next.styles.items():
                for key, value in props.items():
                    if not _ensure_baseline(name, key):
                        continue
                    k = (name, key)
                    start = current.get(k, baseline[k])
                    end = baseline[k] if value is None else value
                    had_explicit, explicit_val = restore[k]

                    if value is None:
                        interval.style_finalizers.append(
                            ('revert', name, key, had_explicit, explicit_val))
                    else:
                        interval.style_finalizers.append(
                            ('set', name, key, end))

                    if start != end:
                        kind = style_kind(key)
                        if start is None or end is None:
                            kind = 'discrete'   # cannot lerp from/to nothing
                        elif kind == 'color' and not (is_hex_color(start) and is_hex_color(end)):
                            kind = 'discrete'   # non-hex colour (named/rgb) — snap instead of lerp
                        interval.style_interps.append(StyleInterpolator(
                            name=name, key=key, kind=kind,
                            start=start, end=end, easing=easing_fn,
                            color_space=color_space,
                        ))
                    current[k] = end

    @classmethod
    def from_json(cls, data, construction):
        """Parse keyframe JSON and validate against the construction.

        Args:
            data: dict with 'keyframes' key (list of keyframe dicts)
            construction: Construction instance to validate against

        Returns:
            KeyframeSequence ready for playback

        Raises:
            ValueError: on validation errors
        """
        raw_keyframes = data.get('keyframes')
        if not raw_keyframes or len(raw_keyframes) < 2:
            raise ValueError("At least 2 keyframes are required")

        version = data.get('version', 1)
        if version not in (1, 2):
            raise ValueError(
                f"Unsupported keyframes JSON version {version!r}; expected 1 or 2"
            )
        if version == 1:
            warnings.warn(
                "keyframes JSON without '\"version\": 2' uses the deprecated v1 "
                "schema. Add '\"version\": 2' to opt into the v2 schema "
                "(per-keyframe 'styles'; future v2 visibility/timing semantics).",
                DeprecationWarning, stacklevel=2,
            )

        raw_defaults = data.get('defaults', {})
        defaults = {}
        if raw_defaults:
            if version < 2:
                raise ValueError("'defaults' requires '\"version\": 2'")
            defaults['easing'] = raw_defaults.get('easing', 'smooth')
            if defaults['easing'] not in EASING_FUNCTIONS:
                raise ValueError(
                    f"defaults.easing: unknown easing '{defaults['easing']}', "
                    f"available: {list(EASING_FUNCTIONS.keys())}")
            if 'enter' in raw_defaults:
                defaults['enter'] = _validate_default_effect(
                    raw_defaults['enter'], ENTER_EFFECTS, 'enter')
            if 'exit' in raw_defaults:
                defaults['exit'] = _validate_default_effect(
                    raw_defaults['exit'], EXIT_EFFECTS, 'exit')

        # Get independent elements from construction
        element_info = construction.get_independents()

        # Parse keyframes
        keyframes = []
        for i, kf_data in enumerate(raw_keyframes):
            if 't' not in kf_data:
                raise ValueError(f"Keyframe {i}: missing 't' (time)")

            values = dict(kf_data.get('values', {}))   # copy so we can pop @camera
            camera = {}
            if CAMERA_KEY in values:
                if version < 2:
                    raise ValueError(f"Keyframe {i}: '@camera' requires '\"version\": 2'")
                camera = _normalize_camera(values.pop(CAMERA_KEY), i)

            show = kf_data.get('show', [])
            hide = kf_data.get('hide', [])
            easing = kf_data.get('easing', defaults.get('easing', 'smooth'))

            if easing not in EASING_FUNCTIONS:
                raise ValueError(f"Keyframe {i}: unknown easing '{easing}', "
                                 f"available: {list(EASING_FUNCTIONS.keys())}")

            # Validate value names
            for name in values:
                if name not in element_info:
                    raise ValueError(
                        f"Keyframe {i}: '{name}' is not an independent element. "
                        f"Available: {list(element_info.keys())}"
                    )

            # Validate show/hide names
            for name in show + hide:
                if construction.element(name) is None:
                    raise ValueError(f"Keyframe {i}: element '{name}' not found in construction")

            raw_styles = kf_data.get('styles', {})
            if raw_styles and version < 2:
                raise ValueError(
                    f"Keyframe {i}: 'styles' requires '\"version\": 2'"
                )
            styles = {}
            for ename, props in raw_styles.items():
                if construction.element(ename) is None:
                    raise ValueError(
                        f"Keyframe {i}: styles target '{ename}' not found in construction"
                    )
                if not isinstance(props, dict):
                    raise ValueError(
                        f"Keyframe {i}: styles['{ename}'] must be an object "
                        f"{{style_key: value}}, got {props!r}"
                    )
                try:
                    styles[ename] = {
                        key: normalize_style_value(key, value)
                        for key, value in props.items()
                    }
                except ValueError as e:
                    raise ValueError(f"Keyframe {i}: styles['{ename}']: {e}") from None

            raw_visible = kf_data.get('visible', {})
            raw_enter = kf_data.get('enter', {})
            raw_exit = kf_data.get('exit', {})
            if (raw_visible or raw_enter or raw_exit) and version < 2:
                raise ValueError(
                    f"Keyframe {i}: 'visible'/'enter'/'exit' require '\"version\": 2'"
                )
            visible = {}
            # show/hide sugar folds into the absolute visible map (v2)
            for nm in show:
                visible[nm] = True
            for nm in hide:
                visible[nm] = False
            for nm, val in raw_visible.items():
                visible[nm] = bool(val)
            for nm in visible:
                if construction.element(nm) is None:
                    raise ValueError(
                        f"Keyframe {i}: visibility target '{nm}' not found in construction"
                    )
            enter = {nm: _normalize_effect(nm, spec, ENTER_EFFECTS, 'enter')
                     for nm, spec in raw_enter.items()}
            exit_ = {nm: _normalize_effect(nm, spec, EXIT_EFFECTS, 'exit')
                     for nm, spec in raw_exit.items()}
            for nm in list(enter) + list(exit_):
                if construction.element(nm) is None:
                    raise ValueError(
                        f"Keyframe {i}: enter/exit target '{nm}' not found in construction"
                    )

            raw_events = kf_data.get('events', [])
            if raw_events and version < 2:
                raise ValueError(f"Keyframe {i}: 'events' requires '\"version\": 2'")
            events = [_normalize_event(ev, i, construction) for ev in raw_events]

            keyframes.append(Keyframe(
                t=kf_data['t'],
                values=values,
                show=show,
                hide=hide,
                easing_name=easing,
                styles=styles,
                visible=visible,
                enter=enter,
                exit=exit_,
                camera=camera,
                events=events,
            ))

        # Sort by time
        keyframes.sort(key=lambda kf: kf.t)

        # Check no duplicate times
        for i in range(1, len(keyframes)):
            if keyframes[i].t <= keyframes[i-1].t:
                raise ValueError(
                    f"Keyframe times must be strictly increasing: "
                    f"t={keyframes[i-1].t} and t={keyframes[i].t}"
                )

        # Build intervals
        intervals = _build_intervals(keyframes, element_info, construction)

        return cls(keyframes, intervals, element_info, version=version, defaults=defaults)


# Interpolation kind per path constraint. Closed paths (circle, ellipse)
# interpolate cyclically with 2*pi wrap; a hyperbola keeps its branch and
# lerps the scalar part; everything else (incl. 'unknown') lerps linearly.
_TPARAM_CYCLIC = frozenset({'circle', 'ellipse'})


def _tparam_kind(constraint):
    if constraint in _TPARAM_CYCLIC:
        return 'tparam_circle'
    if constraint == 'hyperbola':
        return 'tparam_hyperbola'
    return 'tparam_linear'


def _parse_value(name, raw_value, info, construction=None):
    """Convert raw JSON value to internal representation.

    Returns (kind, parsed_value, angle_direction).

    ``construction`` enables the ``[x, y]`` form for tparam points: the
    coordinates are projected onto the point's path via
    ``Construction.tparam_from_coords``.
    """
    etype = info['type']

    if etype == 'free_point':
        if not isinstance(raw_value, (list, tuple)) or len(raw_value) != 2:
            raise ValueError(f"'{name}': free_point requires [x, y], got {raw_value}")
        return 'point', np.array(raw_value, dtype=float), None

    if etype == 'free_text':
        if not isinstance(raw_value, (list, tuple)) or len(raw_value) != 2:
            raise ValueError(f"'{name}': free_text requires [x, y], got {raw_value}")
        return 'text_position', np.array(raw_value, dtype=float), None

    if etype == 'tparam_point':
        constraint = info.get('constraint', 'line')
        kind = _tparam_kind(constraint)
        if isinstance(raw_value, dict):
            tparam = raw_value.get('tparam')
            direction = raw_value.get('direction', 'short')
            if tparam is None:
                raise ValueError(
                    f"'{name}': tparam_point dict requires 'tparam' key"
                )
            if isinstance(tparam, (list, tuple)):      # hyperbola [branch, t]
                tparam = (float(tparam[0]), float(tparam[1]))
            else:
                tparam = float(tparam)
            return kind, tparam, direction
        if (isinstance(raw_value, (list, tuple)) and len(raw_value) == 2
                and all(isinstance(v, (int, float)) for v in raw_value)):
            if construction is None:
                raise ValueError(
                    f"'{name}': [x, y] for a tparam_point needs the "
                    f"construction — pass keyframes through "
                    f"KeyframeSequence.from_json / play_keyframes"
                )
            tparam = construction.tparam_from_coords(name, list(raw_value))
            if tparam is None:
                raise ValueError(
                    f"'{name}': could not project {raw_value} onto the path"
                )
            return kind, tparam, 'short'
        raise ValueError(
            f"'{name}': tparam_point requires {{\"tparam\": value}} or [x, y], "
            f"got {raw_value}"
        )

    if etype in ('number', 'measure'):
        return 'var', float(raw_value), None

    if etype == 'angle':
        return 'var', float(raw_value), None

    if etype == 'boolean':
        return 'bool', bool(raw_value), None

    raise ValueError(f"'{name}': unsupported element type '{etype}'")


def apply_parsed_value(construction, name, kind, val):
    """Apply one parsed keyframe/interpolator value to a construction.

    This helper deliberately has no Manim dependency, so scene playback,
    keyframe snapshot pre-passes, and tests can share exactly the same value
    semantics.
    """
    if kind == 'point':
        construction.update(name, Point(val))
        return

    if kind == 'text_position':
        elem = construction.element(name)
        data = getattr(elem, 'data', None) if elem is not None else None
        if data is not None and hasattr(data, 'position'):
            data.position = np.array(val, dtype=float)
            _mark_var_outputs_dirty(construction, name)
        return

    if kind in ('tparam_circle', 'tparam_linear', 'tparam_hyperbola'):
        construction.update_tparam(name, val)
        return

    var = construction.var(name)
    if kind == 'bool':
        if var and isinstance(var.data, Boolean):
            var.data.value = bool(val)
            _mark_var_outputs_dirty(construction, name)
        else:
            construction.update(name, bool(val))
        return

    # 'var' — number, measure, angle
    if var:
        # Measure and AngleSize expose the numeric value as ``.value``. Writing
        # another attribute would not affect dependent commands.
        if isinstance(var.data, (Measure, AngleSize)):
            var.data.value = float(val)
        else:
            var.data = float(val)
        _mark_var_outputs_dirty(construction, name)
    else:
        construction.update(name, float(val))


def _mark_var_outputs_dirty(construction, name):
    state = construction.state.get(name)
    if state is None:
        return
    state['built'] = True
    for out in state['outputs']:
        construction.state[out]['built'] = False


def _build_intervals(keyframes, element_info, construction=None):
    """Build KeyframeInterval list from parsed keyframes."""
    intervals = []

    # Track current values: start from first keyframe's values
    # For values not specified in a keyframe, carry forward from previous
    current_values = {}  # name -> (kind, value, direction)

    # Initialize from first keyframe
    for name, raw_value in keyframes[0].values.items():
        info = element_info[name]
        current_values[name] = _parse_value(name, raw_value, info, construction)

    running_camera = dict(keyframes[0].camera)

    for i in range(1, len(keyframes)):
        kf_prev = keyframes[i - 1]
        kf_next = keyframes[i]
        easing_fn = EASING_FUNCTIONS[kf_next.easing_name]

        # Parse target values for this keyframe
        target_values = {}
        for name, raw_value in kf_next.values.items():
            info = element_info[name]
            target_values[name] = _parse_value(name, raw_value, info, construction)

        # Build interpolators for values that change
        interpolators = []
        for name, (kind, end_val, direction) in target_values.items():
            if name in current_values:
                _, start_val, _ = current_values[name]
            else:
                # Value first appears — use construction's current value as start
                info = element_info[name]
                start_val = _get_current_value(info)

            # Skip if value hasn't changed (for non-bool types)
            if kind == 'tparam_hyperbola':
                b0, t0 = Interpolator._hyperbola_pair(start_val)
                b1, t1 = Interpolator._hyperbola_pair(end_val)
                if b0 == b1 and np.isclose(t0, t1):
                    current_values[name] = (kind, end_val, direction)
                    continue
            elif kind != 'bool' and kind not in ('point', 'text_position'):
                if np.isclose(start_val, end_val):
                    current_values[name] = (kind, end_val, direction)
                    continue
            elif kind in ('point', 'text_position'):
                if np.allclose(start_val, end_val):
                    current_values[name] = (kind, end_val, direction)
                    continue

            interp = Interpolator(
                name=name,
                kind=kind,
                start=start_val,
                end=end_val,
                easing=easing_fn,
                angle_direction=direction or 'short',
            )
            interpolators.append(interp)
            current_values[name] = (kind, end_val, direction)

        interval = KeyframeInterval(
            start_t=kf_prev.t,
            end_t=kf_next.t,
            interpolators=interpolators,
            show=kf_next.show,
            hide=kf_next.hide,
            easing_name=kf_next.easing_name,
        )

        if kf_next.camera:
            camera_start = dict(running_camera)
            running_camera.update(kf_next.camera)
            interval.camera_interp = CameraInterpolator(
                camera_start, dict(running_camera), easing_fn)

        for ev in kf_next.events:
            dur = interval.duration
            if dur <= 0:
                continue
            at = min(max(ev['at'], 0.0), dur)
            edur = min(ev['duration'], dur - at)
            if edur <= 0:
                continue
            interval.events.append(EventSpec(
                effect=ev['effect'], targets=ev['targets'], start=at,
                duration=edur, color=ev['color'], scale=ev['scale']))

        intervals.append(interval)

    return intervals


def build_reveal_keyframes(names_in_order, type_effects=None, lag=0.3,
                            duration=0.5, default_effect='fade'):
    """Build a 2-keyframe v2 sequence that reveals *names_in_order* one by one,
    staggered by *lag* seconds, each with its per-name effect (from
    *type_effects*, else *default_effect*).
    """
    type_effects = type_effects or {}
    names = list(names_in_order)
    hidden = {n: False for n in names}
    shown = {n: True for n in names}
    enter = {}
    for i, n in enumerate(names):
        enter[n] = {'effect': type_effects.get(n, default_effect),
                    'duration': float(duration), 'at': float(i * lag)}
    total = (len(names) - 1) * lag + duration if names else duration
    return {'version': 2, 'keyframes': [
        {'t': 0, 'visible': hidden},
        {'t': float(total), 'visible': shown, 'enter': enter},
    ]}


def _get_current_value(info):
    """Extract current value from element_info dict."""
    etype = info['type']
    if etype == 'free_point':
        return np.array(info['coords'], dtype=float)
    if etype == 'free_text':
        return np.array(info['position'], dtype=float)
    if etype == 'tparam_point':
        t = info['tparam']
        if isinstance(t, (list, tuple)):
            return (float(t[0]), float(t[1]))
        return float(t)
    if etype in ('number', 'measure', 'angle'):
        return float(info['value'])
    if etype == 'boolean':
        return bool(info['value'])
    raise ValueError(f"Cannot get current value for type '{etype}'")
