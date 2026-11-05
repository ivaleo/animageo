"""Dragging a point of a document (``native.drag``; docs/native/kernel.md §8.1).

A free point goes to the target; a point on a path takes the parameter of the
nearest point of its path. A dependent point moves only through the hint
``appearance.<id>.drag.via`` — free inputs (``point.free``,
``point.on_path``) upstream of it: a Gauss–Newton solve over the joined
vector of their values moves them so that the point reaches the target, or
the nearest point it can reach when a single path parameter drives it.
Evaluation never reads the hint. The algorithm is fixed to the last step so
that the web port gives the same inputs (fixtures ``parity/v1/drag``):

- variables ``u``: per ``via`` in order, a point gives ``x, y`` and a path
  parameter ``t``; the scene scale ``S`` and ``tol = tol.decide`` are those
  of the evaluation at rest (the given ``inputs``);
- difference step ``h``: ``STEP_FRACTION · S`` for a coordinate;
  ``STEP_FRACTION · (hi − lo)`` for a parameter whose range is bounded on
  both sides, ``STEP_FRACTION · S / |v|`` for an affine path open on a side
  (line, ray; ``|v|`` the frame vector at rest, ``STEP_FRACTION`` when
  ``|v| ≤ tol``); the column scale is ``c = h / (STEP_FRACTION · S)``;
- ``J`` by central differences ``(f(u + h) − f(u − h)) / (u⁺ − u⁻)`` over
  the stencil clamped into a clamped range; a column of zero width is zero;
- rank and step on ``Ĵ = J · diag(c)``: ``σ₁² + σ₂² = Σ|col|²``,
  ``σ₁² σ₂² = Σ_{i<j} (col_i × col_j)²``; a singular value counts when it is
  above ``RANK_EPSILON · max(1, σ₁)``; the step is ``δ = −c · Ĵ⁺ r``
  (least norm) with variables at a clamp bound that the step pushes out of
  range frozen (repeated until none is frozen anew);
- first trial length ``λ₀`` (:func:`_length`): ``1``; for a single variable
  the Newton length of ``|r|²/2`` along the step, from the second difference
  of the same stencil (a curved path far from the target);
- line search (:func:`_line_search`): ``λ = λ₀, λ₀/2, …``
  (``MAX_HALVINGS + 1`` trials), the best defined trial within
  ``|r| + ACCEPT_SLACK · tol`` is taken, none ends the solve; at most
  ``MAX_ITERATIONS`` steps; the solve also ends when the predicted move
  ``|J δ|`` is within ``tol`` (stationary);
- status: ``|r| ≤ tol`` → ``ok``; stationary with a variable frozen at a
  clamp bound → ``clamped``; stationary with rank at rest below 2 (the
  nearest reachable point) → ``ok``, unless it is the farthest one
  (:func:`_farthest`); otherwise ``no_convergence``. Rank at rest below
  ``min(2, dim u)`` → ``singular`` before any step.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass

from .document import Issue, NativeDocument, _pointer, as_document, bound_producer
from .kernel import paths as _paths
from .kernel.evaluate import check_inputs, evaluate, producer_values, valid_input
from .registry import free_slot, registry

__all__ = ['ACCEPT_SLACK', 'CURVATURE_FLOOR', 'DRAG_STATUSES', 'MAX_HALVINGS', 'MAX_ITERATIONS', 'RANK_EPSILON', 'STEP_FRACTION',
           'VIA_OPS',
           'DragResult', 'drag', 'drag_issues', 'drag_via', 'solve']

DRAG_STATUSES = ('ok', 'clamped', 'no_convergence', 'singular')
MAX_ITERATIONS = 8
MAX_HALVINGS = 4
STEP_FRACTION = 1e-5
RANK_EPSILON = 1e-6
CURVATURE_FLOOR = 1e-2
ACCEPT_SLACK = 1e-3
VIA_OPS = ('point.free', 'point.on_path', 'point.on_function')
_KINDS = {'point.free': 'point', 'point.on_path': 'pathParameter', 'point.on_function': 'pathParameter'}


@dataclass(frozen=True)
class DragResult:
    """The result of :func:`solve`: ``inputs`` is the given object itself on a
    refusal; ``iterations`` counts the steps taken, ``residual`` is the
    distance from the point to the target at the end (``None`` when the
    point is not defined)."""

    status: str
    inputs: object
    iterations: int = 0
    residual: float | None = None


@dataclass(frozen=True)
class _Var:
    via: str
    h: float                  # difference step
    c: float                  # column scale h / (STEP_FRACTION · S)
    lo: float | None = None   # bounds of a clamped range
    hi: float | None = None
    wrap: tuple | None = None  # (lo, hi) of a wrapped range


# ── the hint ─────────────────────────────────────────────────────────────


def _via_kind(doc: NativeDocument, el_id: str):
    """``"point"`` / ``"pathParameter"`` for the element of ``point.free`` /
    ``point.on_path`` or ``point.on_function`` holding the input, else
    ``None``."""
    producer = bound_producer(doc, el_id)
    if producer is None:
        return None
    name = doc.operations[producer].get('op')
    record = registry().get(name)
    if name not in _KINDS or record is None or doc.elements[el_id]['producer']['slot'] != free_slot(record):
        return None
    return _KINDS[name]


def drag_via(doc, element_id: str):
    """The ``via`` list of ``appearance.<element_id>.drag`` (a single ID
    becomes a list of one), ``None`` without a hint."""
    doc = as_document(doc)
    appearance = doc.data.get('appearance')
    entry = appearance.get(element_id) if isinstance(appearance, dict) else None
    hint = entry.get('drag') if isinstance(entry, dict) else None
    if hint is None:
        return None
    via = hint.get('via') if isinstance(hint, dict) else None
    via = [via] if isinstance(via, str) else via
    if not isinstance(via, list) or not via or not all(isinstance(v, str) for v in via):
        raise ValueError(f'appearance.{element_id}.drag.via must be an ID or a list of IDs')
    return list(via)


def _ancestors(doc: NativeDocument, el_id: str) -> set:
    from .edit import closure
    return set(closure(doc, el_id, direction='up')) - {el_id}


def _via_problems(doc: NativeDocument, el_id: str, via: list, ancestors=None) -> list:
    """``[(index, code, message)]`` of the ``via`` items that cannot drive ``el_id``."""
    out = []
    for i, via_id in enumerate(via):
        if via_id not in doc.elements:
            out.append((i, 'dangling_ref', f'element {via_id!r} does not exist'))
        elif _via_kind(doc, via_id) is None:
            out.append((i, 'drag_via_not_free',
                        f'{via_id!r} is not a free input (point.free, point.on_path, point.on_function)'))
        else:
            if ancestors is None:
                ancestors = _ancestors(doc, el_id)
            if via_id not in ancestors:
                out.append((i, 'drag_via_not_upstream', f'{el_id!r} is not built from {via_id!r}'))
    return out


# ── the problem ──────────────────────────────────────────────────────────


def _path_range(doc: NativeDocument, states: dict, via_id: str):
    """``(frame, lo, hi, outside)`` of the path of the ``point.on_path`` input
    ``via_id`` at rest, ``None`` when the path is not defined."""
    arg = doc.operations[bound_producer(doc, via_id)]['args'].get('path') or {}
    path_id = arg.get('elementId') if arg.get('kind') == 'ref' else None
    rec = states.get(path_id)
    if rec is None or rec['state'] != 'defined':
        return None
    type_ = doc.elements[path_id]['type']
    spec = registry().paths.get(type_)
    if spec is None:
        return None
    producer_op, values = producer_values(path_id, doc.elements, doc.operations, states)
    frame = _paths.frame(type_, rec['value'], producer_op, values)
    lo, hi = _paths.parameter_range(frame)
    return frame, lo, hi, spec.get('outside')


def _on_function(doc: NativeDocument, el_id: str) -> bool:
    return doc.operations[bound_producer(doc, el_id)].get('op') == 'point.on_function'


def _function_domain(doc: NativeDocument, states: dict, via_id: str):
    """``(lo, hi)`` (``None`` — open) of the domain of the function of the
    ``point.on_function`` input ``via_id`` at rest, ``None`` when the
    function is not defined."""
    arg = doc.operations[bound_producer(doc, via_id)]['args'].get('function') or {}
    rec = states.get(arg.get('elementId')) if arg.get('kind') == 'ref' else None
    if rec is None or rec['state'] != 'defined':
        return None
    lo, hi = rec['value']['domain']
    return lo, hi


class _Problem:
    """The variables of ``via`` at rest and the map ``u → point``."""

    def __init__(self, doc, inputs, element_id, via):
        self.doc = doc
        self.given = inputs
        self.inputs = inputs or {}
        self.element_id = element_id
        self.via = via
        rest = evaluate(doc, inputs=inputs)
        self.tol = rest.tolerances.decide_length
        scale = self.scale = rest.tolerances.scale
        values = dict(doc.inputs)
        values.update(self.inputs)
        self.current = values
        self.vars: list = []
        self.u0: list = []
        self.ready = True
        unit = STEP_FRACTION * scale
        for via_id in via:
            kind = _via_kind(doc, via_id)
            value = values.get(via_id)
            if not valid_input(kind, value):
                self.ready = False
                return
            if kind == 'point':
                for coord in value['value']:
                    self.vars.append(_Var(via_id, unit, 1.0))
                    self.u0.append(float(coord))
                continue
            if _on_function(doc, via_id):
                domain = _function_domain(doc, rest.elements, via_id)
                if domain is None:
                    self.ready = False
                    return
                lo, hi = domain
                x = float(value['value'])
                x = max(x, lo) if lo is not None else x
                x = min(x, hi) if hi is not None else x
                self.vars.append(_Var(via_id, unit, 1.0, lo=lo, hi=hi))
                self.u0.append(x)
                continue
            found = _path_range(doc, rest.elements, via_id)
            if found is None:
                self.ready = False
                return
            frame, lo, hi, outside = found
            if lo is not None and hi is not None:
                h = STEP_FRACTION * (hi - lo) if hi > lo else STEP_FRACTION
            else:
                length = math.hypot(*frame.vector)
                h = unit / length if length > self.tol else STEP_FRACTION
            t = float(value['value'])
            if outside == 'clamp':
                t = min(max(t, lo), hi) if hi is not None else max(t, lo)
                var = _Var(via_id, h, h / unit, lo=lo, hi=hi)
            elif outside == 'wrap':
                var = _Var(via_id, h, h / unit, wrap=(lo, hi))
            else:
                var = _Var(via_id, h, h / unit)
            self.vars.append(var)
            self.u0.append(t)

    def entries(self, u) -> dict:
        """``{via: input value}`` of ``u``; a wrapped parameter goes back into
        its range, the ``branch`` of a parameter stays."""
        out = {}
        k = 0
        for via_id in self.via:
            current = self.current[via_id]
            if current['kind'] == 'point':
                out[via_id] = {'kind': 'point', 'value': [u[k], u[k + 1]]}
                k += 2
                continue
            t = u[k]
            var = self.vars[k]
            if var.wrap is not None:
                lo, hi = var.wrap
                period = hi - lo
                t = t - period * math.floor((t - lo) / period)
                if t >= hi or t < lo:
                    t = lo
            value = {'kind': 'pathParameter', 'value': t}
            if 'branch' in current:
                value['branch'] = current['branch']
            out[via_id] = value
            k += 1
        return out

    def point(self, u):
        """The point at ``u``, ``None`` when it is not defined."""
        merged = dict(self.inputs)
        merged.update(self.entries(u))
        rec = evaluate(self.doc, inputs=merged).elements[self.element_id]
        if rec['state'] != 'defined':
            return None
        return rec['value']['x'], rec['value']['y']

    def clamp(self, u) -> list:
        out = list(u)
        for j, var in enumerate(self.vars):
            if var.lo is not None and out[j] < var.lo:
                out[j] = float(var.lo)
            if var.hi is not None and out[j] > var.hi:
                out[j] = float(var.hi)
        return out

    def jacobian(self, u, p):
        """``(cols, curvature)``: the scaled columns ``c_j · ∂point/∂u_j`` and,
        for a single variable, the second difference ``∂²point/∂u²`` of its
        stencil around ``p`` (``(0, 0)`` for a one-sided stencil); ``None``
        when a stencil point is not defined."""
        cols = []
        curvature = (0.0, 0.0)
        for j, var in enumerate(self.vars):
            up = u[j] + var.h
            um = u[j] - var.h
            if var.hi is not None:
                up = min(up, var.hi)
            if var.lo is not None:
                um = max(um, var.lo)
            width = up - um
            if width <= 0:
                cols.append((0.0, 0.0))
                continue
            plus = self.point(u[:j] + [up] + u[j + 1:])
            minus = self.point(u[:j] + [um] + u[j + 1:])
            if plus is None or minus is None:
                return None
            cols.append(((plus[0] - minus[0]) / width * var.c, (plus[1] - minus[1]) / width * var.c))
            hp = up - u[j]
            hm = u[j] - um
            if len(self.vars) == 1 and hp > 0 and hm > 0:
                curvature = tuple(2 * ((plus[k] - p[k]) / hp - (p[k] - minus[k]) / hm) / width for k in (0, 1))
        return cols, curvature


def _least_norm(cols, r):
    """``(rank, d)``: the rank of the 2×k matrix of ``cols`` and ``d = −A⁺ r``."""
    f2 = sum(x * x + y * y for x, y in cols)
    p = 0.0
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            cross = cols[i][0] * cols[j][1] - cols[i][1] * cols[j][0]
            p += cross * cross
    s1sq = (f2 + math.sqrt(max(f2 * f2 - 4 * p, 0.0))) / 2
    s1 = math.sqrt(s1sq)
    s2 = math.sqrt(p / s1sq) if s1sq > 0 else 0.0
    threshold = RANK_EPSILON * max(1.0, s1)
    if s1 <= threshold:
        return 0, [0.0] * len(cols)
    if s2 <= threshold:
        return 1, [-(x * r[0] + y * r[1]) / f2 for x, y in cols]
    a = sum(x * x for x, _ in cols)
    b = sum(x * y for x, y in cols)
    d = sum(y * y for _, y in cols)
    wx = (d * r[0] - b * r[1]) / p
    wy = (a * r[1] - b * r[0]) / p
    return 2, [-(x * wx + y * wy) for x, y in cols]


def _rank(cols) -> int:
    return _least_norm(cols, (0.0, 0.0))[0]


def _step(problem: _Problem, cols, u, r):
    """``(delta, moved, frozen)``: the step of every variable, the length of
    the predicted move of the point and whether a variable is frozen at a
    clamp bound."""
    m = len(cols)
    free = list(range(m))
    delta = [0.0] * m
    while True:
        _rank_f, d = _least_norm([cols[j] for j in free], r)
        delta = [0.0] * m
        for k, j in enumerate(free):
            delta[j] = d[k] * problem.vars[j].c
        out = [j for j in free
               if (problem.vars[j].lo is not None and u[j] <= problem.vars[j].lo and delta[j] < 0)
               or (problem.vars[j].hi is not None and u[j] >= problem.vars[j].hi and delta[j] > 0)]
        if not out:
            break
        free = [j for j in free if j not in out]
    mx = sum(cols[j][0] * delta[j] / problem.vars[j].c for j in free)
    my = sum(cols[j][1] * delta[j] / problem.vars[j].c for j in free)
    return delta, math.hypot(mx, my), len(free) < m


def _length(problem: _Problem, cols, curvature, r, moved) -> float:
    """The first trial length ``λ₀`` of a step.

    ``1`` for two or more variables. For a single variable with
    ``a = |J|²`` and ``b = r·f″`` (``f″`` the second difference of the
    stencil): ``1`` when ``|b| ≤ CURVATURE_FLOOR · a`` (a straight image);
    ``a / (a + b)`` when ``a + b > 0`` (the Newton step of ``|r|²/2``: a
    curved image far from the target makes the plain step overshoot or fall
    short by that factor); ``L = max(1, S / moved)`` when ``a + b ≤ 0`` (the
    point is near the farthest place from the target, the plain step is
    tiny). A length above 1 is at most ``L``: the predicted move
    ``λ₀ · moved`` stays within the scene scale ``S``."""
    if len(cols) != 1:
        return 1.0
    c = problem.vars[0].c
    jx, jy = cols[0][0] / c, cols[0][1] / c
    a = jx * jx + jy * jy
    b = r[0] * curvature[0] + r[1] * curvature[1]
    if a <= 0 or abs(b) <= CURVATURE_FLOOR * a:
        return 1.0
    longest = max(1.0, problem.scale / moved)
    if a + b <= 0:
        return longest
    return min(a / (a + b), longest)


def _farthest(problem: _Problem, cols, curvature, r) -> bool:
    """A stationary single variable at a local maximum of the distance (the
    target straight across a curved path): ``a + b < −CURVATURE_FLOOR · a``
    with ``a = |J|²``, ``b = r·f″``."""
    if len(cols) != 1:
        return False
    c = problem.vars[0].c
    a = (cols[0][0] / c) ** 2 + (cols[0][1] / c) ** 2
    b = r[0] * curvature[0] + r[1] * curvature[1]
    return a + b < -CURVATURE_FLOOR * a


def _line_search(problem: _Problem, u, delta, length, target, norm):
    """``(|r|, u, point)`` of the step taken, ``None`` when none is.

    Trials ``λ = λ₀, λ₀/2, …`` (``MAX_HALVINGS + 1`` at most), each clamped
    into the clamped ranges, with ``ε = ACCEPT_SLACK · tol``: the first
    defined trial is kept, a later one replaces it only when its ``|r|`` is
    below the kept one by more than ``ε``; the search stops at a kept
    ``|r| ≤ tol``, and at a defined trial that does not replace a kept one
    within ``|r| + ε`` (it halves while that improves). The kept trial is
    taken when it is within ``|r| + ε``. The slack keeps the rounding of
    ``|r|`` out of the choice at a stationary point far from the target."""
    slack = ACCEPT_SLACK * problem.tol
    limit = norm + slack
    best = None
    for _ in range(MAX_HALVINGS + 1):
        trial = problem.clamp([u[j] + length * delta[j] for j in range(len(u))])
        q = problem.point(trial)
        if q is not None:
            dist = math.hypot(q[0] - target[0], q[1] - target[1])
            if best is None or dist < best[0] - slack:
                best = (dist, trial, q)
                if dist <= problem.tol:
                    break
            elif best[0] <= limit:
                break
        length /= 2
    return best if best is not None and best[0] <= limit else None


def _target(target) -> tuple:
    try:
        x, y = target
        x, y = float(x), float(y)
    except (TypeError, ValueError):
        raise ValueError('target must be a pair of finite numbers (x, y)') from None
    if not (math.isfinite(x) and math.isfinite(y)):
        raise ValueError('target must be a pair of finite numbers (x, y)')
    return x, y


def _new_inputs(inputs, entries) -> dict:
    out = copy.deepcopy(dict(inputs or {}))
    out.update(entries)
    return out


def _gauss_newton(problem: _Problem, target, max_iterations) -> DragResult:
    inputs = problem.given
    if not problem.ready:
        return DragResult('no_convergence', inputs)
    u = problem.u0
    p = problem.point(u)
    if p is None:
        return DragResult('no_convergence', inputs)
    stencil = problem.jacobian(u, p)
    if stencil is None:
        return DragResult('no_convergence', inputs, residual=math.hypot(p[0] - target[0], p[1] - target[1]))
    cols, curvature = stencil
    rank0 = _rank(cols)
    if rank0 < min(2, len(problem.vars)):
        return DragResult('singular', inputs, residual=math.hypot(p[0] - target[0], p[1] - target[1]))
    tol = problem.tol
    r = (p[0] - target[0], p[1] - target[1])
    norm = math.hypot(*r)
    steps = 0
    while norm > tol and steps < max_iterations and cols is not None:
        delta, moved, _frozen = _step(problem, cols, u, r)
        if moved <= tol:
            break
        taken = _line_search(problem, u, delta, _length(problem, cols, curvature, r, moved), target, norm)
        if taken is None:
            break
        norm, u, p = taken
        r = (p[0] - target[0], p[1] - target[1])
        steps += 1
        if norm > tol:
            stencil = problem.jacobian(u, p)
            cols, curvature = stencil if stencil is not None else (None, None)
    if norm <= tol:
        status = 'ok'
    elif cols is None:
        status = 'no_convergence'
    else:
        _delta, moved, frozen = _step(problem, cols, u, r)
        if moved <= tol and frozen:
            status = 'clamped'
        elif moved <= tol and rank0 < 2 and not _farthest(problem, cols, curvature, r):
            status = 'ok'
        else:
            status = 'no_convergence'
    if status in ('no_convergence', 'singular'):
        return DragResult(status, inputs, steps, norm)
    return DragResult(status, _new_inputs(inputs, problem.entries(u)), steps, norm)


def _project(doc, inputs, element_id, target) -> DragResult:
    rest = evaluate(doc, inputs=inputs)
    found = _path_range(doc, rest.elements, element_id)
    if found is None:
        return DragResult('no_convergence', inputs)
    frame, lo, hi, outside = found
    tol = rest.tolerances.decide_length
    t = _paths.project(frame, target[0], target[1], tol)
    at = _paths.point_at(frame, t)
    residual = math.hypot(at['x'] - target[0], at['y'] - target[1])
    status = 'ok'
    if outside == 'clamp' and residual > tol and (t == lo or (hi is not None and t == hi)):
        status = 'clamped'
    current = dict(doc.inputs)
    current.update(inputs or {})
    value = {'kind': 'pathParameter', 'value': t}
    if isinstance(current.get(element_id), dict) and 'branch' in current[element_id]:
        value['branch'] = current[element_id]['branch']
    return DragResult(status, _new_inputs(inputs, {element_id: value}), 0, residual)


def _drag_on_function(doc, inputs, element_id, target) -> DragResult:
    """``point.on_function`` without a hint: the input becomes the x of the
    target, clamped into the domain (``clamped`` when that moves it); no
    value of the function there — ``no_convergence``."""
    rest = evaluate(doc, inputs=inputs)
    domain = _function_domain(doc, rest.elements, element_id)
    if domain is None:
        return DragResult('no_convergence', inputs)
    lo, hi = domain
    x = target[0]
    status = 'ok'
    if lo is not None and x < lo:
        x, status = float(lo), 'clamped'
    if hi is not None and x > hi:
        x, status = float(hi), 'clamped'
    new = _new_inputs(inputs, {element_id: {'kind': 'pathParameter', 'value': x}})
    rec = evaluate(doc, inputs=new).elements[element_id]
    if rec['state'] != 'defined':
        return DragResult('no_convergence', inputs)
    residual = math.hypot(rec['value']['x'] - target[0], rec['value']['y'] - target[1])
    return DragResult(status, new, 0, residual)


def solve(doc, inputs, element_id: str, target, *, max_iterations: int = MAX_ITERATIONS) -> DragResult:
    """:func:`drag` with the number of steps and the residual (for tests and
    diagnostics); ``max_iterations`` limits the Gauss–Newton steps."""
    doc = as_document(doc)
    if element_id not in doc.elements:
        raise ValueError(f'unknown element {element_id!r}')
    if doc.elements[element_id]['type'] != 'point':
        raise ValueError(f'element {element_id!r} is a {doc.elements[element_id]["type"]}, not a point')
    target = _target(target)
    check_inputs(doc, inputs)
    kind = _via_kind(doc, element_id)
    if kind == 'point':
        entry = {element_id: {'kind': 'point', 'value': [target[0], target[1]]}}
        return DragResult('ok', _new_inputs(inputs, entry), 0, 0.0)
    via = drag_via(doc, element_id)
    if via is not None:
        problems = _via_problems(doc, element_id, via)
        if problems:
            i, code, message = problems[0]
            raise ValueError(f'appearance.{element_id}.drag.via[{i}]: {message} ({code})')
        return _gauss_newton(_Problem(doc, inputs, element_id, via), target, max_iterations)
    if kind == 'pathParameter' and _on_function(doc, element_id):
        return _drag_on_function(doc, inputs, element_id, target)
    if kind == 'pathParameter':
        return _project(doc, inputs, element_id, target)
    raise ValueError(f'element {element_id!r} is not free and has no appearance.{element_id}.drag.via')


def drag(doc, inputs, element_id: str, target) -> dict:
    """Move the point ``element_id`` towards ``target = (x, y)``.

    ``inputs`` are the input values of the case (``{elementId: input}``, as in
    :func:`~animageo.native.evaluate`; ``None`` — none). Returns ``{"inputs",
    "status"}``: on ``ok`` and ``clamped`` a new dict — the given entries
    (copied) and the new values of the moved inputs; on ``no_convergence``
    and ``singular`` the given ``inputs`` object itself, unchanged. The input
    is never changed.

    A free point goes to ``target`` (``ok``); a point on a path without a
    hint takes the parameter of the nearest point of its path (``clamped``
    when it stops at an end of a clamped range away from the target); a
    point on a graph without a hint takes the x of the target, clamped into
    the domain (``clamped`` when that moves it); a
    point with ``appearance.<id>.drag.via`` is solved by Gauss–Newton over
    the ``via`` inputs (docs/native/kernel.md §8.1). ``ValueError``: an
    unknown element, not a point, a bad target or ``inputs``, a dependent
    point without a hint, a hint that cannot drive it.
    """
    result = solve(doc, inputs, element_id, target)
    return {'inputs': result.inputs, 'status': result.status}


# ── validate ─────────────────────────────────────────────────────────────


def _rest_rank(doc: NativeDocument, el_id: str, via: list):
    """``(rank, variables)`` of ``∂el_id/∂via`` at rest, ``None`` when the
    point or a stencil point is not defined."""
    problem = _Problem(doc, None, el_id, via)
    if not problem.ready:
        return None
    p = problem.point(problem.u0)
    stencil = problem.jacobian(problem.u0, p) if p is not None else None
    if stencil is None:
        return None
    return _rank(stencil[0]), len(stencil[0])


def drag_issues(doc: NativeDocument) -> list:
    """The issues of the ``drag`` hints of a structurally valid document:
    ``dangling_ref``, ``type_mismatch``, ``drag_via_not_free``,
    ``drag_via_not_upstream`` (errors) and ``drag_singular`` (warning)."""
    appearance = doc.data.get('appearance')
    out = []
    if not isinstance(appearance, dict):
        return out
    for el_id in sorted(appearance):
        entry = appearance[el_id]
        if not isinstance(entry, dict) or 'drag' not in entry:
            continue
        base = '/appearance' + _pointer(el_id) + '/drag'
        raw = entry['drag']['via']
        via = [raw] if isinstance(raw, str) else list(raw)
        paths = [base + '/via'] if isinstance(raw, str) else [f'{base}/via/{i}' for i in range(len(via))]
        el = doc.elements.get(el_id)
        if el is None:
            out.append(Issue('dangling_ref', base, f'element {el_id!r} does not exist'))
            continue
        if el['type'] != 'point':
            out.append(Issue('type_mismatch', base, f"only a point is dragged; {el_id!r} is a {el['type']}",
                             elementId=el_id))
            continue
        problems = _via_problems(doc, el_id, via)
        for i, code, message in problems:
            out.append(Issue(code, paths[i], message, elementId=el_id))
        if problems:
            continue
        found = _rest_rank(doc, el_id, via)
        if found is not None and found[0] < min(2, found[1]):
            out.append(Issue('drag_singular', base + '/via',
                             f'{el_id!r} moves in {found[0]} of {min(2, found[1])} directions through '
                             f'{", ".join(via)} at rest', elementId=el_id, severity='warning'))
    return out
