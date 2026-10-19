"""Axes and grid of the view (registry 1.6, ``viewDefaults.axes`` and
``viewDefaults.grid``; docs/native/view.md).

``viewDefaults.axes`` — ``{show?, numbers?, step?, labels?}``: ``show``
(default ``true`` — the object asks for the axes), ``numbers`` (default
``true``) — the numbers at the ticks, ``step`` — a positive number or
``null`` (automatic), ``labels`` — ``{x?, y?}`` the names at the ends of the
axes (default ``"x"``, ``"y"``; ``""`` — none). ``viewDefaults.grid`` —
``{kind?, step?}``: ``kind`` ``none`` | ``major`` | ``major_minor``
(default ``major``), ``step`` — a positive number or ``null`` (the step of
the axes).

The automatic step is :func:`nice_step` of ``max(w, h) / 10``, ``w, h`` the
sizes of ``viewDefaults.bounds`` (``defaultBounds`` without them): the
smallest of ``{1, 2, 5}·10^k`` not less than it. The minor grid divides a
major cell into :data:`MINOR_DIVISIONS`. Lines, ticks and numbers lie at
``k·step`` (``k`` an integer) inside the drawn rectangle; the x axis is
drawn when ``y = 0`` is inside it, the y axis when ``x = 0`` is; no tick,
number or grid line at ``0`` of a drawn axis. A document without axes and
grid (no keys, ``show: false``, ``kind: "none"``) draws nothing: its output
is byte for byte what it was before 1.6. Manim-free.
"""
from __future__ import annotations

import math

__all__ = ['GRID_KINDS', 'MINOR_DIVISIONS', 'VIEW_STYLE_KEYS', 'nice_step', 'view_layout', 'view_settings',
           'view_style']

GRID_KINDS = ('none', 'major', 'major_minor')
MINOR_DIVISIONS = 5
AUTO_STEP_DIVISIONS = 10
# a direction with more lines than this is thinned (the step times an integer)
MAX_LINES = 400
AXIS_LABEL_MAX = 32

# key of the ``rendering`` section of the style → (unit, the renderer's own
# default when the style has none); ``style_keys()["view"]``.
VIEW_STYLE_KEYS = {
    'axes_color': ('color', '#808080'), 'axes_width_px': ('px', 0.75), 'axes_opacity': ('opacity', 1),
    'axes_font_size_px': ('px', 10), 'axes_tick_length_px': ('px', 4),
    'grid_color': ('color', '#cccccc'), 'grid_width_px': ('px', 0.5), 'grid_opacity': ('opacity', 1),
    'grid_minor_width_px': ('px', 0.25), 'grid_minor_opacity': ('opacity', 0.6),
}


def view_style(rendering) -> dict:
    """The values of :data:`VIEW_STYLE_KEYS` in ``rendering`` (the resolved
    ``rendering`` section of a style), a bad or missing one by its default."""
    from ..style.colorspace import as_hex
    rendering = rendering if isinstance(rendering, dict) else {}
    out = {}
    for key, (unit, fallback) in VIEW_STYLE_KEYS.items():
        value = rendering.get(key, fallback)
        if unit == 'color':
            value = as_hex(value) or fallback
        else:
            try:
                value = float(value)
            except (TypeError, ValueError):
                value = float(fallback)
            if not (math.isfinite(value) and value >= 0):
                value = float(fallback)
            if unit == 'opacity':
                value = min(value, 1.0)
        out[key] = value
    return out


def nice_step(value: float) -> float:
    """The smallest of ``{1, 2, 5}·10^k`` not less than ``value`` (``> 0``)."""
    value = float(value)
    if not (math.isfinite(value) and value > 0):
        return 1.0
    k = math.floor(math.log10(value))
    for _ in range(3):
        base = 10.0 ** k
        for m in (1, 2, 5):
            step = m * base
            if step >= value * (1 - 1e-12):
                return float(f'{step:.12g}')
        k += 1
    return float(f'{10.0 ** k:.12g}')


