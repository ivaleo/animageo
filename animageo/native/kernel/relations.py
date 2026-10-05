"""Relation predicates and ``general_position`` (docs/native/checks.md).

A relation is ``{"id", "predicate", "args": [elementId, …]}``. Its error
``e >= 0`` is a length measured from the values of the argument elements and
classified by ``tol.check`` like a mandatory check (``passed``, ``failed``,
``inconclusive``); a predicate this registry does not know, an argument type
outside its table or a wrong argument count is ``unsupported``.

``general_position`` (``trials = N > 0``) re-evaluates the document with
perturbed free inputs and requires every trial to pass; the trial sequence of
one check is seeded by the first 8 bytes of ``sha256(m + "\\0" + checkId)``
(``m`` = ``documentId`` or ``str(seed)``; the mandatory op checks share the
sequence of ``checkId = ""``).
"""
from __future__ import annotations

import hashlib
import math

from ..document import bound_producer
from ..registry import registry
from . import paths
from .checks import classify

__all__ = ['SplitMix64', 'check_document', 'PREDICATES', 'relation_status', 'trial_seed', 'perturbed_inputs', 'aggregate',
           'check_relations', 'RELATION_PREFIX']

RELATION_PREFIX = 'relation:'
TWO_PI = 2 * math.pi
PERTURB_RADIUS = 0.25     # of S
RETRIES = 3               # resamples of an undefined trial, each with half the radius


class _Unsupported(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class _Inconclusive(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _family(name):
    return set(registry().families.get(name, ())) | {name}


def _xy(value):
    if isinstance(value, dict):
        return value['x'], value['y']
    return value[0], value[1]


def _direction(type_, value, tol):
    """Unit direction of a linear element or a vector."""
    if type_ == 'line':
        return value['dir'][0], value['dir'][1]
    if type_ == 'ray':
        return value['dir'][0], value['dir'][1]
    ax, ay = value['a']
    bx, by = value['b']
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length <= tol.decide_length:
        raise _Inconclusive('zero_length')
    return dx / length, dy / length


def _anchor(type_, value):
    """A point of the carrier line of a linear element."""
    if type_ == 'line':
        return value['p'][0], value['p'][1]
    if type_ == 'ray':
        return value['origin'][0], value['origin'][1]
    return value['a'][0], value['a'][1]


def _circle(value):
    return value['c'][0], value['c'][1], value['r']


def _need(items, types, count=None, at_least=None):
    if count is not None and len(items) != count:
        raise _Unsupported('arity')
    if at_least is not None and len(items) < at_least:
        raise _Unsupported('arity')
    for type_, _value in items:
        if type_ not in types:
            raise _Unsupported('type')


def _incident(items, tol):
    if len(items) != 2:
        raise _Unsupported('arity')
    path_types = set(registry().families.get('path', ()))
    (t1, v1), (t2, v2) = items
    if t1 == 'point' and t2 in path_types:
        point, (tp, vp) = v1, (t2, v2)
    elif t2 == 'point' and t1 in path_types:
        point, (tp, vp) = v2, (t1, v1)
    else:
        raise _Unsupported('type')
    x, y = _xy(point)
    return paths.distance_to_path(x, y, tp, vp)


def _linear_or_vector():
    return _family('linear') | {'vector'}


def _parallel(items, tol):
    _need(items, _linear_or_vector(), count=2)
    d1 = _direction(*items[0], tol)
    d2 = _direction(*items[1], tol)
    return abs(d1[0] * d2[1] - d1[1] * d2[0]) * tol.scale


def _perpendicular(items, tol):
    _need(items, _linear_or_vector(), count=2)
    d1 = _direction(*items[0], tol)
    d2 = _direction(*items[1], tol)
    return abs(d1[0] * d2[0] + d1[1] * d2[1]) * tol.scale


def _equal_length(items, tol):
    _need(items, {'segment', 'vector'}, count=2)
    return abs(items[0][1]['length'] - items[1][1]['length'])


def _equal_angle(items, tol):
    _need(items, {'angle'}, count=2)
    return abs(items[0][1]['size'] - items[1][1]['size']) * tol.scale


def _collinear(items, tol):
    _need(items, {'point'}, at_least=3)
    pts = [_xy(v) for _t, v in items]
    best = (-1.0, 0, 0)
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = math.hypot(pts[j][0] - pts[i][0], pts[j][1] - pts[i][1])
            if d > best[0]:
                best = (d, i, j)
    length, i, j = best
    if length <= tol.decide_length:
        return 0.0
    ax, ay = pts[i]
    dx, dy = (pts[j][0] - ax) / length, (pts[j][1] - ay) / length
    return max(abs((x - ax) * dy - (y - ay) * dx) for x, y in pts)


def _circumcircle(a, b, c):
    bx, by = b[0] - a[0], b[1] - a[1]
    cx, cy = c[0] - a[0], c[1] - a[1]
    cross = bx * cy - by * cx
    b2 = bx * bx + by * by
    c2 = cx * cx + cy * cy
    d = 2 * cross
    ux = (cy * b2 - by * c2) / d
    uy = (bx * c2 - cx * b2) / d
    return a[0] + ux, a[1] + uy, math.hypot(ux, uy)


def _concyclic(items, tol):
    _need(items, {'point'}, at_least=4)
    pts = [_xy(v) for _t, v in items]
    best = (-1.0, None)
    n = len(pts)
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                (ax, ay), (bx, by), (cx, cy) = pts[i], pts[j], pts[k]
                area = abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax))
                if area > best[0]:
                    best = (area, (i, j, k))
    area, (i, j, k) = best
    longest = max(math.hypot(pts[q][0] - pts[p][0], pts[q][1] - pts[p][1])
                  for p, q in ((i, j), (j, k), (k, i)))
    if longest <= tol.decide_length or area / longest <= tol.decide_length:
        raise _Inconclusive('degenerate')
    ox, oy, r = _circumcircle(pts[i], pts[j], pts[k])
    return max(abs(math.hypot(x - ox, y - oy) - r) for x, y in pts)


