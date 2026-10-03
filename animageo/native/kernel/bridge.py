"""Document → classic ``animageo.geo.Construction`` (render and animation path).

``build_construction(doc, *, inputs=None, seed=None) → (Construction, names)``: every
element becomes a classic element named ``names.by_id[id]``; a free point is
a level-0 ``Element`` (like a free point of a ``.ggb``); every other
operation is a :class:`NativeCommand` whose function runs the kernel
implementation (``IMPLEMENTATIONS``) on values converted from the classic
data and converts the result back. ``rebuild(full=True)`` therefore gives the
values of :func:`~animageo.native.evaluate` (the bridge identity test).

Elements are created in the order of the operations (Kahn's order of
``evaluate``, ties by operation ID; outputs by slot), as a DSL creates them
line by line; the renderer breaks z-index ties by this order. Structurally
broken operations (a cycle, an op not in the registry, argument errors, a
free op without a valid input) get no command: their elements, created last
in ID order, stay ``None``. An undefined result is ``None`` as well.

A free number (``number.free``) is a level-0 ``Var`` holding the kernel
value (clamped to ``min``/``max``; ``None`` when undefined). Values convert
by type: a vector is a classic ``Vector``; a number is a ``float``
(``scalar``), a ``Measure`` of dimension 1 or 2 (``length``, ``area``), an
``AngleSize`` (``angle``) or a ``Measure`` of dimension 0 (``count``). Params
and number literals are constants of the command, not classic inputs.

This module imports ``animageo.geo`` (and numpy) inside its functions only,
so ``import animageo.native`` stays free of the classic code; ``animageo.geo``
itself does not need manim.
"""
from __future__ import annotations

import math
import re
from typing import NamedTuple

from ..registry import registry
from . import paths
from .evaluate import _argument_status, _order, number_literal, valid_input
from .numeric import scene_scale, tolerances
from .ops import IMPLEMENTATIONS, OpContext
from .values import Detailed, Input, Undefined, is_finite_value

__all__ = ['Names', 'build_construction', 'classic_name', 'to_classic', 'from_classic']

_UUID_RE = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')


class Names(NamedTuple):
    """``by_id``: element ID → classic name; ``by_name``: the inverse."""

    by_id: dict
    by_name: dict


def classic_name(element_id: str) -> str:
    """``e_<id>``: a UUID as 32 hex digits, other characters outside
    ``[A-Za-z0-9_]`` as ``_`` (collisions are resolved by :func:`build_names`)."""
    if _UUID_RE.match(element_id):
        return 'e_' + element_id.replace('-', '').lower()
    return 'e_' + re.sub(r'[^A-Za-z0-9_]', '_', element_id)


def build_names(element_ids) -> Names:
    """Classic names of ``element_ids``; a collision gets ``_2``, ``_3``… in ID order."""
    by_id = {}
    taken = set()
    for el_id in sorted(element_ids):
        base = classic_name(el_id)
        name = base
        k = 2
        while name in taken:
            name = f'{base}_{k}'
            k += 1
        taken.add(name)
        by_id[el_id] = name
    return Names(by_id, {v: k for k, v in by_id.items()})


# ── value conversion ─────────────────────────────────────────────────────

def _fingerprint(obj) -> tuple:
    keys = ('coords', 'normal', 'offset', 'start', 'endpoints', 'center', 'radius', 'vertices', 'value',
            'dimension')
    out = []
    for key in keys:
        value = getattr(obj, key, None)
        if value is not None:
            out.append((key, value.tobytes() if hasattr(value, 'tobytes') else float(value)))
    return tuple(out)


