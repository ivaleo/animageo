"""Source conic-element plans, typed operands and owned circle adapters."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from types import SimpleNamespace

from .ggb_expr import ExprError, parse_number, parse_typed
from .ggb_function_analysis import _arguments
from .ggb_inline import HELPER_APPEARANCE
from .keys import element_id, operation_id

COMMANDS = {
    'Center': 'center', 'Focus': 'foci', 'Vertex': 'vertices', 'Axes': 'axes',
    'MajorAxis': 'focal', 'FirstAxis': 'focal', 'MinorAxis': 'conjugate', 'SecondAxis': 'conjugate',
    'Directrix': 'directrices', 'Asymptote': 'asymptotes', 'Polar': 'polar',
    'Diameter': 'diameter', 'ConjugateDiameter': 'diameter',
}
DEFERRED = {'Eccentricity', 'FirstAxisLength', 'SecondAxisLength', 'SemiMajorAxisLength',
            'SemiMinorAxisLength', 'Excentricity', 'LinearEccentricity', 'Parameter'}
_FIXED = {'center': ['center'], 'foci': ['first', 'second'],
          'vertices': ['first', 'second', 'third', 'fourth'], 'axes': ['focal', 'conjugate'],
          'focal': ['focal'], 'conjugate': ['conjugate'], 'polar': ['line'], 'diameter': ['line']}
_AXES = ('xAxis', 'yAxis')
_RECOVERABLE = {'parse_error', 'no_registry_op', 'unsupported_signature'}


@dataclass
class Operand:
    name: str | None = None
    kind: str = ''
    ast: dict | None = None
    refs: list = field(default_factory=list)


@dataclass
class ElementPlan:
    command: str
    mode: str
    outputs: dict
    signature: str = ''
    operands: dict = field(default_factory=dict)
    capacity: int = 2
    error: tuple | None = None

    def dependencies(self):
        return list(dict.fromkeys(n for operand in self.operands.values()
                                 for n in ([operand.name] if operand.name else operand.refs)))


def snapshot_commands(root):
    nodes = [copy.deepcopy(n) for n in root.findall('./construction/command')
             if n.attrib.get('name') in COMMANDS or n.attrib.get('name') in DEFERRED]
    for node in nodes:
        out = node.find('output')
        if out is not None:
            _output_ordinals(out)
    return nodes


def _output_ordinals(out):
    ordinals = {}
    for attr in out.attrib:
        if not (attr.startswith('a') and attr[1:].isascii() and attr[1:].isdigit()):
            continue
        digits = attr[1:].lstrip('0') or '0'
        if len(digits) > 2:
            from .ggb import ImportRefused
            raise ImportRefused('import_too_many_objects', 'conic output capacity exceeds 100')
        ordinals[attr] = int(digits)
    return ordinals


def _operand(text, kind, kinds, norm):
    if text in kinds:
        allowed = ('conic', 'circle') if kind == 'conic' else ('line', 'vector') if kind == 'direction' else ('point',)
        if kinds[text] not in allowed:
            raise ExprError('unsupported_signature', f'{kind} input is required')
        return Operand(norm.get(text, text), kinds[text])
    if kind == 'conic':
        parts = text.split('=')
        if len(parts) != 2 or not all(p.strip() for p in parts):
            raise ExprError('unsupported_signature', 'a conic reference or quadratic equation is required')
        ast, refs = parse_number(f'({parts[0]})-({parts[1]})', kinds, variables=('x', 'y'))
        return Operand(kind='conic', ast=ast, refs=[norm[n] for n in refs])
    if kind == 'direction':
        from .ggb_typed import _VECTOR
        wrapper = _VECTOR.fullmatch(text)
        if wrapper:
            text = wrapper.group(1) if wrapper.group(1) is not None else wrapper.group(2)
    try:
        ast, refs = parse_typed(text, kinds, result='vec')
    except ExprError as vector_error:
        try:
            parse_typed(text, kinds, result='num')
        except ExprError:
            raise vector_error
        raise ExprError('unsupported_signature', f'{kind} input cannot be a scalar') from None
    return Operand(kind='vector' if kind == 'direction' else 'point', ast=ast, refs=[norm[n] for n in refs])


def read_elements(nodes, infos, norm, ctx, constr, signature_of):
    kinds = dict.fromkeys(_AXES, 'line') | {i['label']: i['type'] for i in infos}
    by_label = {i['label']: i for i in infos}
    classic = {str(getattr(o, 'name', o)): cmd for cmd in constr.commands for o in cmd.outputs}
    for node in nodes:
        name = node.attrib['name']
        inp, out = node.find('input'), node.find('output')
        first = inp.attrib.get('a0', '').strip() if inp is not None else ''
        if name == 'Vertex' and kinds.get(first) in ('polygon', 'segment', 'inequality'):
            continue
        if out is None:
            continue
        ordinals = _output_ordinals(out)
        outputs = {norm[label]: ordinals[a] for a, label in sorted(
            out.attrib.items(), key=lambda pair: ordinals.get(pair[0], 0))
            if a in ordinals and label in norm and by_label[label].get('command') == name
            and norm[label] not in ctx.conic_elements}
        if not outputs:
            continue
        mode = COMMANDS.get(name, '')
        plan = ElementPlan(name, mode, outputs, capacity=max(2, max(ordinals.values(), default=0)+1))
        if plan.capacity > 100:
            from .ggb import ImportRefused
            raise ImportRefused('import_too_many_objects', 'conic output capacity exceeds 100')
        try:
            args = [s.strip() for s in _arguments(inp)]
            plan.signature = f'{name}({", ".join(args)})'
            if name in DEFERRED:
                raise ExprError('unsupported_signature', 'scalar conic characteristics are not supported')
            if len(ordinals) != len(out.attrib) or len(set(outputs.values())) != len(outputs):
                raise ExprError('unsupported_signature', 'invalid conic output ordinals')
            if len(args) != (2 if mode in ('polar', 'diameter') else 1):
                raise ExprError('unsupported_signature', 'unsupported conic element signature')
            plan.operands['conic'] = _operand(args[-1], 'conic', kinds, norm)
            if mode in ('polar', 'diameter'):
                slot = 'point' if mode == 'polar' else 'direction'
                plan.operands[slot] = _operand(args[0], slot, kinds, norm)
            kind = 'point' if mode in ('center', 'foci', 'vertices') else 'line'
            if any(kinds[ctx.display[n]] != kind for n in outputs):
                raise ExprError('unsupported_signature', f'{name} requires {kind} outputs')
            slots = _FIXED.get(mode)
            if slots and (len(outputs) > len(slots) or any(i >= len(slots) for i in outputs.values())):
                raise ExprError('unsupported_signature', 'output ordinal exceeds the fixed conic slots')
            # Retain the established dispatch signature for old Center imports.
            cmd = classic.get(next(iter(outputs)))
            if mode == 'center' and cmd is not None:
                plan.signature = signature_of(cmd)
                if '?' in plan.signature:
                    plan.signature = 'center_K' if kinds.get(args[0]) == 'conic' else 'center_c'
        except ExprError as exc:
            plan.error = (exc.reason, exc.detail)
        dependencies = plan.dependencies()
        if inp is not None:
            dependencies.extend(norm[t.strip()] for t in inp.attrib.values() if t.strip() in norm)
        for n in outputs:
            ctx.conic_elements[n] = plan
            forced = ctx.forced.get(n, (None,))[0]
            if forced in _RECOVERABLE or forced == 'list' and plan.error and plan.error[0] == 'unsupported_signature':
                ctx.forced.pop(n)
        ctx.source_commands.append(SimpleNamespace(name=name, inputs=list(dict.fromkeys(dependencies)),
                                                   outputs=list(outputs), source_signature=plan.signature))


def _helper(builder, owner, key, operation, args, kind, slot):
    oid, eid = operation_id(builder.ns, key), element_id(builder.ns, key)
    builder.doc['operations'][oid] = {'id': oid, 'op': operation, 'args': args,
                                      'outputs': [{'slot': slot, 'elementId': eid}]}
    builder.doc['elements'][eid] = {'id': eid, 'type': kind, 'displayName': '',
                                   'producer': {'operationId': oid, 'slot': slot},
                                   'origin': {'kind': 'auto', 'source': owner}}
    builder.doc['appearance'][eid] = copy.deepcopy(HELPER_APPEARANCE)
    return {'kind': 'ref', 'elementId': eid}


def _emit(builder, mode, resolved, outs, recs, ordinals, capacity):
    from .construction import _Untranslated
    owner = operation_id(builder.ns, recs[0].key)
    curve = resolved['conic']
    kind = builder.doc['elements'][curve['elementId']]['type']
    if kind not in ('circle', 'conic'):
        raise _Untranslated('unsupported_signature', 'a native circle or conic is required')
    if mode in ('foci', 'vertices', 'axes', 'focal', 'conjugate') and kind == 'circle':
        curve = _helper(builder, owner, recs[0].key+'/inline/conic', 'conic.from_circle',
                        {'circle': curve}, 'conic', 'conic')
    operation = {'center': 'point.center' if kind == 'circle' else 'conic.center',
                 'focal': 'conic.axes', 'conjugate': 'conic.axes',
                 'polar': 'line.polar_conic', 'diameter': 'line.conjugate_diameter'}.get(mode, 'conic.'+mode)
    args = {'of' if operation == 'point.center' else 'conic': curve}
    args.update({s: a for s, a in resolved.items() if s != 'conic'})
    repeated = mode in ('directrices', 'asymptotes')
    slots = ([f'{"directrix" if mode == "directrices" else "asymptote"}.{i+1}' for i in range(capacity)]
             if repeated else _FIXED[mode])
    if repeated:
        args['count'] = {'kind': 'number', 'value': capacity}
    op = {'id': owner, 'op': operation, 'args': args, 'outputs': []}
    builder.doc['operations'][owner] = op
    output_kind = 'point' if mode in ('center', 'foci', 'vertices') else 'line'
    bound = []
    for n, rec in zip(outs, recs):
        slot = slots[ordinals[n]]
        eid = builder.add_element(n, rec, owner, slot, output_kind)
        op['outputs'].append({'slot': slot, 'elementId': eid})
        rec.op_id = owner
        bound.append((n, slot))
    if len(slots) > 1:
        builder.by_value[owner] = {'conic_elements': True, 'outputs': bound, 'slots': slots,
                                   'type': output_kind, 'ordinals': ordinals, 'repeated': repeated}


def build_elements(builder, plan, outs, recs):
    from .construction import _Untranslated
    from ..expr.validate import problems
    if plan.error:
        raise _Untranslated(*plan.error)
    resolved, pending = {}, {}
    for slot, operand in plan.operands.items():
        if operand.name:
            if operand.name in _AXES:
                pending[slot] = operand
            else:
                eid = builder.element_of.get(operand.name)
                if eid is None:
                    raise _Untranslated('depends_on_unsupported', deps=[operand.name])
                resolved[slot] = {'kind': 'ref', 'elementId': eid}
            continue
        refs = []
        for n in operand.refs:
            eid = builder.element_of.get(n)
            if eid is None:
                raise _Untranslated('depends_on_unsupported', deps=[n])
            refs.append({'kind': 'ref', 'elementId': eid})
        types = [builder.doc['elements'][r['elementId']]['type'] for r in refs]
        issues = problems(operand.ast, len(refs), vars=('x', 'y')) if operand.kind == 'conic' else problems(
            operand.ast, len(refs), operands=types, result='vec')
        if issues or operand.kind == 'conic' and any(t != 'number' for t in types):
            raise _Untranslated('formula_unsupported', 'inline operand exceeds its native expression language')
        pending[slot] = operand, refs
    owner = operation_id(builder.ns, recs[0].key)
    for slot, value in pending.items():
        if isinstance(value, Operand):
            from .ggb_conic import axis_ref
            resolved[slot] = axis_ref(builder, value.name)
            continue
        operand, refs = value
        args = {'expr': {'kind': 'expr', 'ast': operand.ast}, 'refs': {'kind': 'list', 'items': refs}}
        resolved[slot] = _helper(builder, owner, recs[0].key+'/inline/'+slot,
            'conic.equation' if operand.kind == 'conic' else operand.kind+'.expression', args, operand.kind, operand.kind)
    _emit(builder, plan.mode, resolved, outs, recs, plan.outputs, plan.capacity)


def build_classic_elements(builder, cmd, sig, inputs, outs, recs):
    """Existing factories share subtype routing and slot matching with XML."""
    from .construction import _Untranslated
    mode = COMMANDS.get(cmd.name)
    if mode is None or mode in ('asymptotes', 'diameter'):
        return False
    if cmd.name == 'Vertex' and sig not in ('vertex_K', 'vertex_c'):
        return False
    if mode == 'polar' and sig not in ('polar_pK', 'polar_Kp', 'polar_pc'):
        raise _Untranslated('unsupported_signature', 'point poles are not supported; Polar requires a point')
    if len(inputs) != (2 if mode == 'polar' else 1):
        return False
    slots = _FIXED.get(mode)
    if slots is not None and len(outs) > len(slots):
        raise _Untranslated('unsupported_signature', 'too many fixed conic outputs')
    curve_index = 0 if sig == 'polar_Kp' else len(inputs)-1
    resolved = {'conic': builder.arg_for(inputs[curve_index], 'conic', set())}
    if mode == 'polar':
        resolved['point'] = builder.arg_for(inputs[1-curve_index], 'point', set())
    ordinals = {n: builder.ctx.output_positions.get(n, i) for i, n in enumerate(outs)}
    _emit(builder, mode, resolved, outs, recs, ordinals, max(2, max(ordinals.values())+1))
    return True