def _concurrent(items, tol):
    _need(items, _family('linear'), at_least=3)
    lines = [(_anchor(t, v), _direction(t, v, tol)) for t, v in items]
    best = (-1.0, 0, 0)
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            d1, d2 = lines[i][1], lines[j][1]
            cross = abs(d1[0] * d2[1] - d1[1] * d2[0])
            if cross > best[0]:
                best = (cross, i, j)
    cross, i, j = best
    if cross <= tol.decide_scalar:
        raise _Inconclusive('parallel')
    (p1, d1), (p2, d2) = lines[i], lines[j]
    den = d1[0] * d2[1] - d1[1] * d2[0]
    s = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
    x, y = p1[0] + s * d1[0], p1[1] + s * d1[1]
    return max(abs((x - p[0]) * d[1] - (y - p[1]) * d[0]) for p, d in lines)


def _tangent(items, tol):
    if len(items) != 2:
        raise _Unsupported('arity')
    linear = _family('linear')
    circular = _family('circular')
    (t1, v1), (t2, v2) = items
    if t1 in circular and t2 in circular:
        x1, y1, r1 = _circle(v1)
        x2, y2, r2 = _circle(v2)
        d = math.hypot(x2 - x1, y2 - y1)
        return min(abs(d - (r1 + r2)), abs(d - abs(r1 - r2)))
    if t1 in linear and t2 in circular:
        lt, lv, cv = t1, v1, v2
    elif t2 in linear and t1 in circular:
        lt, lv, cv = t2, v2, v1
    else:
        raise _Unsupported('type')
    px, py = _anchor(lt, lv)
    dx, dy = _direction(lt, lv, tol)
    cx, cy, r = _circle(cv)
    return abs(abs((cx - px) * dy - (cy - py) * dx) - r)


PREDICATES = {
    'incident': _incident,
    'parallel': _parallel,
    'perpendicular': _perpendicular,
    'equal_length': _equal_length,
    'equal_angle': _equal_angle,
    'collinear': _collinear,
    'concyclic': _concyclic,
    'concurrent': _concurrent,
    'tangent': _tangent,
}


