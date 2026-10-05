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

Registry 1.4: an arc is a classic ``Arc`` and a sector a ``CircleSector``
whose ``angles`` are the kernel ``[a0, a1]`` as they are (a full arc keeps
``a1 = a0 + 2π``); a polyline is a ``LocusCurve`` of its vertices. A free
``angle`` input (``segment.from_point_length``) is a constant of the
command: the input of the element of the first output slot, ``0`` when absent.

A free number (``number.free``) is a level-0 ``Var`` holding the kernel
value (clamped to ``min``/``max``; ``None`` when undefined). Values convert
by type: a vector is a classic ``Vector``; a number is a ``float``
(``scalar``), a ``Measure`` of dimension 1 or 2 (``length``, ``area``), an
``AngleSize`` (``angle``) or a ``Measure`` of dimension 0 (``count``). Params
and number literals are constants of the command, not classic inputs.

An angle is a classic ``Angle(vertex, side1, side2)`` carrying the kernel
``size``; ``angle.by_points`` gives it the sides ``a − vertex`` and
``b − vertex`` (the classic arc radius depends on their lengths), other
values unit sides along ``a0`` and ``a1``. A right-angle mark is a classic
``Angle`` of its three points (drawn with the right-angle marker, see
``native.appearance_plan``); an equality mark is a :class:`NativeMark` —
no geometry of its own, the renderer draws its ticks on the targets.

A text (``text.free``, 1.4 a5) is a classic ``Text`` with one literal
segment — the filled template — and its top-left corner at the anchor; an
``expr`` tree or a template is a constant of the command, like a param.

Registry 1.5: an altitude on a line or ray side receives the side's two
defining points (``ends`` input, see ``evaluate.side_end_slots``) as extra
classic inputs. A ``locus`` (``locus.of_point``) is a classic ``LocusCurve``
of its defined samples with ``breaks`` where a neighbour is ``null`` or two
neighbours are more than ``0.25·S`` apart (a closed locus joins its last
sample to the first); its command evaluates the document with the current
free inputs of the construction (the kernel samples a subgraph, the
construction has no notion of it).