def to_classic(type_: str, value):
    """A kernel value as a classic data object (``None`` for no value).

    The kernel value is cached on the object (``_native``) with a
    fingerprint of its classic fields, so a downstream kernel op reads the
    exact kernel value back (a line's ``p`` is not recomputed from the
    classic normal and offset) unless the object was moved since.
    """
    if value is None:
        return None
    from ...geo.lib_elements import Circle, Line, Point, Polygon, Ray, Segment, Vector
    from ...geo.lib_vars import AngleSize, Measure
    import numpy as np

    if type_ == 'number' and value['unit'] == 'scalar':
        return float(value['value'])      # the data of a classic Var; a float carries no cache

    if type_ == 'point':
        obj = Point([value['x'], value['y']])
    elif type_ == 'segment':
        obj = Segment(np.array(value['a'], dtype=float), np.array(value['b'], dtype=float))
        obj.length = value['length']
    elif type_ == 'line':
        (px, py), (dx, dy) = value['p'], value['dir']
        obj = Line((-dy, dx), -dy * px + dx * py)
    elif type_ == 'ray':
        obj = Ray(np.array(value['origin'], dtype=float), np.array(value['dir'], dtype=float))
    elif type_ == 'circle':
        obj = Circle(np.array(value['c'], dtype=float), value['r'])
    elif type_ == 'polygon':
        obj = Polygon(value['vertices'])
    elif type_ == 'vector':
        obj = Vector(np.array([value['a'], value['b']], dtype=float))
    elif type_ == 'number':
        unit = value['unit']
        if unit == 'angle':
            obj = AngleSize(float(value['value']))
        else:
            obj = Measure(float(value['value']), _MEASURE_DIMENSION.get(unit, 0))
    else:
        raise ValueError(f'no classic type for {type_!r}')
    obj._native = (_fingerprint(obj), value)
    return obj


_MEASURE_DIMENSION = {'length': 1, 'area': 2}     # other units (count) as a dimensionless Measure
_DIMENSION_UNIT = {0: 'scalar', 1: 'length', 2: 'area'}


def _shoelace(pts) -> float:
    acc = 0.0
    n = len(pts)
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[(i + 1) % n]
        acc = acc + (xi * yj - xj * yi)
    return abs(acc) / 2


def from_classic(type_: str, obj):
    """A classic data object as a kernel value of ``type_`` (``None`` for none)."""
    if obj is None:
        return None
    cached = getattr(obj, '_native', None)
    if cached is not None and cached[0] == _fingerprint(obj):
        return cached[1]
    if type_ == 'point':
        return {'x': float(obj.coords[0]), 'y': float(obj.coords[1])}
    if type_ == 'segment':
        (ax, ay), (bx, by) = (map(float, p) for p in obj.endpoints)
        return {'a': [ax, ay], 'b': [bx, by], 'length': math.hypot(bx - ax, by - ay)}
    if type_ == 'line':
        nx, ny = (float(v) for v in obj.normal)
        c = float(obj.offset)
        return {'p': [c * nx, c * ny], 'dir': [ny, -nx]}
    if type_ == 'ray':
        return {'origin': [float(v) for v in obj.start], 'dir': [float(v) for v in obj.direction]}
    if type_ == 'circle':
        return {'c': [float(v) for v in obj.center], 'r': float(obj.radius)}
    if type_ == 'polygon':
        pts = [(float(x), float(y)) for x, y in obj.vertices]
        return {'vertices': [[x, y] for x, y in pts], 'area': _shoelace(pts)}
    if type_ == 'vector':
        (ax, ay), (bx, by) = (map(float, p) for p in obj.endpoints)
        return {'a': [ax, ay], 'b': [bx, by], 'length': math.hypot(bx - ax, by - ay)}
    if type_ == 'number':
        from ...geo.lib_vars import AngleSize, Measure
        if isinstance(obj, AngleSize):
            return {'value': float(obj.value), 'unit': 'angle'}
        if isinstance(obj, Measure):
            return {'value': float(obj.value), 'unit': _DIMENSION_UNIT.get(obj.dimension, 'scalar')}
        if isinstance(obj, (int, float)) and not isinstance(obj, bool):
            return {'value': float(obj), 'unit': 'scalar'}
        raise ValueError(f'no kernel number for {type(obj).__name__}')
    raise ValueError(f'no kernel type for {type_!r}')


# ── commands ─────────────────────────────────────────────────────────────

