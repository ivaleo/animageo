"""Time by element ID (1.9.0a4, plan L3 §5; docs/native/timeline.md).

A timeline is the keyframe JSON v2 of the classic library
(``animageo/keyframes.py``: ``t``, ``values``, ``show``, ``hide``,
``visible``, ``enter``, ``exit``, ``styles``, ``events``, ``easing``,
top-level ``defaults``) whose keys are element IDs of the document.

Values (``values.<id>``) by the free input kind of the element:

- ``point`` — ``[x, y]``;
- ``pathParameter`` — ``{"tparam": t, "direction": "short" | "long" | "cw" |
  "ccw"}`` in the parameter of ``point.on_path`` (``kernel/paths.py``);
- ``number`` — ``v``.

Other inputs (a free ``angle`` of ``segment.from_point_length``, a text
anchor) are not animatable: ``ValueError``. IDs not in the document are
skipped everywhere (a deleted element); ``@camera`` passes through.

``sample_timeline(doc, timeline, t)`` — without the classic code:

1. Keyframes are sorted by ``t`` (strictly increasing, at least one);
   ``t`` is clamped to ``[t_0, t_last]``.
2. Values carry forward: the value of ``id`` at keyframe ``k`` is its
   value in the last keyframe ``≤ k`` that has one, else the input of the
   document. In the interval ``[t_k, t_{k+1}]`` that holds ``t`` (the first
   such interval: at an inner keyframe time the interval that ends there),
   an ``id`` with a value in keyframe ``k+1`` goes from its value at ``k``
   to that value with ``p = (t − t_k)/(t_{k+1} − t_k)``, ``e = ease(p)``
   (the easing of keyframe ``k+1``, else ``defaults.easing``, else
   ``smooth``; ``animageo/easing.py``): a point and a number
   ``(1 − e)·s + e·v``; a path parameter on a wrapping path (circle — period
   ``2π``, polygon — ``n``, sector — ``3``) ``s + e·d`` with ``d`` by the
   direction of keyframe ``k+1``: ``r = (v − s) mod P``; ``short`` — ``r``
   if ``r ≤ P/2`` else ``r − P``; ``long`` — ``r − P`` if ``0 < r ≤ P/2``,
   ``r`` if ``r > P/2``, ``0`` if ``r = 0``; ``ccw`` — ``r``; ``cw`` —
   ``r − P`` if ``r > 0`` else ``0``; on other paths ``(1 − e)·s + e·v``.
   The value at keyframe ``k+1`` is then ``s + d`` (unwrapped).
3. Visibility carries forward (the formula of the web's
   ``keyframe_visibility_parity.json``): ``visible.<id>`` is the value of
   the last keyframe with ``t_k ≤ t`` that mentions ``id`` (``show``, then
   ``hide``, then ``visible`` of one keyframe), else
   ``appearance.<id>.visible`` (default ``true``).

The result: ``{"t": t, "inputs": {id: {"kind", "value"}}, "visible": {id:
bool}}`` — ``inputs`` for the animated elements only, in the format of
``evaluate(doc, inputs=…)``; ``visible`` for every element.

``timeline_to_bridge(doc, timeline)`` — the classic keyframe JSON of the
scene built by the bridge: IDs → ``e_<hex>`` (``kernel/bridge.py``), a path
parameter → the classic ``tparam`` (the bridge passes it to the kernel as
it is) unwrapped along the timeline as in step 2, with ``ccw`` for
``d > 0`` and ``cw`` for ``d < 0``: the classic interpolation then gives the
same values on every path (``|d| < 2π``). Number elements (classic
``Var``) are dropped from visibility maps.

``steps_timeline(doc, *, lag, duration, pause, effects, start)`` — the
construction step by step (plan L3 §5.4; docs/native/timeline.md §4).
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field

from ..easing import EASING_FUNCTIONS
from .document import as_document, bound_producer

__all__ = ['TIMELINE_FORMAT', 'DIRECTIONS', 'STEP_EFFECTS', 'StepsTimeline', 'sample_timeline',
           'steps_timeline', 'timeline_to_bridge', 'normalize_timeline', 'appearance_visible']

TIMELINE_FORMAT = 'animageo-timeline/v1'
DIRECTIONS = ('short', 'long', 'cw', 'ccw')
TWO_PI = 2 * math.pi

# Entrance effects by element type (the table of ``reveal_construction``).
STEP_EFFECTS = {
    'point': 'fade',
    'segment': 'create', 'line': 'create', 'ray': 'create', 'vector': 'create', 'circle': 'create',
    'arc': 'create', 'polyline': 'create', 'locus': 'create',
    'polygon': 'fade', 'sector': 'fade', 'angle': 'fade', 'mark': 'fade',
    'text': 'write',
}
# The entrance effects of the keyframe JSON v2 (``keyframes.ENTER_EFFECTS``;
# repeated here so ``steps_timeline`` stays free of the classic code).
ENTER_EFFECTS = ('fade', 'none', 'create', 'grow', 'write')
# Types without a drawing of their own (a classic ``Var``): never in a step timeline.
UNDRAWN = frozenset({'number'})


# ── validation ───────────────────────────────────────────────────────────

def _free_kinds(doc) -> dict:
    from .kernel.evaluate import _free_elements
    from .registry import registry
    return _free_elements(doc, registry())


def _number(value, where) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'timeline: {where} must be a finite number, got {value!r}')
    return float(value)


def _value(el_id, kind, raw, where):
    """``(kind, value, direction)`` of a keyframe value."""
    if kind == 'point':
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            raise ValueError(f'timeline: {where} {el_id!r} is a point: [x, y], got {raw!r}')
        return 'point', (_number(raw[0], where), _number(raw[1], where)), None
    if kind == 'pathParameter':
        if not isinstance(raw, dict) or 'tparam' not in raw:
            raise ValueError(f'timeline: {where} {el_id!r} is a point on a path: {{"tparam": t}}, got {raw!r}')
        direction = raw.get('direction', 'short')
        if direction not in DIRECTIONS:
            raise ValueError(f'timeline: {where} {el_id!r}: direction must be one of {list(DIRECTIONS)}')
        return 'pathParameter', _number(raw['tparam'], where), direction
    if kind == 'number':
        return 'number', _number(raw, where), None
    raise ValueError(f'timeline: {where} {el_id!r}: a free {kind} input is not animatable')


def normalize_timeline(doc, timeline) -> dict:
    """The keyframes of ``timeline`` checked against ``doc`` and sorted by ``t``:
    ``{"keyframes": [{t, values: {id: (kind, value, direction)}, visible: {id:
    bool}, easing, raw}], "easing": default}``; ``ValueError`` on a broken one."""
    doc = as_document(doc)
    if not isinstance(timeline, dict):
        raise ValueError('timeline must be a mapping with "keyframes"')
    raw_keyframes = timeline.get('keyframes')
    if not isinstance(raw_keyframes, list) or not raw_keyframes:
        raise ValueError('timeline: at least one keyframe is required')
    defaults = timeline.get('defaults') or {}
    default_easing = defaults.get('easing', 'smooth')
    if default_easing not in EASING_FUNCTIONS:
        raise ValueError(f'timeline: defaults.easing: unknown easing {default_easing!r}')
    free = _free_kinds(doc)
    out = []
    for i, kf in enumerate(raw_keyframes):
        if not isinstance(kf, dict) or 't' not in kf:
            raise ValueError(f"timeline: keyframe {i}: missing 't'")
        t = _number(kf['t'], f'keyframe {i} t')
        easing = kf.get('easing', default_easing)
        if easing not in EASING_FUNCTIONS:
            raise ValueError(f'timeline: keyframe {i}: unknown easing {easing!r}')
        values = {}
        for el_id, raw in (kf.get('values') or {}).items():
            if el_id == '@camera' or el_id not in doc.elements:
                continue
            kind = free.get(el_id)
            if kind is None:
                raise ValueError(f'timeline: keyframe {i}: {el_id!r} is not a free element')
            values[el_id] = _value(el_id, kind, raw, f'keyframe {i}')
        visible = {}
        for el_id in kf.get('show') or []:
            visible[el_id] = True
        for el_id in kf.get('hide') or []:
            visible[el_id] = False
        for el_id, flag in (kf.get('visible') or {}).items():
            visible[el_id] = bool(flag)
        visible = {el_id: flag for el_id, flag in visible.items() if el_id in doc.elements}
        out.append({'t': t, 'values': values, 'visible': visible, 'easing': easing, 'raw': kf})
    out.sort(key=lambda k: k['t'])
    for a, b in zip(out, out[1:]):
        if not b['t'] > a['t']:
            raise ValueError(f"timeline: keyframe times must be strictly increasing: {a['t']} and {b['t']}")
    return {'keyframes': out, 'easing': default_easing}


# ── paths ────────────────────────────────────────────────────────────────

def _path_periods(doc, ids) -> dict:
    """``{id: period | None}`` of the points on a path in ``ids``: ``2π`` on a
    circle, ``n`` on a polygon of ``n`` vertices (the document's values),
    ``3`` on a sector, ``None`` on other paths."""
    from .registry import registry
    paths = registry().paths
    out = {}
    ev = None
    for el_id in ids:
        producer = bound_producer(doc, el_id)
        op = doc.operations[producer] if producer is not None else None
        arg = (op or {}).get('args', {}).get('path') or {}
        path_id = arg.get('elementId') if arg.get('kind') == 'ref' else None
        spec = paths.get(doc.elements[path_id]['type']) if path_id in doc.elements else None
        if spec is None or spec.get('outside') != 'wrap':
            out[el_id] = None
        elif spec['kind'] == 'angle':
            out[el_id] = TWO_PI
        elif spec['kind'] == 'sector':
            out[el_id] = 3.0
        else:                                   # perimeter: n of the polygon now
            if ev is None:
                from .kernel.evaluate import evaluate
                ev = evaluate(doc)
            record = ev.elements.get(path_id) or {}
            vertices = (record.get('value') or {}).get('vertices') if record.get('state') == 'defined' else None
            out[el_id] = float(len(vertices)) if vertices else None
    return out


def path_delta(start: float, end: float, direction: str, period) -> float:
    """The signed move ``d`` from ``start`` towards ``end`` (module docstring, step 2)."""
    if period is None:
        return end - start
    r = (end - start) % period
    if direction == 'ccw':
        return r
    if direction == 'cw':
        return r - period if r > 0 else 0.0
    if direction == 'long':
        if r == 0:
            return 0.0
        return r - period if r <= period / 2 else r
    return r if r <= period / 2 else r - period


def _document_value(doc, el_id, kind):
    from .registry import FREE_INPUT_DEFAULTS
    value = doc.inputs.get(el_id) or FREE_INPUT_DEFAULTS.get(kind)
    if not isinstance(value, dict) or 'value' not in value:
        raise ValueError(f'timeline: {el_id!r} has no input in the document')
    v = value['value']
    return (float(v[0]), float(v[1])) if kind == 'point' else float(v)


def _tracks(doc, norm) -> dict:
    """``{id: [(value at keyframe k) for every k]}`` (carried forward, path
    parameters unwrapped) and the move of each interval."""
    keyframes = norm['keyframes']
    ids = sorted({el_id for kf in keyframes for el_id in kf['values']})
    kinds = {}
    for kf in keyframes:
        for el_id, (kind, _v, _d) in kf['values'].items():
            kinds[el_id] = kind
    periods = _path_periods(doc, [i for i in ids if kinds[i] == 'pathParameter'])
    tracks = {}
    for el_id in ids:
        kind = kinds[el_id]
        first = keyframes[0]['values'].get(el_id)
        current = first[1] if first is not None else _document_value(doc, el_id, kind)
        at = [current]
        for kf in keyframes[1:]:
            entry = kf['values'].get(el_id)
            if entry is not None:
                _kind, target, direction = entry
                if kind == 'pathParameter' and periods.get(el_id) is not None:
                    current = current + path_delta(current, target, direction, periods[el_id])
                else:
                    current = target
            at.append(current)
        tracks[el_id] = (kind, periods.get(el_id), at)
    return tracks


# ── sampling ─────────────────────────────────────────────────────────────

def appearance_visible(doc, el_id) -> bool:
    appearance = doc.data.get('appearance')
    entry = appearance.get(el_id) if isinstance(appearance, dict) else None
    flag = entry.get('visible') if isinstance(entry, dict) else None
    return flag if isinstance(flag, bool) else True


def _interval(keyframes, t) -> tuple:
    """``(k, p)``: the first interval ``[t_k, t_{k+1}]`` holding the clamped ``t``."""
    if len(keyframes) == 1:
        return 0, 0.0
    for k in range(len(keyframes) - 1):
        t0, t1 = keyframes[k]['t'], keyframes[k + 1]['t']
        if t0 <= t <= t1:
            return k, (t - t0) / (t1 - t0)
    return len(keyframes) - 2, 1.0


def sample_timeline(doc, timeline, t) -> dict:
    """``{t, inputs, visible}`` of ``timeline`` at time ``t`` (module docstring)."""
    doc = as_document(doc)
    norm = normalize_timeline(doc, timeline)
    keyframes = norm['keyframes']
    t = _number(t, 't')
    t = max(keyframes[0]['t'], min(t, keyframes[-1]['t']))
    k, p = _interval(keyframes, t)
    inputs = {}
    for el_id, (kind, period, at) in _tracks(doc, norm).items():
        start = at[k]
        if len(keyframes) > 1 and el_id in keyframes[k + 1]['values']:
            end = at[k + 1]
            e = EASING_FUNCTIONS[keyframes[k + 1]['easing']](p)
            if kind == 'point':
                value = [(1 - e) * start[0] + e * end[0], (1 - e) * start[1] + e * end[1]]
            elif kind == 'pathParameter' and period is not None:
                value = start + e * (end - start)
            else:
                value = (1 - e) * start + e * end
        else:
            value = list(start) if kind == 'point' else start
        inputs[el_id] = {'kind': kind, 'value': value}
    visible = {el_id: appearance_visible(doc, el_id) for el_id in sorted(doc.elements)}
    for kf in keyframes:
        if kf['t'] > t:
            break
        visible.update(kf['visible'])
    return {'t': t, 'inputs': inputs, 'visible': visible}


# ── bridge ───────────────────────────────────────────────────────────────

def timeline_to_bridge(doc, timeline) -> dict:
    """The classic keyframe JSON v2 of ``timeline`` for the scene of the bridge."""
    from .kernel.bridge import build_names
    doc = as_document(doc)
    norm = normalize_timeline(doc, timeline)
    names = build_names(doc.elements).by_id
    drawn = {el_id for el_id, el in doc.elements.items() if el['type'] not in UNDRAWN}
    tracks = _tracks(doc, norm)
    out_keyframes = []
    for k, kf in enumerate(norm['keyframes']):
        raw = kf['raw']
        item = {'t': kf['t']}
        values = {}
        for el_id, (kind, _v, _d) in sorted(kf['values'].items()):
            _kind, _period, at = tracks[el_id]
            if kind == 'point':
                values[names[el_id]] = [at[k][0], at[k][1]]
            elif kind == 'number':
                values[names[el_id]] = at[k]
            else:
                d = at[k] - at[k - 1] if k > 0 else 0.0
                values[names[el_id]] = {'tparam': at[k],
                                        'direction': 'ccw' if d > 0 else ('cw' if d < 0 else 'short')}
        camera = (raw.get('values') or {}).get('@camera')
        if camera is not None:
            values['@camera'] = copy.deepcopy(camera)
        if values:
            item['values'] = values
        visible = {names[el_id]: flag for el_id, flag in sorted(kf['visible'].items()) if el_id in drawn}
        if visible:
            item['visible'] = visible
        for key in ('enter', 'exit', 'styles'):
            spec = raw.get(key) or {}
            mapped = {names[el_id]: copy.deepcopy(v) for el_id, v in sorted(spec.items())
                      if el_id in doc.elements and el_id in drawn}
            if mapped:
                item[key] = mapped
        events = []
        for event in raw.get('events') or []:
            targets = [names[e] for e in (event.get('targets') or []) if e in drawn]
            if targets:
                events.append({**copy.deepcopy(event), 'targets': targets})
        if events:
            item['events'] = events
        if 'easing' in raw:
            item['easing'] = raw['easing']
        out_keyframes.append(item)
    out = {'version': 2, 'keyframes': out_keyframes}
    if timeline.get('defaults'):
        out['defaults'] = copy.deepcopy(timeline['defaults'])
    return out


# ── steps ────────────────────────────────────────────────────────────────

@dataclass
class StepsTimeline:
    """The result of :func:`steps_timeline`: ``keyframes`` — a timeline v2 with
    ID keys; ``steps`` — ``[{stepId, start, end, elementIds, text}]``;
    ``duration`` — the time of the last keyframe."""

    keyframes: dict
    steps: list = field(default_factory=list)
    duration: float = 0.0

    def to_dict(self) -> dict:
        return {'keyframes': self.keyframes, 'steps': self.steps, 'duration': self.duration}


def _check_positive(name, value, *, zero=True) -> float:
    v = _number(value, name)
    if v < 0 or (not zero and v == 0):
        raise ValueError(f'steps_timeline: {name} must be {"≥ 0" if zero else "> 0"}, got {value!r}')
    return v


def steps_timeline(doc, *, lag=0.3, duration=0.5, pause=0.6, effects=None, start=0.0) -> StepsTimeline:
    """The construction step by step (plan L3 §5.4; docs/native/timeline.md §4).

    Steps of :func:`~animageo.native.steps` with their visible drawn
    elements (``elementIds`` of the step without numbers); a step without
    one is skipped. ``d_i = (n_i − 1)·lag + duration``, ``S_1 = start``,
    ``S_{i+1} = S_i + d_i + pause``. Keyframe 0 at ``start`` hides every
    element of the steps; keyframe ``i`` at ``S_i + d_i`` shows the elements
    of step ``i`` with ``enter[id] = {effect, duration, at}``, ``at = j·lag``
    for the first step and ``pause + j·lag`` for the others. ``effects``
    (``{type: effect}``) overrides :data:`STEP_EFFECTS`; a type outside the
    table fades.
    """
    from .steps import steps as _steps
    doc = as_document(doc)
    lag = _check_positive('lag', lag)
    duration = _check_positive('duration', duration, zero=False)
    pause = _check_positive('pause', pause)
    start = _number(start, 'start')
    table = dict(STEP_EFFECTS)
    if effects is not None:
        if not isinstance(effects, dict):
            raise ValueError('steps_timeline: effects must be a mapping of element type to effect')
        for type_, effect in effects.items():
            if effect not in ENTER_EFFECTS:
                raise ValueError(f'steps_timeline: unknown effect {effect!r} for {type_!r}; valid: {list(ENTER_EFFECTS)}')
        table.update(effects)
    rows = []
    for step in _steps(doc):
        ids = [e for e in step.elementIds if doc.elements[e]['type'] not in UNDRAWN]
        if ids:
            rows.append((step, ids))
    hidden = {e: False for _step, ids in rows for e in ids}
    keyframes = [{'t': start, 'visible': hidden}]
    out_steps = []
    s_i = start
    for i, (step, ids) in enumerate(rows):
        d_i = (len(ids) - 1) * lag + duration
        offset = 0.0 if i == 0 else pause
        enter = {e: {'effect': table.get(doc.elements[e]['type'], 'fade'), 'duration': duration,
                     'at': offset + j * lag} for j, e in enumerate(ids)}
        keyframes.append({'t': s_i + d_i, 'visible': {e: True for e in ids}, 'enter': enter})
        out_steps.append({'stepId': step.id, 'start': s_i, 'end': s_i + d_i, 'elementIds': list(ids),
                          'text': step.text if step.text is not None else step.title})
        s_i = s_i + d_i + pause
    total = keyframes[-1]['t']
    return StepsTimeline({'version': 2, 'keyframes': keyframes}, out_steps, total)