This module imports ``animageo.geo`` (and numpy) inside its functions only,
so ``import animageo.native`` stays free of the classic code; ``animageo.geo``
itself does not need manim.
"""
from __future__ import annotations

import math
import re
from typing import NamedTuple

from ..registry import FREE_INPUT_DEFAULTS, free_slot, registry
from . import paths
from .evaluate import _argument_status, _order, number_literal, side_end_slots, valid_input
from .numeric import scene_scale, tolerances
from .ops import IMPLEMENTATIONS, OpContext
from .values import Detailed, Input, Undefined, is_finite_value

__all__ = ['Names', 'NativeMark', 'build_construction', 'classic_name', 'to_classic', 'from_classic']

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

class NativeMark:
    """Classic data of an equality mark (``mark.equal_segments``,
    ``mark.equal_angles``): its ``kind`` and ``count`` only. It has no
    geometry and no renderer — ``addAllGeometry`` skips it; the appearance
    plan puts ``tick_count`` on the marked segments and angles."""

    def __init__(self, kind: str, count: int):
        self.kind = kind
        self.count = count

    def __repr__(self):
        return f'NativeMark({self.kind}, {self.count})'


def _fingerprint(obj) -> tuple:
    keys = ('coords', 'normal', 'offset', 'start', 'endpoints', 'center', 'radius', 'vertices', 'value',
            'dimension', 'vertex', 'side1', 'side2', 'kind', 'count', 'angles', 'points', 'position')
    out = []
    for key in keys:
        value = getattr(obj, key, None)
        if isinstance(value, str):
            out.append((key, value))
        elif isinstance(value, (list, tuple)):
            out.append((key, tuple(float(v) for v in value)))
        elif value is not None:
            out.append((key, value.tobytes() if hasattr(value, 'tobytes') else float(value)))
    return tuple(out)


LOCUS_GAP = 0.25     # a locus line breaks between samples farther apart than LOCUS_GAP·S


def locus_runs(value, scale: float):
    """``(points, breaks)`` of a kernel ``locus`` for drawing: the defined
    samples in order and the indices where a new run starts (a neighbour is
    ``null`` or farther than ``LOCUS_GAP·scale``); a closed locus whose first
    and last samples are defined and near repeats the first at the end.
    ``breaks`` is empty for one run."""
    gap = LOCUS_GAP * scale
    samples = value['points']
    points: list = []
    breaks: list = []
    prev = None
    for p in samples:
        if p is None:
            prev = None
            continue
        if points and (prev is None or math.hypot(p[0] - prev[0], p[1] - prev[1]) > gap):
            breaks.append(len(points))
        points.append([float(p[0]), float(p[1])])
        prev = p
    first, last = (samples[0], samples[-1]) if samples else (None, None)
    if value.get('closed') and first is not None and last is not None and len(points) > 1 \
            and math.hypot(first[0] - last[0], first[1] - last[1]) <= gap:
        points.append([float(first[0]), float(first[1])])
    return points, breaks


def to_classic(type_: str, value, *, sides=None, scale=None):
    """A kernel value as a classic data object (``None`` for no value).

    The kernel value is cached on the object (``_native``) with a
    fingerprint of its classic fields, so a downstream kernel op reads the
    exact kernel value back (a line's ``p`` is not recomputed from the
    classic normal and offset) unless the object was moved since.

    ``sides``: ``(side1, side2)`` vectors of an ``angle`` (default: unit
    vectors along ``a0`` and ``a1``), or ``(vertex, side1, side2)`` of a
    ``right_angle`` mark (without them the mark is a :class:`NativeMark`).
    ``scale``: the scene scale ``S`` of a ``locus`` (its break distance).
    """
    if value is None:
        return None
    from ...geo.lib_elements import Angle, Arc, Circle, CircleSector, Line, LocusCurve, Point, Polygon, Ray, \
        Segment, Text, Vector
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
    elif type_ in ('arc', 'sector'):
        cls = Arc if type_ == 'arc' else CircleSector
        obj = cls(np.array(value['c'], dtype=float), value['r'], [value['a0'], value['a1']])
        obj.angles = [float(value['a0']), float(value['a1'])]     # the kernel angles (a full arc stays full)
    elif type_ == 'polyline':
        obj = LocusCurve(value['vertices'])
    elif type_ == 'locus':
        points, breaks = locus_runs(value, 1.0 if scale is None else float(scale))
        if not points:
            return None
        obj = LocusCurve(points, breaks=breaks or None)
    elif type_ == 'vector':
        obj = Vector(np.array([value['a'], value['b']], dtype=float))
    elif type_ == 'angle':
        if sides is None:
            a0, a1 = value['a0'], value['a1']
            sides = ((math.cos(a0), math.sin(a0)), (math.cos(a1), math.sin(a1)))
        obj = Angle(np.array(value['vertex'], dtype=float), np.array(sides[0], dtype=float),
                    np.array(sides[1], dtype=float))
        obj.size = float(value['size'])                 # the kernel size, not the classic difference
        obj.end_angle = obj.start_angle + obj.size
    elif type_ == 'mark':
        if value['kind'] == 'right_angle' and sides is not None:
            vertex, side1, side2 = (np.array(v, dtype=float) for v in sides)
            obj = Angle(vertex, side1, side2)
        else:
            obj = NativeMark(value['kind'], int(value['count']))
    elif type_ == 'number':
        unit = value['unit']
        if unit == 'angle':
            obj = AngleSize(float(value['value']))
        else:
            obj = Measure(float(value['value']), _MEASURE_DIMENSION.get(unit, 0))
    elif type_ == 'text':               # a plain classic text of the filled template, top-left at the anchor
        obj = Text([('str', value['text'])], position=value['anchor'])
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
    if type_ in ('arc', 'sector'):
        from .ops.angle import TWO_PI, normalize_angle
        a0 = normalize_angle(float(obj.angles[0]))
        sweep = min(max(float(obj.angles[1]) - float(obj.angles[0]), 0.0), TWO_PI)
        return {'c': [float(v) for v in obj.center], 'r': float(obj.radius), 'a0': a0, 'a1': a0 + sweep}
    if type_ == 'polyline':
        pts = [(float(x), float(y)) for x, y in obj.points]
        length = 0.0
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            length = length + math.hypot(x1 - x0, y1 - y0)
        return {'vertices': [[x, y] for x, y in pts], 'length': length}
    if type_ == 'locus':     # a moved curve: its points as an open locus of the same samples
        pts = [[float(x), float(y)] for x, y in obj.points]
        return {'points': pts, 'range': [0.0, float(max(len(pts) - 1, 0))], 'closed': False}
    if type_ == 'angle':
        from .ops.angle import angle_size, normalize_angle
        (s1x, s1y), (s2x, s2y) = (map(float, v) for v in (obj.side1, obj.side2))
        l1, l2 = math.hypot(s1x, s1y), math.hypot(s2x, s2y)
        if l1 == 0 or l2 == 0:
            return None
        ua, ub = (s1x / l1, s1y / l1), (s2x / l2, s2y / l2)
        a0 = normalize_angle(math.atan2(ua[1], ua[0]))
        size = angle_size(ua, ub)
        return {'vertex': [float(v) for v in obj.vertex], 'a0': a0, 'a1': a0 + size, 'size': size}
    if type_ == 'mark':
        if isinstance(obj, NativeMark):
            return {'kind': obj.kind, 'count': int(obj.count)}
        return {'kind': 'right_angle', 'count': 1}     # a classic Angle drawn as a right-angle mark
    if type_ == 'number':
        from ...geo.lib_vars import AngleSize, Measure
        if isinstance(obj, AngleSize):
            return {'value': float(obj.value), 'unit': 'angle'}
        if isinstance(obj, Measure):
            return {'value': float(obj.value), 'unit': _DIMENSION_UNIT.get(obj.dimension, 'scalar')}
        if isinstance(obj, (int, float)) and not isinstance(obj, bool):
            return {'value': float(obj), 'unit': 'scalar'}
        raise ValueError(f'no kernel number for {type(obj).__name__}')
    if type_ == 'text':
        text = ''.join(s for kind, s in obj.segments if kind == 'str')
        return {'anchor': [float(v) for v in obj.position[:2]], 'text': text, 'parts': [{'text': text}] if text else []}
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
                 free_value=None, path_frame=None, tparam_of=None, constants=None, free_input=None,
                 end_slots=()):
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
        self.free_input = free_input      # a free angle input: the document's (or default) input value
        self.end_slots = end_slots        # slots whose side gets the two defining points (registry 1.5)
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
        input_value = self.free_input
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
        for slot in self.end_slots:
            a, b = (from_classic('point', classic[i + k]) for k in range(2))
            i += 2
            side = args[slot]
            frame = ((a['x'], a['y']), (b['x'], b['y'])) if a is not None and b is not None else None
            args[slot] = Input(side.type, side.value, frame)
        result = IMPLEMENTATIONS[self.op_name](args, OpContext(self.tol, input=input_value))
        out = []
        for slot, type_ in zip(self.out_slots, self.out_types):
            value = result.get(slot)
            if isinstance(value, Detailed):
                value = value.value
            if value is None or isinstance(value, Undefined) or not is_finite_value(value):
                out.append(None)
            else:
                out.append(to_classic(type_, value, sides=_classic_sides(self.op_name, type_, args)))
        return out


class _LocusRunner:
    """The function of a ``locus.of_point`` command: the document evaluated with
    the current free inputs of the construction, its locus as a classic
    ``LocusCurve`` (or ``None``)."""

    def __init__(self, construction, doc, names, values_in, element_id, free_ids):
        self.construction = construction
        self.doc = doc
        self.names = names
        self.values_in = values_in
        self.element_id = element_id
        self.free_ids = free_ids          # [(element ID, input kind)] of the free operations
        self.__name__ = 'locus.of_point'

    def _inputs(self):
        inputs = {}
        for el_id, kind in self.free_ids:
            element = self.construction.objectByName(self.names.by_id[el_id])
            data = getattr(element, 'data', None)
            if kind == 'point' and data is not None:
                value = from_classic('point', data)
                inputs[el_id] = {'kind': 'point', 'value': [value['x'], value['y']]}
            elif kind == 'number' and isinstance(data, (int, float)) and not isinstance(data, bool):
                inputs[el_id] = {'kind': 'number', 'value': float(data)}
            elif kind == 'pathParameter' and getattr(element, 'tparam', None) is not None:
                inputs[el_id] = {'kind': 'pathParameter', 'value': float(element.tparam)}
            elif el_id in self.values_in:
                inputs[el_id] = self.values_in[el_id]
        return inputs

    def __call__(self, *classic):
        from .evaluate import evaluate
        if any(c is None for c in classic):
            return [None]
        ev = evaluate(self.doc, inputs=self._inputs())
        record = ev.elements[self.element_id]
        if record['state'] != 'defined':
            return [None]
        return [to_classic('locus', record['value'], scale=ev.tolerances.scale)]


def _classic_sides(op_name, type_, args):
    """The ``sides`` of :func:`to_classic` from the producer's arguments."""
    if op_name not in ('angle.by_points', 'mark.right_angle'):
        return None
    v = args['vertex'].value
    side1 = (args['a'].value['x'] - v['x'], args['a'].value['y'] - v['y'])
    side2 = (args['b'].value['x'] - v['x'], args['b'].value['y'] - v['y'])
    if type_ == 'angle':
        return side1, side2
    return (v['x'], v['y']), side1, side2


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
        out_type = reg.output_type(record, elements[el_id]['producer']['slot'], ops[producer]['args'], doc)
        if out_type is not None and out_type == elements[el_id]['type']:
            bound.setdefault(producer, []).append(el_id)

    free_ids = []                       # the free inputs a locus command reads back from the construction
    for op_id in sorted(bound):
        free = reg.get(ops[op_id]['op']).get('free')
        if free is None:
            continue
        for el_id in bound[op_id]:
            if elements[el_id]['producer']['slot'] == free_slot(reg.get(ops[op_id]['op'])):
                free_ids.append((el_id, free['kind']))

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
            holders = [e for e in outs if elements[e]['producer']['slot'] == free_slot(record)]
            if not holders:
                continue
            value = values_in.get(holders[0])
            if value is None:
                value = FREE_INPUT_DEFAULTS.get(free['kind'])
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
        if op['op'] == 'locus.of_point':
            for el_id in outs:
                construction.add(Element(names.by_id[el_id], None))
                created.add(el_id)
            runner = _LocusRunner(construction, doc, names, values_in, outs[0], free_ids)
            construction.add(NativeCommand(op['op'], input_names, [names.by_id[e] for e in outs], op_id, runner))
            continue
        constants = dict(resolved.params)
        constants.update({slot: number_literal(v) for slot, v in resolved.literals.items()})
        constants.update({slot: Input('expr', ast) for slot, ast in resolved.exprs.items()})
        constants.update({slot: Input('template', s) for slot, s in resolved.templates.items()})
        path_frame = None
        tparam_of = None
        free_value = None
        free_input = value if free is not None and free['kind'] == 'angle' else None
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
        end_slots = []
        for item in record['inputs']:
            if not item.get('ends'):
                continue
            ids = next((ids for slot, is_list, ids in resolved.refs if slot == item['slot'] and not is_list), None)
            if not ids:
                continue
            side_op = ops[elements[ids[0]]['producer']['operationId']]
            slots = side_end_slots(elements[ids[0]]['type'], side_op['op'])
            if slots is None:
                continue
            ends = [[r for r in iter_refs(side_op['args'].get(s) or {}) if r in elements] for s in slots]
            if all(len(e) == 1 and elements[e[0]]['type'] == 'point' for e in ends):
                end_slots.append(item['slot'])
                input_names += [names.by_id[e[0]] for e in ends]
        for el_id in outs:              # elements in construction order, as a DSL would create them
            if el_id not in created:
                construction.add(Element(names.by_id[el_id], None))
                created.add(el_id)
        runner = _Runner(construction, op['op'], layout,
                         [elements[e]['producer']['slot'] for e in outs],
                         [elements[e]['type'] for e in outs], tol,
                         free_value=free_value, path_frame=path_frame, tparam_of=tparam_of,
                         constants=constants, free_input=free_input, end_slots=end_slots)
        construction.add(NativeCommand(op['op'], input_names, [names.by_id[e] for e in outs], op_id, runner))

    for el_id in sorted(elements):      # elements of broken operations
        if el_id not in created:
            construction.add(Element(names.by_id[el_id], None))
    return construction, names


def _slot_key(slot: str):
    head, _, index = slot.partition('.')
    return (0 if not index else 1, int(index) if index else 0, head)