def _step(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0:
        return float(value)
    return None


def view_settings(doc):
    """The axes and grid of ``doc`` with the defaults filled in, or ``None``
    when nothing is drawn: ``{axes: {show, numbers, step, labels: {x, y}},
    grid: {kind, step}}``, the steps resolved (automatic → :func:`nice_step`)."""
    from .document import as_document
    from .kernel.numeric import default_bounds
    doc = as_document(doc)
    view = doc.data.get('viewDefaults')
    if not isinstance(view, dict):
        return None
    axes = view.get('axes')
    grid = view.get('grid')
    axes = axes if isinstance(axes, dict) else None
    grid = grid if isinstance(grid, dict) else None
    show = bool(axes.get('show', True)) if axes is not None else False
    kind = grid.get('kind', 'major') if grid is not None else 'none'
    if kind not in GRID_KINDS:
        kind = 'none'
    if not show and kind == 'none':
        return None
    xmin, ymin, xmax, ymax = (float(v) for v in (doc.bounds or default_bounds()))
    auto = nice_step(max(xmax - xmin, ymax - ymin) / AUTO_STEP_DIVISIONS)
    axes_step = _step((axes or {}).get('step')) or auto
    labels = (axes or {}).get('labels')
    labels = labels if isinstance(labels, dict) else {}
    return {
        'axes': {
            'show': show,
            'numbers': bool((axes or {}).get('numbers', True)),
            'step': axes_step,
            'labels': {k: str(labels.get(k, k))[:AXIS_LABEL_MAX] for k in ('x', 'y')},
        },
        'grid': {'kind': kind, 'step': _step((grid or {}).get('step')) or axes_step},
    }


def _multiples(lo: float, hi: float, step: float) -> list:
    """``k·step`` in ``[lo, hi]``, ``k`` integer; thinned to :data:`MAX_LINES`."""
    first = math.ceil(lo / step - 1e-9)
    last = math.floor(hi / step + 1e-9)
    if first > last:
        return []
    every = max(1, math.ceil((last - first + 1) / MAX_LINES))
    if every > 1:
        first = math.ceil(first / every) * every
    return [round(k * step, 12) + 0.0 for k in range(first, last + 1, every)]


def number_text(value: float) -> str:
    """A tick number: ``2``, ``0.5``, ``−1.25`` (the minus sign U+2212)."""
    text = f'{value:.10g}'
    if 'e' in text:
        text = f'{value:.6g}'
    return text.replace('-', '−')


def view_layout(settings, rect, margin: float = 0.0) -> dict:
    """What to draw of ``settings`` (:func:`view_settings`) in ``rect`` =
    ``(left, bottom, right, top)`` (world units):

    ``{"grid": {"major": {"x": [...], "y": [...]}, "minor": {...}},
    "axes": {"x": bool, "y": bool}, "ticks": {"x": [...], "y": [...]},
    "numbers": {"x": [[value, text], ...], "y": [...]}, "labels": {"x":
    text or None, "y": ...}}``; grid ``x`` — the abscissas of the vertical
    lines, ``y`` — the ordinates of the horizontal ones; ticks and numbers
    of an axis that is not drawn are empty; no number closer than
    ``margin`` to the ends of its axis (it would be cut by the frame)."""
    left, bottom, right, top = (float(v) for v in rect)
    axes = settings['axes']
    grid = settings['grid']
    show = axes['show']
    draw_x = show and bottom <= 0 <= top
    draw_y = show and left <= 0 <= right
    out = {'grid': {'major': {'x': [], 'y': []}, 'minor': {'x': [], 'y': []}},
           'axes': {'x': draw_x, 'y': draw_y}, 'ticks': {'x': [], 'y': []},
           'numbers': {'x': [], 'y': []}, 'labels': {'x': None, 'y': None}}
    if grid['kind'] != 'none':
        step = grid['step']
        major_x = [x for x in _multiples(left, right, step) if not (draw_y and x == 0)]
        major_y = [y for y in _multiples(bottom, top, step) if not (draw_x and y == 0)]
        out['grid']['major'] = {'x': major_x, 'y': major_y}
        if grid['kind'] == 'major_minor':
            minor = step / MINOR_DIVISIONS
            for axis, lo, hi, drawn in (('x', left, right, draw_y), ('y', bottom, top, draw_x)):
                out['grid']['minor'][axis] = [
                    v for v in _multiples(lo, hi, minor)
                    if abs(v / step - round(v / step)) > 1e-9 and not (drawn and v == 0)]
    step = axes['step']
    for axis, lo, hi, drawn in (('x', left, right, draw_x), ('y', bottom, top, draw_y)):
        if not drawn:
            continue
        ticks = [v for v in _multiples(lo, hi, step) if v != 0]
        out['ticks'][axis] = ticks
        if axes['numbers']:
            out['numbers'][axis] = [[v, number_text(v)] for v in ticks if lo + margin <= v <= hi - margin]
        label = axes['labels'][axis]
        out['labels'][axis] = label or None
    return out