def _native_command_class():
    from ...geo.lib_commands import Command

    class NativeCommand(Command):
        """A classic command that runs a kernel operation.

        ``name`` is the registry op, ``operation_id`` the document operation;
        ``func()`` returns the kernel wrapper. ``Construction.copy`` keeps
        this class (and these attributes) for ``apply``.
        """

        def __init__(self, op_name, inputs, outputs, operation_id, runner):
            super().__init__(op_name, inputs, outputs)
            self.operation_id = operation_id
            self._runner = runner

        def func(self, log_unsupported=True):
            return self._runner

        def __repr__(self):
            return f'NativeCommand[{self.operation_id}] ' + super().__repr__()

    return NativeCommand


class _Runner:
    """The function of one :class:`NativeCommand`: classic inputs → kernel → classic outputs."""

    def __init__(self, construction, op_name, layout, out_slots, out_types, tol, *,
                 free_value=None, path_frame=None, tparam_of=None, constants=None):
        self.construction = construction
        self.op_name = op_name
        self.layout = layout              # [(slot, is_list, [element type…])]
        self.constants = constants or {}  # params and number literals: {slot: float | None | Input}
        self.out_slots = out_slots
        self.out_types = out_types
        self.tol = tol
        self.free_value = free_value      # point.on_path: the document's input value
        self.path_frame = path_frame      # (producer op, [(slot, is_list, [type…])]) of the path
        self.tparam_of = tparam_of        # classic name of the on_path output
        self.__name__ = op_name

    def __call__(self, *classic):
        none = [None] * len(self.out_slots)
        args = dict(self.constants)
        i = 0
        for slot, is_list, types in self.layout:
            items = []
            for type_ in types:
                value = from_classic(type_, classic[i])
                i += 1
                if value is None:
                    return none
                items.append(Input(type_, value))
            args[slot] = items if is_list else items[0]
        input_value = None
        if self.path_frame is not None:
            producer_op, producer_layout = self.path_frame
            values = {}
            for slot, is_list, types in producer_layout:
                vals = [from_classic(t, classic[i + k]) for k, t in enumerate(types)]
                i += len(types)
                if any(v is None for v in vals):
                    values = None
                    break
                values[slot] = vals if is_list else vals[0]
            path = args['path']
            frame = paths.frame(path.type, path.value, producer_op, values) if values is not None else None
            args['path'] = Input(path.type, path.value, frame)
            element = self.construction.element(self.tparam_of)
            t = getattr(element, 'tparam', None)
            if t is None:
                t = self.free_value['value']
            input_value = {'kind': 'pathParameter', 'value': float(t)}
        result = IMPLEMENTATIONS[self.op_name](args, OpContext(self.tol, input=input_value))
        out = []
        for slot, type_ in zip(self.out_slots, self.out_types):
            value = result.get(slot)
            if isinstance(value, Detailed):
                value = value.value
            if value is None or isinstance(value, Undefined) or not is_finite_value(value):
                out.append(None)
            else:
                out.append(to_classic(type_, value))
        return out


