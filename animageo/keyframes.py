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
import numpy as np
from .geo.lib_elements import Point, Line, Segment, Ray, Circle
from .geo.lib_vars import Measure, AngleSize, Boolean

logger = logging.getLogger(__name__)

#--------------------------------------------------------------------------
# Easing functions (matching manim rate_functions)
#--------------------------------------------------------------------------

def _ease_linear(t):
    return t

def _ease_smooth(t):
    # manim smooth: 3t^2 - 2t^3
    return 3 * t**2 - 2 * t**3

def _ease_in(t):
    return t**2

def _ease_out(t):
    return 1 - (1 - t)**2

def _ease_in_out(t):
    if t < 0.5:
        return 2 * t**2
    return 1 - 2 * (1 - t)**2

EASING_FUNCTIONS = {
    'linear': _ease_linear,
    'smooth': _ease_smooth,
    'in': _ease_in,
    'out': _ease_out,
    'in_out': _ease_in_out,
}

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

        if self.kind == 'point':
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

class Keyframe:
    """A single keyframe at time t."""
    __slots__ = ('t', 'values', 'show', 'hide', 'easing_name')

    def __init__(self, t, values=None, show=None, hide=None, easing_name='smooth'):
        self.t = float(t)
        self.values = values or {}     # name -> value (raw from JSON)
        self.show = show or []
        self.hide = hide or []
        self.easing_name = easing_name


class KeyframeInterval:
    """Interval between two adjacent keyframes with computed interpolators.

    ``label_interps`` and ``dynamic_angle_params`` are populated by
    ``KeyframeSequence.attach_label_layouts`` when keyframe-snapshot label
    placement is enabled. Empty by default.
    """
    __slots__ = ('start_t', 'end_t', 'duration', 'interpolators',
                 'show', 'hide', 'label_interps', 'dynamic_angle_params',
                 'easing_name')

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


class KeyframeSequence:
    """Parsed and validated sequence of keyframes ready for playback."""

    def __init__(self, keyframes, intervals, element_info):
        self.keyframes = keyframes           # List[Keyframe]
        self.intervals = intervals           # List[KeyframeInterval]
        self.element_info = element_info     # dict from get_independents()
        self.label_layouts = None            # Optional[list[dict[name, LabelPlacement]]]

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
                if start_pl is None:
                    # Label wasn't placed at start keyframe (element hidden
                    # at that keyframe). Skip interpolation — the label
                    # appears at `show` time with its end-keyframe offset.
                    continue
                interval.label_interps.append(LabelOffsetInterpolator(
                    name=name,
                    start_offset=start_pl.offset_ggb,
                    end_offset=end_pl.offset_ggb,
                    easing=easing_fn,
                ))

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

        # Get independent elements from construction
        element_info = construction.get_independents()

        # Parse keyframes
        keyframes = []
        for i, kf_data in enumerate(raw_keyframes):
            if 't' not in kf_data:
                raise ValueError(f"Keyframe {i}: missing 't' (time)")

            values = kf_data.get('values', {})
            show = kf_data.get('show', [])
            hide = kf_data.get('hide', [])
            easing = kf_data.get('easing', 'smooth')

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

            keyframes.append(Keyframe(
                t=kf_data['t'],
                values=values,
                show=show,
                hide=hide,
                easing_name=easing,
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

        return cls(keyframes, intervals, element_info)


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
            elif kind != 'bool' and kind != 'point':
                if np.isclose(start_val, end_val):
                    current_values[name] = (kind, end_val, direction)
                    continue
            elif kind == 'point':
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

        intervals.append(KeyframeInterval(
            start_t=kf_prev.t,
            end_t=kf_next.t,
            interpolators=interpolators,
            show=kf_next.show,
            hide=kf_next.hide,
            easing_name=kf_next.easing_name,
        ))

    return intervals


def _get_current_value(info):
    """Extract current value from element_info dict."""
    etype = info['type']
    if etype == 'free_point':
        return np.array(info['coords'], dtype=float)
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
