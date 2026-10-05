"""Easing functions of keyframe animation (a leaf module: pure math).

``EASING_FUNCTIONS[name](t)`` maps the progress ``t ∈ [0, 1]`` of an interval
to the eased progress. The names and formulas are those of the keyframe JSON
(``animageo/keyframes.py``, manim rate functions); ``animageo.native``
samples timelines with the same functions (``native.sample_timeline``), and
the web's TypeScript kernel repeats them. Moved here from ``keyframes.py`` in
1.9.0a4 with bitwise the same values; ``keyframes.py`` re-exports them.
"""

import math

__all__ = ['EASING_FUNCTIONS', 'ease']


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


def _clamp01(t):
    return 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)


def _ease_smootherstep(t):
    t = _clamp01(t)
    return 6 * t**5 - 15 * t**4 + 10 * t**3


def _ease_in_sine(t):
    t = _clamp01(t)
    return 1 - math.cos((t * math.pi) / 2)


def _ease_out_sine(t):
    t = _clamp01(t)
    return math.sin((t * math.pi) / 2)


def _ease_in_out_sine(t):
    t = _clamp01(t)
    return -(math.cos(math.pi * t) - 1) / 2


def _ease_in_cubic(t):
    t = _clamp01(t)
    return t * t * t


def _ease_out_cubic(t):
    t = _clamp01(t)
    return 1 - (1 - t) ** 3


def _ease_in_out_cubic(t):
    t = _clamp01(t)
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def _manim_smooth_sigmoid(t, inflection=10.0):
    # animageo_web manimSmooth (sigmoid) — used by rush_into/rush_from
    error = 1 / (1 + math.exp(inflection / 2))
    return max(0.0, min(1.0, (
        1 / (1 + math.exp(-inflection * (t - 0.5))) - error
    ) / (1 - 2 * error)))


def _ease_rush_into(t):
    t = _clamp01(t)
    return 2 * _manim_smooth_sigmoid(t / 2)


def _ease_rush_from(t):
    t = _clamp01(t)
    return 2 * _manim_smooth_sigmoid(t / 2 + 0.5) - 1


def _ease_out_back(t):
    t = _clamp01(t)
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def _ease_out_elastic(t):
    t = _clamp01(t)
    if t == 0 or t == 1:
        return t
    c4 = (2 * math.pi) / 3
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * c4) + 1


def _ease_out_bounce(t):
    t = _clamp01(t)
    n1 = 7.5625
    d1 = 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


EASING_FUNCTIONS = {
    'linear': _ease_linear,
    'smooth': _ease_smooth,
    'in': _ease_in,
    'out': _ease_out,
    'in_out': _ease_in_out,
    'smootherstep': _ease_smootherstep,
    'ease_in_sine': _ease_in_sine,
    'ease_out_sine': _ease_out_sine,
    'ease_in_out_sine': _ease_in_out_sine,
    'ease_in_cubic': _ease_in_cubic,
    'ease_out_cubic': _ease_out_cubic,
    'ease_in_out_cubic': _ease_in_out_cubic,
    'rush_into': _ease_rush_into,
    'rush_from': _ease_rush_from,
    'ease_out_back': _ease_out_back,
    'ease_out_elastic': _ease_out_elastic,
    'ease_out_bounce': _ease_out_bounce,
}


def ease(name, t):
    """``EASING_FUNCTIONS[name](t)``; ``ValueError`` for an unknown name."""
    fn = EASING_FUNCTIONS.get(name)
    if fn is None:
        raise ValueError(f"unknown easing {name!r}; available: {list(EASING_FUNCTIONS)}")
    return fn(t)