def _validate(relations) -> list:
    if not isinstance(relations, (list, tuple)):
        raise ValueError('relations must be a list of {id, predicate, args}')
    seen = set()
    out = []
    for item in relations:
        if not isinstance(item, dict):
            raise ValueError('a relation must be a mapping {id, predicate, args}')
        rid = item.get('id')
        if not isinstance(rid, str) or not rid:
            raise ValueError('a relation needs a non-empty string id')
        if rid in seen:
            raise ValueError(f'relation id {rid!r} is repeated')
        seen.add(rid)
        args = item.get('args')
        if not isinstance(args, (list, tuple)) or not all(isinstance(a, str) for a in args):
            raise ValueError(f'relation {rid!r}: args must be a list of element IDs')
        if not isinstance(item.get('predicate'), str):
            raise ValueError(f'relation {rid!r}: predicate must be a string')
        out.append({'id': rid, 'predicate': item['predicate'], 'args': list(args)})
    return out


def relation_status(relation: dict, evaluated, element_types: dict) -> tuple:
    """``(status, error | None, detail | None)`` of one relation in ``evaluated``."""
    fn = PREDICATES.get(relation['predicate'])
    if fn is None:
        return 'unsupported', None, {'reason': 'unknown_predicate'}
    missing = [a for a in relation['args'] if a not in element_types]
    if missing:
        return 'unsupported', None, {'reason': 'dangling_ref', 'elementIds': missing}
    undefined = [a for a in relation['args'] if evaluated.elements[a]['state'] != 'defined']
    tol = evaluated.tolerances
    items = [(element_types[a], evaluated.elements[a].get('value')) for a in relation['args']]
    try:
        if undefined:
            # The types still decide ``unsupported`` before the state does.
            fn([(t, _placeholder(t)) for t, _v in items], tol)
            return 'inconclusive', None, {'reason': 'undefined', 'elementIds': undefined}
        error = float(fn(items, tol))
    except _Unsupported as exc:
        return 'unsupported', None, {'reason': exc.reason}
    except _Inconclusive as exc:
        if undefined:
            return 'inconclusive', None, {'reason': 'undefined', 'elementIds': undefined}
        return 'inconclusive', None, {'reason': exc.reason}
    return classify(error, tol), error, None


def _placeholder(type_):
    """A harmless value of ``type_`` to let a predicate check argument types."""
    pt = {'x': 0.0, 'y': 0.0}
    return {
        'point': pt,
        'line': {'p': [0.0, 0.0], 'dir': [1.0, 0.0]},
        'ray': {'origin': [0.0, 0.0], 'dir': [1.0, 0.0]},
        'segment': {'a': [0.0, 0.0], 'b': [1.0, 0.0], 'length': 1.0},
        'vector': {'a': [0.0, 0.0], 'b': [1.0, 0.0], 'length': 1.0},
        'circle': {'c': [0.0, 0.0], 'r': 1.0},
        'arc': {'c': [0.0, 0.0], 'r': 1.0, 'a0': 0.0, 'a1': 1.0},
        'sector': {'c': [0.0, 0.0], 'r': 1.0, 'a0': 0.0, 'a1': 1.0},
        'polygon': {'vertices': [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]], 'area': 0.5},
        'polyline': {'vertices': [[0.0, 0.0], [1.0, 0.0]], 'length': 1.0},
        'angle': {'vertex': [0.0, 0.0], 'a0': 0.0, 'a1': 1.0, 'size': 1.0},
    }.get(type_, {})


_MASK = (1 << 64) - 1


class SplitMix64:
    """A seeded stream of floats in ``[0, 1)`` (SplitMix64, 53-bit mantissa),
    so another language reproduces the trials of one seed bit for bit."""

    __slots__ = ('state',)

    def __init__(self, seed: int):
        self.state = int(seed) & _MASK

    def next_u64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & _MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
        return z ^ (z >> 31)

    def random(self) -> float:
        return (self.next_u64() >> 11) * (1.0 / (1 << 53))


def trial_seed(material: str, check_id: str) -> int:
    """``uint64`` of the first 8 bytes of ``sha256(material + "\\0" + check_id)``."""
    digest = hashlib.sha256((material + '\0' + check_id).encode('utf-8')).digest()
    return int.from_bytes(digest[:8], 'big')