def build_construction(doc, *, inputs=None, seed=None):
    """``(Construction, Names)`` for ``doc`` with ``inputs`` overriding free inputs.

    ``seed`` is passed to ``Construction`` (default: its own default).
    """
    from ...geo.construction import Construction
    from ...geo.lib_elements import Element, Point
    from ...geo.lib_vars import Var
    from ..document import as_document, bound_producer, cyclic_operations, iter_refs, op_dependencies
    from .evaluate import check_inputs

    doc = as_document(doc)
    reg = registry()
    overrides = check_inputs(doc, inputs)
    values_in = dict(doc.inputs)
    values_in.update(overrides)
    ops = doc.operations
    elements = doc.elements
    names = build_names(elements)

    free_points = []
    for el_id in sorted(elements):
        producer = bound_producer(doc, el_id)
        if producer is not None and ops[producer]['op'] == 'point.free' and \
                valid_input('point', values_in.get(el_id)):
            free_points.append(tuple(values_in[el_id]['value']))
    tol = tolerances(scene_scale(doc.bounds, free_points))

    construction = Construction() if seed is None else Construction(seed=seed)
    NativeCommand = _native_command_class()

    bound: dict = {}
    for el_id in sorted(elements):
        producer = bound_producer(doc, el_id)
        record = reg.get(ops[producer]['op']) if producer is not None else None
        if record is None:
            continue
        out_type = reg.output_type(record, elements[el_id]['producer']['slot'], ops[producer]['args'])
        if out_type is not None and out_type == elements[el_id]['type']:
            bound.setdefault(producer, []).append(el_id)

    created = set()
    deps = op_dependencies(doc)
    cyclic = cyclic_operations(deps)
    for op_id in _order(list(ops), deps, cyclic):
        if op_id in cyclic:
            continue
        op = ops[op_id]
        record = reg.get(op['op'])
        if record is None:
            continue
        resolved = _argument_status(op, record, doc, reg)
        if isinstance(resolved, tuple):
            continue
        outs = sorted(bound.get(op_id, ()), key=lambda e: _slot_key(elements[e]['producer']['slot']))
        if not outs:
            continue
        free = record.get('free')
        if free is not None:
            value = values_in.get(outs[0])
            if not valid_input(free['kind'], value):
                continue
            if free['kind'] == 'point':
                construction.add(Element(names.by_id[outs[0]], Point(value['value'])))
                created.add(outs[0])
                continue
            if free['kind'] == 'number':     # a level-0 Var with the kernel value (clamped), None if undefined
                result = IMPLEMENTATIONS[op['op']](dict(resolved.params), OpContext(tol, input=value))
                number = result.get(elements[outs[0]]['producer']['slot'])
                if isinstance(number, Detailed):
                    number = number.value
                defined = number is not None and not isinstance(number, Undefined) and is_finite_value(number)
                construction.add(Var(names.by_id[outs[0]], to_classic('number', number) if defined else None))
                created.add(outs[0])
                continue
        layout = [(slot, is_list, [elements[r]['type'] for r in ids]) for slot, is_list, ids in resolved.refs]
        input_names = [names.by_id[r] for _slot, _is_list, ids in resolved.refs for r in ids]
        constants = dict(resolved.params)
        constants.update({slot: number_literal(v) for slot, v in resolved.literals.items()})
        path_frame = None
        tparam_of = None
        free_value = None
        if free is not None and free['kind'] == 'pathParameter':
            path_id = resolved.refs[0][2][0]
            path_op = ops[elements[path_id]['producer']['operationId']]
            producer_layout = []
            for slot, arg in path_op['args'].items():
                ids = [r for r in iter_refs(arg) if r in elements]
                if not ids:
                    continue
                producer_layout.append((slot, arg.get('kind') == 'list', [elements[r]['type'] for r in ids]))
                input_names += [names.by_id[r] for r in ids]
            path_frame = (path_op['op'], producer_layout)
            tparam_of = names.by_id[outs[0]]
            free_value = values_in[outs[0]]
            construction.add(Element(tparam_of, Point([0.0, 0.0]), tparam=float(free_value['value'])))
            created.add(outs[0])
        for el_id in outs:              # elements in construction order, as a DSL would create them
            if el_id not in created:
                construction.add(Element(names.by_id[el_id], None))
                created.add(el_id)
        runner = _Runner(construction, op['op'], layout,
                         [elements[e]['producer']['slot'] for e in outs],
                         [elements[e]['type'] for e in outs], tol,
                         free_value=free_value, path_frame=path_frame, tparam_of=tparam_of,
                         constants=constants)
        construction.add(NativeCommand(op['op'], input_names, [names.by_id[e] for e in outs], op_id, runner))

    for el_id in sorted(elements):      # elements of broken operations
        if el_id not in created:
            construction.add(Element(names.by_id[el_id], None))
    return construction, names


def _slot_key(slot: str):
    head, _, index = slot.partition('.')
    return (0 if not index else 1, int(index) if index else 0, head)
