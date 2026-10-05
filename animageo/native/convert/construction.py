"""Classic ``Construction`` → document by the table ``dsl_map.json`` (plan L5 §3.4).

:func:`translate` walks the free objects and then ``constr.commands`` in the
order of the construction (topological), looks every command up by its
classic key (``strFullCommand``) and builds operations of the registry with
IDs ``uuid5(namespace, key)`` (:mod:`.keys`). What does not translate gets a
reason; what depends on it is the closure. The document is checked by
``validate`` (an operation it rejects is untranslated with the issue as the
detail, its dependents the closure); the slots of ``byValue`` outputs are
chosen by value with one evaluation of a probe document in which every slot
is bound; the final document is evaluated once more and every translated
element is measured against its expected value (:mod:`.values`).

The classic code is loaded inside the functions only (it needs numpy; it
does not need manim).
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field

from ..registry import REGISTRY_VERSION, registry
from .keys import KeyMaker, document_id, element_id, operation_id
from .mapping import dsl_map
from .values import TOL_IMPORT, classic_report_value, compare, native_report_value

__all__ = ['ConvertError', 'Record', 'Context', 'Translation', 'translate', 'DOCUMENT_BOUNDS']

DOCUMENT_BOUNDS = [-10.0, -6.0, 10.0, 6.0]
AXES = ('xAxis', 'yAxis')
_XML_SHORTCUTS = {'point': 'p', 'segment': 's', 'line': 'l', 'ray': 'r', 'polygon': 'P', 'vector': 'v',
                  'numeric': 'i', 'angle': 'A', 'conicpart': 'C'}


class ConvertError(ValueError):
    """``mode="strict"``: something does not translate; ``items`` — the records."""

    def __init__(self, items):
        self.items = list(items)
        first = self.items[0] if self.items else {}
        super().__init__(f'{len(self.items)} object(s) do not translate'
                         + (f', first {first.get("name")}: {first.get("reason")}' if first else ''))


@dataclass
class Record:
    """What became of one classic object."""

    name: str
    key: str
    display: str
    command: str | None = None          # command name (GGB / DSL factory), None — free
    signature: str | None = None        # classic key
    status: str = 'translated'          # translated | untranslated | closure
    reason: str | None = None
    detail: str | None = None
    free: bool = False
    native_ids: list = field(default_factory=list)
    inputs: list = field(default_factory=list)       # classic names of the direct inputs
    type: str | None = None             # native type of the first element
    value_check: str = 'not_checked'
    expected: dict | None = None
    native_value: dict | None = None
    delta: float | None = None
    op_id: str | None = None
    order: int = 0

    def to_item(self) -> dict:
        out = {'name': self.name, 'key': self.key, 'command': self.command, 'signature': self.signature,
               'reason': self.reason}
        if self.detail:
            out['detail'] = self.detail
        return out


@dataclass
class Context:
    """What the caller knows besides the construction (``from_ggb`` fills it)."""

    namespace: object
    prefix: str = 'dsl'
    mode: str = 'strict'
    display: dict = field(default_factory=dict)       # classic name → label / variable name
    keys: dict = field(default_factory=dict)          # classic name → key given by the caller (key_of)
    order: dict = field(default_factory=dict)         # classic name → position in the source
    expected: dict = field(default_factory=dict)      # classic name → report value (GGB XML)
    free_points: dict = field(default_factory=dict)   # classic name → [x, y] of a free point
    free_numbers: dict = field(default_factory=dict)  # classic name → {value, min?, max?, step?, angle?}
    xml_types: dict = field(default_factory=dict)     # classic name → GGB element type
    forced: dict = field(default_factory=dict)        # classic name → (reason, detail) decided by the caller
    appearance: dict = field(default_factory=dict)    # classic name → appearance entry
    bounds: list | None = None
    origin_of: object = None


@dataclass
class Translation:
    document: dict
    records: dict          # classic name → Record
    names: list            # classic names in source order
    warnings: list
    scale: float = 1.0


def _ref(eid):
    return {'kind': 'ref', 'elementId': eid}


def _num(v):
    return {'kind': 'number', 'value': float(v)}


# the notes of ``dsl_map.json`` (English, for the table) → ``detail`` of the report (for people, in Russian)
NOTE_DETAILS = {
    'coordinates, conics and functions: the ops come with stage L4':
        'коники, функции и координаты пока не переносятся в редактируемый чертёж',
    'arithmetic of values (number.expression is not built from it)': 'вычисление по значениям пока не переносится',
    'a check or a boolean, not a construction': 'проверка или логическое значение, а не построение',
    'the registry intersects lines, circles and sectors only': 'пересекаются только прямые, окружности и дуги',
    'this kind of object or argument is not transformed by the op': 'такой объект или аргумент операция не принимает',
    'a point by coordinates or a fixed path parameter given by numbers':
        'точка задана числами (координаты или параметр на пути)',
    'common tangents of two circles have no op': 'общие касательные двух окружностей пока не строятся',
}


class _Untranslated(Exception):
    def __init__(self, reason, detail=None, deps=()):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail
        self.deps = list(deps)


def _literal(data):
    """A classic constant as a float (``None`` — not a number)."""
    from ...geo.lib_vars import AngleSize, Measure
    if isinstance(data, bool):
        return None
    if isinstance(data, (int, float)):
        return float(data)
    if isinstance(data, (AngleSize, Measure)):
        return float(data.value)
    return None


class _Builder:
    def __init__(self, constr, ctx: Context):
        from ...geo.lib_commands import strFullCommand, type_to_shortcut
        from ...geo.lib_elements import Point
        self._strFullCommand = strFullCommand
        self._shortcuts = type_to_shortcut
        self._Point = Point
        self.constr = constr
        self.ctx = ctx
        self.ns = ctx.namespace
        self.reg = registry()
        self.table = dsl_map()
        self.keys = KeyMaker(ctx.prefix, ctx.display)
        self.keys.keys.update(ctx.keys)
        self.records: dict = {}
        self.doc = {
            'format': 'animageo-construction/v1',
            'documentId': document_id(self.ns),
            'operationRegistryVersion': REGISTRY_VERSION,
            'operations': {},
            'elements': {},
            'inputs': {},
            'appearance': {},
            'viewDefaults': {'bounds': list(ctx.bounds or DOCUMENT_BOUNDS)},
            'bindings': {'legacyNames': {}},
        }
        self.element_of: dict = {}       # classic name → native element ID
        self.on_path: list = []          # (classic name, element ID)
        self.by_value: dict = {}         # op ID → {slots, outputs: [(name, provisional slot)]}
        self.warnings: list = []

    # -- helpers ------------------------------------------------------------
    def data_of(self, name):
        obj = self.constr.objectByName(name) if isinstance(name, str) else None
        return obj.data if obj is not None else None

    def is_object(self, name) -> bool:
        return isinstance(name, str) and self.constr.objectByName(name) is not None

    def signature(self, cmd, inputs) -> str:
        datas = []
        for inp in inputs:
            if isinstance(inp, str):
                datas.append(self.constr.dataByStr(inp))
            else:
                datas.append(getattr(inp, 'data', inp))
        key = self._strFullCommand(cmd.name, datas)
        if '?' in key:
            codes = []
            for inp, data in zip(inputs, datas):
                code = self._shortcuts.get(type(data))
                if code is None and isinstance(inp, str):
                    code = _XML_SHORTCUTS.get(self.ctx.xml_types.get(self.ctx.display.get(inp, inp)))
                codes.append(code or '?')
            from ...geo.lib_commands import strCommand
            base = strCommand(cmd.name)
            key = base if base == 'polygon' and set(codes) == {'p'} else f'{base}_{"".join(codes)}'
        return key

    def key_for(self, name, signature=None, input_keys=(), number=0) -> str:
        if KeyMaker.is_phantom(name):
            return self.keys.phantom(name, signature or 'value', input_keys, number)
        return self.keys.named(name)

    def record(self, name, **kw) -> Record:
        rec = self.records.get(name)
        if rec is None:
            display = '' if KeyMaker.is_phantom(name) else self.ctx.display.get(name, name)
            rec = Record(name=name, key=kw.pop('key'), display=display,
                         order=self.ctx.order.get(name, 10 ** 6 + len(self.records)))
            self.records[name] = rec
        else:
            kw.pop('key', None)
        for k, v in kw.items():
            setattr(rec, k, v)
        return rec

    def add_element(self, name, rec, op_id, slot, type_):
        eid = element_id(self.ns, rec.key) if not rec.native_ids else element_id(self.ns, f'{rec.key}/{slot}')
        el = {'id': eid, 'type': type_, 'producer': {'operationId': op_id, 'slot': slot},
              'displayName': rec.display}
        if self.ctx.origin_of is not None:
            origin = self.ctx.origin_of(name)
            if isinstance(origin, dict):
                el['origin'] = origin
        self.doc['elements'][eid] = el
        if rec.display:
            self.doc['bindings']['legacyNames'][eid] = rec.display
        rec.native_ids.append(eid)
        rec.type = rec.type or type_
        self.element_of[name] = eid
        app = self.ctx.appearance.get(name)
        if app:
            self.doc['appearance'][eid] = copy.deepcopy(app)
        return eid

    # -- free objects -------------------------------------------------------
    def free_point(self, name, rec, xy):
        op_id = operation_id(self.ns, rec.key)
        self.doc['operations'][op_id] = {'id': op_id, 'op': 'point.free', 'args': {},
                                         'outputs': [{'slot': 'point', 'elementId': None}]}
        eid = self.add_element(name, rec, op_id, 'point', 'point')
        self.doc['operations'][op_id]['outputs'][0]['elementId'] = eid
        self.doc['inputs'][eid] = {'kind': 'point', 'value': [float(xy[0]), float(xy[1])]}
        rec.op_id = op_id
        rec.free = True

    def free_number(self, name, rec, value, *, angle=False, slider=None):
        op_id = operation_id(self.ns, rec.key)
        args = {}
        for k in ('min', 'max', 'step'):
            v = (slider or {}).get(k)
            if v is not None and math.isfinite(float(v)):
                args[k] = _num(v)
        op = 'number.angle' if angle else 'number.free'
        self.doc['operations'][op_id] = {'id': op_id, 'op': op, 'args': args,
                                         'outputs': [{'slot': 'number', 'elementId': None}]}
        eid = self.add_element(name, rec, op_id, 'number', 'number')
        self.doc['operations'][op_id]['outputs'][0]['elementId'] = eid
        self.doc['inputs'][eid] = {'kind': 'angle' if angle else 'number', 'value': float(value)}
        rec.op_id = op_id
        rec.free = True

    def free_object(self, name):
        from ...geo.lib_vars import AngleSize, Boolean, Var
        obj = self.constr.objectByName(name)
        rec = self.record(name, key=self.key_for(name), command=None, inputs=[])
        forced = self.ctx.forced.get(name)
        if forced:
            rec.status, rec.reason, rec.detail = 'untranslated', forced[0], forced[1]
            return
        data = obj.data
        if isinstance(obj, Var):
            if isinstance(data, Boolean):
                rec.status, rec.reason = 'untranslated', 'ui_object'
                return
            info = self.ctx.free_numbers.get(name, {})
            value = _literal(data)
            if value is None or not math.isfinite(value):
                rec.status, rec.reason = 'untranslated', 'formula_unsupported'
                return
            angle = isinstance(data, AngleSize) or bool(info.get('angle'))
            self.free_number(name, rec, info.get('value', value), angle=angle, slider=info)
            return
        if isinstance(data, self._Point) or name in self.ctx.free_points:
            xy = self.ctx.free_points.get(name)
            if xy is None:
                xy = [float(data.coords[0]), float(data.coords[1])]
            if not all(math.isfinite(float(v)) for v in xy):
                rec.status, rec.reason = 'untranslated', 'no_registry_op'
                rec.detail = 'точка без конечных координат'
                return
            self.free_point(name, rec, xy)
            return
        kind = type(data).__name__ if data is not None else None
        rec.status = 'untranslated'
        rec.reason = 'formula_unsupported' if kind in ('Line', 'Conic', 'Function', 'ImplicitCurve') else \
            'no_registry_op'
        rec.detail = f'свободный объект {kind}' if kind else None

    # -- commands -----------------------------------------------------------
    def arg_for(self, inp, slot, params):
        """The argument of classic input ``inp`` for ``slot`` (or raise)."""
        if isinstance(inp, str) and inp in AXES:
            raise _Untranslated('no_registry_op', 'оси координат не входят в документ')
        if self.is_object(inp):
            eid = self.element_of.get(inp)
            if eid is not None:
                if slot in params:
                    raise _Untranslated('unsupported_signature', f'параметр {slot} задан объектом')
                return _ref(eid)
            rec = self.records.get(inp)
            if rec is not None and rec.status in ('untranslated', 'closure'):
                raise _Untranslated('depends_on_unsupported', deps=[inp])
            value = _literal(self.data_of(inp))
            if value is not None and KeyMaker.is_phantom(inp):
                return _num(value)
            raise _Untranslated('depends_on_unsupported', deps=[inp])
        value = _literal(self.constr.dataByStr(inp) if isinstance(inp, str) else inp)
        if value is None or not math.isfinite(value):
            raise _Untranslated('formula_unsupported', f'аргумент {inp!r}')
        return _num(value)

    def segment_ends(self, inp):
        eid = self.element_of.get(inp) if isinstance(inp, str) else None
        if eid is None:
            if self.is_object(inp):
                raise _Untranslated('depends_on_unsupported', deps=[inp])
            raise _Untranslated('unsupported_signature', 'нужен отрезок')
        el = self.doc['elements'][eid]
        op = self.doc['operations'][el['producer']['operationId']]
        slot = el['producer']['slot']
        if op['op'] == 'segment.by_points':
            return op['args']['a'], op['args']['b']
        if op['op'] == 'polygon.by_points' and slot.startswith('side.'):
            items = op['args']['vertices']['items']
            k = int(slot.split('.')[1])
            return items[k - 1], items[k % len(items)]
        raise _Untranslated('unsupported_signature', 'концы отрезка не являются входами документа')

    def command(self, cmd):
        outs = [str(getattr(o, 'name', o)) for o in cmd.outputs if str(getattr(o, 'name', o))]
        if not outs:
            return
        inputs = list(cmd.inputs)
        sig = self.signature(cmd, inputs)
        in_names = [i for i in inputs if isinstance(i, str) and self.is_object(i)]
        input_keys = []
        for i in inputs:
            if isinstance(i, str) and i in self.records:
                input_keys.append(self.records[i].key)
            else:
                input_keys.append(str(getattr(i, 'name', i)))
        recs = [self.record(o, key=self.key_for(o, sig, input_keys, n), command=cmd.name, signature=sig,
                            inputs=in_names) for n, o in enumerate(outs)]
        try:
            forced = [o for o in outs if o in self.ctx.forced]
            if forced and len(forced) == len(outs):
                raise _Untranslated(*self.ctx.forced[forced[0]])
            self.build(cmd, sig, inputs, outs, recs)
            # a forced output (a script on one side of a polygon, …) drops alone:
            # the operation keeps its other outputs, its dependents make the closure
            for o, rec in zip(outs, recs):
                if o in self.ctx.forced:
                    rec.status, (rec.reason, rec.detail) = 'untranslated', self.ctx.forced[o]
        except _Untranslated as exc:
            for rec in recs:
                if rec.native_ids:
                    continue
                if exc.reason == 'depends_on_unsupported':
                    rec.status, rec.reason = 'closure', 'depends_on_unsupported'
                else:
                    rec.status, rec.reason, rec.detail = 'untranslated', exc.reason, exc.detail

    def build(self, cmd, sig, inputs, outs, recs):
        row = self.table.lookup(sig)
        # a dependency that did not translate makes the closure first
        for name in (i for i in inputs if isinstance(i, str) and self.is_object(i)):
            rec = self.records.get(name)
            if rec is not None and rec.status in ('untranslated', 'closure'):
                raise _Untranslated('depends_on_unsupported', deps=[name])
        if row is None:
            same = [k for k in self.table.commands if k.rpartition('_')[0] == sig.rpartition('_')[0]
                    and 'op' in self.table.commands[k]]
            raise _Untranslated('unsupported_signature' if same else 'no_registry_op',
                                f'{cmd.name}: такие аргументы не переносятся ({sig})' if same
                                else f'команда {cmd.name} не переносится')
        if 'unmapped' in row:
            raise _Untranslated(row['unmapped'], NOTE_DETAILS.get(row.get('note')))
        if 'free' in row and row['free'] in ('number', 'angle'):
            # a DSL AngleSize(0.7): a free angle when its argument is a literal
            arg = inputs[0] if inputs else None
            named = isinstance(arg, str) and self.is_object(arg) and getattr(self.records.get(arg), 'status',
                                                                              None) != 'constant'
            value = _literal(self.constr.dataByStr(arg) if isinstance(arg, str) else arg)
            if named or value is None or not math.isfinite(value):
                raise _Untranslated('formula_unsupported', 'значение задано выражением')
            self.free_number(outs[0], recs[0], value, angle=row['free'] == 'angle')
            return
        if 'free' in row:
            data = self.data_of(outs[0])
            xy = self.ctx.free_points.get(outs[0])
            if xy is None and isinstance(data, self._Point):
                xy = [float(data.coords[0]), float(data.coords[1])]
            if xy is None:
                raise _Untranslated('no_registry_op', 'точка без координат')
            self.free_point(outs[0], recs[0], xy)
            return
        op_name = row['op']
        record = self.reg.ops[op_name]
        params = {p['slot'] for p in record.get('params', ())}
        args = {}
        spec = row['args']
        if isinstance(spec, dict):
            args[spec['variadic']] = {'kind': 'list', 'items': [self.arg_for(i, spec['variadic'], params)
                                                                for i in inputs]}
        else:
            if len(inputs) < sum(1 for s in spec if s is not None):
                raise _Untranslated('unsupported_signature', 'не хватает аргументов')
            for i, slot in enumerate(spec):
                if slot is None:
                    continue
                if isinstance(slot, dict):
                    a, b = self.segment_ends(inputs[i])
                    args[slot['ends'][0]], args[slot['ends'][1]] = a, b
                else:
                    args[slot] = self.arg_for(inputs[i], slot, params)
        # outputs → slots
        out_spec = row['outputs']
        index = None
        if row.get('index') is not None:
            raw = inputs[row['index']['input']]
            value = _literal(self.constr.dataByStr(raw) if isinstance(raw, str) else raw)
            if value is None or value != int(value) or value < row['index'].get('base', 1):
                raise _Untranslated('unsupported_signature', 'номер выхода не задан числом')
            index = int(value) - row['index'].get('base', 1)
        if isinstance(out_spec, list):
            slots = list(out_spec)
        elif 'byValue' in out_spec:
            cands = out_spec['byValue']
            slots = [cands[index]] if index is not None and index < len(cands) else list(cands)
        elif out_spec.get('pattern') == 'polygon_sides':
            slots = ['polygon'] + [f'side.{k}' for k in range(1, len(inputs) + 1)]
        else:      # regular
            n = int(args['n']['value']) if args.get('n', {}).get('kind') == 'number' else 0
            if n < 3:
                raise _Untranslated('unsupported_signature', 'число сторон')
            slots = ['polygon'] + [f'side.{k}' for k in range(1, n + 1)] + [f'vertex.{k}' for k in range(3, n + 1)]
        op_id = operation_id(self.ns, recs[0].key)
        op = {'id': op_id, 'op': op_name, 'args': args, 'outputs': []}
        self.doc['operations'][op_id] = op
        graph = self.doc
        bound = []
        for n, (name, rec) in enumerate(zip(outs, recs)):
            slot = slots[n] if n < len(slots) else None
            if slot is None:
                rec.status, rec.reason, rec.detail = 'untranslated', 'unsupported_signature', 'лишний выход команды'
                continue
            type_ = self.reg.output_type(record, slot, args, graph)
            if type_ is None:
                rec.status, rec.reason, rec.detail = 'untranslated', 'unsupported_signature', f'нет слота {slot}'
                continue
            eid = self.add_element(name, rec, op_id, slot, type_)
            op['outputs'].append({'slot': slot, 'elementId': eid})
            rec.op_id = op_id
            bound.append((name, slot))
        if not op['outputs']:
            del self.doc['operations'][op_id]
            return
        if isinstance(out_spec, dict) and 'byValue' in out_spec:
            self.by_value[op_id] = {'slots': list(out_spec['byValue']), 'outputs': bound}
        if row.get('input') == 'pathParameter':
            eid = op['outputs'][0]['elementId']
            self.doc['inputs'][eid] = {'kind': 'pathParameter', 'value': 0.0}
            self.on_path.append((outs[0], eid))


def _drop_operation(builder: _Builder, op_id: str, reason: str, detail: str | None):
    op = builder.doc['operations'].pop(op_id, None)
    if op is None:
        return
    for out in op['outputs']:
        eid = out['elementId']
        builder.doc['elements'].pop(eid, None)
        builder.doc['inputs'].pop(eid, None)
        builder.doc['appearance'].pop(eid, None)
        builder.doc['bindings']['legacyNames'].pop(eid, None)
    builder.by_value.pop(op_id, None)
    for rec in builder.records.values():
        if rec.op_id == op_id:
            for eid in rec.native_ids:
                builder.element_of.pop(rec.name, None)
            rec.native_ids = []
            rec.op_id = None
            rec.status, rec.reason, rec.detail = 'untranslated', reason, detail


def _close(builder: _Builder):
    """Drop every operation that refers to a missing element (repeat to the fixpoint)."""
    from ..document import iter_refs
    changed = True
    while changed:
        changed = False
        elements = builder.doc['elements']
        for op_id, op in list(builder.doc['operations'].items()):
            missing = [r for arg in op['args'].values() if isinstance(arg, dict) for r in iter_refs(arg)
                       if r not in elements]
            if missing:
                _drop_operation(builder, op_id, 'depends_on_unsupported', None)
                for rec in builder.records.values():
                    if rec.status == 'untranslated' and rec.reason == 'depends_on_unsupported':
                        rec.status = 'closure'
                changed = True


def _validate(builder: _Builder):
    from ..document import load, validate
    for _ in range(64):
        _close(builder)
        doc = load(builder.doc, strict=False)
        issues = [i for i in validate(doc) if getattr(i, 'severity', 'error') == 'error']
        if not issues:
            return doc
        dropped = False
        for issue in issues:
            op_id = issue.operationId
            if op_id is None and issue.elementId is not None:
                el = builder.doc['elements'].get(issue.elementId)
                op_id = el['producer']['operationId'] if el else None
            if op_id is None and issue.path.startswith('/operations/'):
                op_id = issue.path.split('/')[2]
            if op_id in builder.doc['operations']:
                _drop_operation(builder, op_id, 'unsupported_signature', f'{issue.code}: {issue.message}'[:200])
                dropped = True
        if not dropped:
            raise RuntimeError('validate: ' + '; '.join(f'{i.code} {i.path}' for i in issues[:3]))
    raise RuntimeError('validate: no fixpoint')


def _expected(builder: _Builder, rec: Record):
    exp = builder.ctx.expected.get(rec.name)
    if exp is not None:
        return exp
    if rec.type is None:
        return None
    return classic_report_value(rec.type, builder.data_of(rec.name))


def _resolve_by_value(builder: _Builder, doc, scale: float):
    """Bind each output of a ``byValue`` operation to the slot whose value matches it."""
    from ..kernel.evaluate import evaluate
    if not builder.by_value:
        return {}
    probe = copy.deepcopy(builder.doc)
    probe_ids = {}
    for op_id, info in builder.by_value.items():
        op = probe['operations'][op_id]
        record = builder.reg.ops[op['op']]
        have = {o['slot'] for o in op['outputs']}
        for n, slot in enumerate(info['slots']):
            if slot in have:
                probe_ids[(op_id, slot)] = next(o['elementId'] for o in op['outputs'] if o['slot'] == slot)
                continue
            eid = f'probe{len(probe_ids)}x{n}'
            type_ = builder.reg.output_type(record, slot, op['args'], probe)
            probe['elements'][eid] = {'id': eid, 'type': type_, 'producer': {'operationId': op_id, 'slot': slot},
                                      'displayName': ''}
            op['outputs'].append({'slot': slot, 'elementId': eid})
            probe_ids[(op_id, slot)] = eid
    ev = evaluate(probe)
    ambiguous = {}
    for op_id, info in builder.by_value.items():
        values = {}
        for slot in info['slots']:
            eid = probe_ids[(op_id, slot)]
            st = ev.elements.get(eid, {})
            type_ = probe['elements'][eid]['type']
            values[slot] = native_report_value(type_, st.get('value')) if st.get('state') == 'defined' else None
        used = set()
        new_slots = {}
        for name, provisional in info['outputs']:
            rec = builder.records[name]
            exp = _expected(builder, rec)
            if exp is None:
                new_slots[name] = provisional
                continue
            matches = [s for s in info['slots'] if values[s] is not None
                       and compare(exp, values[s], scale)[0] == 'passed']
            free = [s for s in matches if s not in used]
            if provisional in free:
                choice = provisional
            elif len(free) == 1:
                choice = free[0]
            elif len(free) == 2 and compare(values[free[0]], values[free[1]], scale)[0] == 'passed':
                choice = free[0]     # a tangency: both slots hold the point
            else:
                choice = provisional
                if exp.get('value') is not None or matches:
                    ambiguous[name] = 'slot_ambiguous' if len(free) != 1 and matches else None
            used.add(choice)
            new_slots[name] = choice
        op = builder.doc['operations'][op_id]
        for out in op['outputs']:
            name = next((n for n, _s in info['outputs'] if builder.element_of.get(n) == out['elementId']), None)
            if name is not None and new_slots.get(name):
                out['slot'] = new_slots[name]
                builder.doc['elements'][out['elementId']]['producer']['slot'] = new_slots[name]
    return {k: v for k, v in ambiguous.items() if v}


def _project_on_path(builder: _Builder):
    from ..kernel.evaluate import evaluate
    if not builder.on_path:
        return
    from .. import project
    for name, eid in builder.on_path:
        if eid not in builder.doc['elements']:
            continue
        xy = builder.ctx.free_points.get(name)
        if xy is None:
            data = builder.data_of(name)
            if isinstance(data, builder._Point):
                xy = [float(data.coords[0]), float(data.coords[1])]
        try:
            t = project(builder.doc, eid, xy) if xy is not None else None
        except ValueError:
            t = None
        if t is None or not math.isfinite(t):
            builder.warnings.append({'code': 'path_parameter_default', 'name': name})
            continue
        builder.doc['inputs'][eid] = {'kind': 'pathParameter', 'value': float(t)}
    evaluate      # noqa: B018 — imported for symmetry with the other passes


def translate(constr, ctx: Context) -> Translation:
    """Translate ``constr`` with what ``ctx`` knows; see the module doc."""
    from ...geo.lib_vars import Var
    from ..kernel.evaluate import evaluate
    builder = _Builder(constr, ctx)
    produced = set()
    for cmd in constr.commands:
        for o in cmd.outputs:
            produced.add(str(getattr(o, 'name', o)))
    free = [e.name for e in constr.elements if e.name not in AXES and e.name not in produced]
    free += [v.name for v in constr.vars if v.name not in produced]
    for name in sorted(free, key=lambda n: ctx.order.get(n, 10 ** 6)):
        obj = constr.objectByName(name)
        if isinstance(obj, Var) and KeyMaker.is_phantom(name):
            builder.record(name, key=builder.key_for(name, 'value', (str(_literal(obj.data)),), 0),
                           status='untranslated', reason='formula_unsupported')
            builder.records[name].status = 'constant'
            continue
        builder.free_object(name)
    for cmd in constr.commands:
        builder.command(cmd)
    doc = _validate(builder)
    _project_on_path(builder)
    doc = _validate(builder)
    ev0 = evaluate(doc)
    scale = float(ev0.tolerances.scale)
    ambiguous = _resolve_by_value(builder, doc, scale)
    doc = _validate(builder)
    ev = evaluate(doc)
    for rec in builder.records.values():
        if rec.status != 'translated' or not rec.native_ids:
            continue
        eid = rec.native_ids[0]
        st = ev.elements.get(eid, {})
        rec.native_value = native_report_value(rec.type, st.get('value')) if st.get('state') == 'defined' else None
        if rec.free:
            rec.expected = builder.ctx.expected.get(rec.name) or rec.native_value
            status, delta = compare(rec.expected, rec.native_value, scale)
            rec.value_check, rec.delta = ('passed', 0.0) if status == 'not_checked' else (status, delta)
            continue
        rec.expected = _expected(builder, rec)
        rec.value_check, rec.delta = compare(rec.expected, rec.native_value, scale)
        if rec.name in ambiguous:
            rec.reason = 'slot_ambiguous'
    # assign seq by source order
    order = sorted(builder.records.values(), key=lambda r: (r.order, r.name))
    seq = 0
    seen = set()
    for rec in order:
        if rec.op_id and rec.op_id in builder.doc['operations'] and rec.op_id not in seen:
            seen.add(rec.op_id)
            seq += 1
            builder.doc['operations'][rec.op_id]['seq'] = seq
    if not builder.doc['bindings']['legacyNames']:
        builder.doc['bindings'] = {}
    names = [r.name for r in order if r.status != 'constant']
    return Translation(document=builder.doc, records=builder.records, names=names, warnings=builder.warnings,
                       scale=scale)


TOL = TOL_IMPORT