def _free_specs(doc, base_eval, values_in):
    """``[(elementId, kind, info)]`` of free inputs in ID order; ``info`` holds
    the parameter range of a path point and the bounds of a number."""
    reg = registry()
    out = []
    for el_id in sorted(doc.elements):
        producer = bound_producer(doc, el_id)
        if producer is None:
            continue
        op = doc.operations[producer]
        record = reg.get(op['op'])
        if record is None or record.get('free') is None:
            continue
        if doc.elements[el_id]['producer']['slot'] != record['outputs'][0]['slot']:
            continue
        kind = record['free']['kind']
        info = {}
        if kind == 'number':
            for name in ('min', 'max'):
                arg = op['args'].get(name)
                if isinstance(arg, dict) and arg.get('kind') == 'number':
                    info[name] = float(arg['value'])
        elif kind == 'pathParameter':
            info = _path_range(doc, op, base_eval)
        out.append((el_id, kind, info))
    return out


def _path_range(doc, op, base_eval) -> dict:
    from .evaluate import producer_values
    arg = op['args'].get('path') or {}
    path_id = arg.get('elementId') if arg.get('kind') == 'ref' else None
    if path_id is None or base_eval.elements.get(path_id, {}).get('state') != 'defined':
        return {}
    type_ = doc.elements[path_id]['type']
    try:
        _op, values = producer_values(path_id, doc.elements, doc.operations, base_eval.elements)
        f = paths.frame(type_, base_eval.elements[path_id]['value'], _op, values)
    except (KeyError, ValueError, TypeError):
        return {}
    lo, hi = paths.parameter_range(f)
    length = math.hypot(*f.vector) if f.kind == 'affine' else 0.0
    return {'lo': lo, 'hi': hi, 'unit': length}


def perturbed_inputs(specs, values_in, rng, radius) -> dict:
    """Free input values of one trial; draws from ``rng`` in ``specs`` order."""
    out = {}
    for el_id, kind, info in specs:
        current = values_in.get(el_id)
        if kind == 'point':
            if current is None:
                continue
            x, y = current['value']
            rho = radius * math.sqrt(rng.random())
            phi = TWO_PI * rng.random()
            out[el_id] = {'kind': 'point', 'value': [x + rho * math.cos(phi), y + rho * math.sin(phi)]}
        elif kind == 'pathParameter':
            if current is None:
                continue
            u = rng.random()
            lo, hi = info.get('lo'), info.get('hi')
            if lo is not None and hi is not None:
                t = lo + u * (hi - lo)
            else:
                unit = info.get('unit') or 1.0
                t = current['value'] + (2 * u - 1) * radius / unit
                if lo is not None and t < lo:
                    t = lo
            value = {'kind': 'pathParameter', 'value': t}
            if 'branch' in current:
                value['branch'] = current['branch']
            out[el_id] = value
        elif kind == 'number':
            if current is None:
                continue
            u = rng.random()
            if 'min' in info and 'max' in info and info['max'] >= info['min']:
                v = info['min'] + u * (info['max'] - info['min'])
            else:
                v0 = current['value']
                v = v0 * (1 + (2 * u - 1) * 0.25) if v0 != 0 else (2 * u - 1) * 0.25
            out[el_id] = {'kind': 'number', 'value': v}
        elif kind == 'angle':
            out[el_id] = {'kind': 'angle', 'value': TWO_PI * rng.random()}
    return out


def aggregate(base, trials) -> tuple:
    """``(status, detail)`` from the base status and the trial results
    ``[(status, error, inputs)]`` (``status`` ``undefined`` when the check
    could not be measured)."""
    counts = {'passed': 0, 'failed': 0, 'inconclusive': 0, 'undefined': 0}
    counterexample = None
    status0, error0 = base
    if status0 == 'failed':
        counterexample = {'trial': 0, 'error': error0}
    for i, (status, error, inputs) in enumerate(trials, start=1):
        counts[status if status in counts else 'inconclusive'] += 1
        if status == 'failed' and counterexample is None:
            counterexample = {'trial': i, 'error': error, 'inputs': inputs}
    detail = {'trials': len(trials), **counts}
    if status0 == 'failed' or counts['failed']:
        detail['counterexample'] = counterexample
        return 'failed', detail
    if status0 != 'passed' or counts['inconclusive'] or counts['undefined']:
        return 'inconclusive', detail
    return 'passed', detail


def run_trials(doc, values_in, specs, keys, measure, rng, trials, scale, evaluate) -> dict:
    """``{key: [(status, error, inputs)…]}`` over ``trials`` trials.

    ``measure(evaluated) -> {key: (status, error)}`` for the keys it could
    measure; an unmeasured key is resampled with half the radius up to
    :data:`RETRIES` times within the same trial, then counts ``undefined``.
    """
    out = {key: [] for key in keys}
    for _trial in range(trials):
        pending = set(keys)
        radius = PERTURB_RADIUS * scale
        for _attempt in range(RETRIES + 1):
            overrides = perturbed_inputs(specs, values_in, rng, radius)
            try:
                ev = evaluate(doc, inputs=overrides)
            except ValueError:
                ev = None
            got = measure(ev) if ev is not None else {}
            for key in sorted(pending):
                if key in got:
                    status, error = got[key]
                    out[key].append((status, error, overrides))
                    pending.discard(key)
            if not pending:
                break
            radius /= 2
        for key in sorted(pending):
            out[key].append(('undefined', None, None))
    return out


def check_relations(relations, evaluated, doc) -> dict:
    """``{key: (status, error, detail)}`` of the relations in ``evaluated``."""
    types = {el_id: el['type'] for el_id, el in doc.elements.items()}
    out = {}
    for relation in relations:
        out[RELATION_PREFIX + relation['id']] = relation_status(relation, evaluated, types)
    return out


validate_relations = _validate


def check_document(doc, checks=None, *, inputs=None, relations=None, trials=0, seed=None):
    """:func:`animageo.native.check` (see there)."""
    from ..document import as_document
    from .checks import run_checks
    from .evaluate import check_inputs, evaluate

    doc = as_document(doc)
    rels = _validate(relations) if relations is not None else []
    trials = int(trials or 0)
    if trials < 0:
        raise ValueError('trials must be >= 0')
    base = evaluate(doc, inputs=inputs)
    report = run_checks(base, checks)
    for key, (status, error, detail) in check_relations(rels, base, doc).items():
        report.results[key] = status
        if error is not None:
            report.errors[key] = error
        if detail is not None:
            report.details[key] = detail
    if trials == 0:
        return report

    values_in = dict(doc.inputs)
    values_in.update(check_inputs(doc, inputs))
    specs = _free_specs(doc, base, values_in)
    material = str(seed) if seed is not None else str(doc.document_id)
    scale = base.scale

    def _evaluate(d, inputs):
        merged = dict(inputs_base)
        merged.update(inputs)
        return evaluate(d, inputs=merged)

    inputs_base = dict(inputs or {})

    op_keys = [k for k in report.results if not k.startswith(RELATION_PREFIX)]
    if op_keys:
        def measure_ops(ev):
            sub = run_checks(ev, op_keys)
            return {k: (sub.results[k], sub.errors.get(k)) for k in sub.results}
        rng = SplitMix64(trial_seed(material, ''))
        runs = run_trials(doc, values_in, specs, op_keys, measure_ops, rng, trials, scale, _evaluate)
        for key in op_keys:
            status, detail = aggregate((report.results[key], report.errors.get(key)), runs[key])
            report.results[key] = status
            report.details[key] = detail
    types = {el_id: el['type'] for el_id, el in doc.elements.items()}
    for relation in rels:
        key = RELATION_PREFIX + relation['id']
        if report.results[key] == 'unsupported':
            continue

        def measure_rel(ev, relation=relation, key=key):
            status, error, detail = relation_status(relation, ev, types)
            if detail is not None and detail.get('reason') == 'undefined':
                return {}
            return {key: (status, error)}
        rng = SplitMix64(trial_seed(material, relation['id']))
        runs = run_trials(doc, values_in, specs, [key], measure_rel, rng, trials, scale, _evaluate)
        base_detail = report.details.get(key)
        status, detail = aggregate((report.results[key], report.errors.get(key)), runs[key])
        if base_detail is not None:
            detail['base'] = base_detail
        report.results[key] = status
        report.details[key] = detail
    return report
