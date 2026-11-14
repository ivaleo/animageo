"""Live tangency lowerings and grouped saved-line matching.

XML commands are captured before classic parsing. Saved coefficients only
identify output slots and check values; they never define a free tangent.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from types import SimpleNamespace

from .ggb_expr import ExprError, parse_typed
from .ggb_function import FunctionSpec, source_ref_names
from .ggb_function_analysis import NumberSource, _arguments, _function
from .ggb_inline import HELPER_APPEARANCE
from .keys import element_id, operation_id
from .values import circle_from_matrix, compare, native_report_value

_RECOVERABLE = {'parse_error', 'unsupported_signature', 'no_registry_op'}
_REPEATED = {'line.tangents_from_point_conic', 'line.tangents_parallel_conic'}
_OPERATIONS = _REPEATED | {'line.tangent_function_at', 'line.slope'}
_AXES = ('xAxis', 'yAxis')


@dataclass
class TangencyPlan:
    command: str
    outputs: dict                         # normalized label -> original aN
    signature: str = ''
    operation: str = ''
    objects: dict = field(default_factory=dict)
    function: str | FunctionSpec | None = None
    number: NumberSource | None = None
    capacity: int = 1
    error: tuple | None = None

    def dependencies(self, ctx):
        names = list(self.objects.values())
        if isinstance(self.function, str):
            names.append(self.function)
        elif self.function is not None:
            names.extend(source_ref_names(self.function, ctx))
        if self.number is not None:
            names.extend(self.number.refs)
        return list(dict.fromkeys(names))


def snapshot_commands(root):
    """Keep original arguments and sparse ordinals before classic can fail."""
    return [copy.deepcopy(node) for node in root.findall('./construction/command')
            if node.attrib.get('name') in ('Tangent', 'Slope')]


def read_tangency(nodes, infos, norm, ctx):
    """Configure source plans independently of classic dispatch and values."""
    kinds = dict.fromkeys(_AXES, 'line') | {i['label']: i['type'] for i in infos}
    by_label = {i['label']: i for i in infos}
    for node in nodes:
        command = node.attrib['name']
        inp, out = node.find('input'), node.find('output')
        if out is None:
            continue
        texts = [inp.attrib.get(f'a{i}', '').strip() for i in range(2)] if inp is not None else []
        if command == 'Tangent' and len(texts) == 2 and kinds.get(texts[0]) != 'line':
            curve = by_label.get(texts[1], {})
            if curve.get('type') == 'conic' and curve.get('matrix') is not None and None not in curve['matrix'] \
                    and circle_from_matrix(curve['matrix']):
                # Keep all earlier circle signatures, including inline points,
                # indexed outputs and Circle+Circle, on their existing path.
                continue
        ordinals = {a: int(a[1:]) for a in out.attrib if a.startswith('a') and a[1:].isdigit()}
        outputs = {norm[label]: ordinals[a] for a, label in sorted(
            out.attrib.items(), key=lambda item: ordinals.get(item[0], 0))
            if a in ordinals and label in norm and by_label[label].get('command') == command
            and norm[label] not in ctx.tangency}
        if not outputs:
            continue
        capacity = max(ordinals.values(), default=0) + 1
        if capacity > 100:
            from .ggb import ImportRefused
            raise ImportRefused('import_too_many_objects', 'tangency output capacity exceeds 100')
        plan = TangencyPlan(command, outputs, capacity=capacity)
        try:
            args = [s.strip() for s in _arguments(inp)]
            plan.signature = f'{command}({", ".join(args)})'
            if len(ordinals) != len(out.attrib):
                raise ExprError('unsupported_signature', 'invalid output ordinal')
            if command == 'Slope' and len(args) == 1 and kinds.get(args[0]) == 'line':
                plan.operation = 'line.slope'
                plan.objects = {'line': norm.get(args[0], args[0])}
            elif command == 'Tangent' and len(args) == 2:
                a, b = args
                if kinds.get(b) == 'function' or b not in kinds:
                    plan.operation = 'line.tangent_function_at'
                    plan.function = _function(b, kinds, norm, ctx)
                    text = f'x({a})' if kinds.get(a) == 'point' else a
                    ast, refs = parse_typed(text, kinds, result='num')
                    if any(kinds[r] not in ('numeric', 'angle', 'point') for r in refs):
                        raise ExprError('unsupported_signature', 'a numeric abscissa is required')
                    plan.number = NumberSource(ast, [norm[r] for r in refs])
                elif kinds.get(b) == 'conic' and kinds.get(a) in ('point', 'line'):
                    parallel = kinds[a] == 'line'
                    plan.operation = 'line.tangents_parallel_conic' if parallel else 'line.tangents_from_point_conic'
                    plan.objects = {'base' if parallel else 'point': norm.get(a, a), 'conic': norm[b]}
            if not plan.operation:
                raise ExprError('unsupported_signature', f'unsupported {command} signature')
            repeated = plan.operation in _REPEATED
            expected_type = 'numeric' if plan.operation == 'line.slope' else 'line'
            if any(kinds[ctx.display[n]] != expected_type for n in outputs):
                raise ExprError('unsupported_signature', 'unexpected tangency output type')
            if not repeated and (len(outputs) != 1 or next(iter(outputs.values())) != 0):
                raise ExprError('unsupported_signature', 'the command has one output')
        except ExprError as exc:
            plan.error = (exc.reason, exc.detail)
        # Preserve closure even for a refused signature.
        dependencies = plan.dependencies(ctx)
        dependencies.extend(norm[t] for t in texts if t in norm)
        for name in outputs:
            ctx.tangency[name] = plan
            if ctx.forced.get(name, (None,))[0] in _RECOVERABLE:
                ctx.forced.pop(name)
        ctx.source_commands.append(SimpleNamespace(name=command, inputs=list(dict.fromkeys(dependencies)),
                                                   outputs=list(outputs), source_signature=plan.signature))


def _helper(builder, rec, owner, kind, ast, refs, suffix, domain=None):
    args = {'expr': {'kind': 'expr', 'ast': copy.deepcopy(ast)}, 'refs': {'kind': 'list', 'items': refs}}
    if domain is not None:
        for bound, value in zip(('min', 'max'), domain):
            if value is not None:
                args[bound] = {'kind': 'number', 'value': value}
    operation = {'function': 'function.expr', 'number': 'number.expression', 'point': 'point.expression'}[kind]
    return _private(builder, rec, owner, operation, kind, args, suffix)


def _private(builder, rec, owner, operation, kind, args, suffix):
    key = f'{rec.key}/inline/{suffix}'
    oid, eid = operation_id(builder.ns, key), element_id(builder.ns, key)
    builder.doc['operations'][oid] = {'id': oid, 'op': operation,
                                      'args': args, 'outputs': [{'slot': kind, 'elementId': eid}]}
    builder.doc['elements'][eid] = {'id': eid, 'type': kind, 'displayName': '',
                                   'producer': {'operationId': oid, 'slot': kind},
                                   'origin': {'kind': 'auto', 'source': owner}}
    builder.doc['appearance'][eid] = copy.deepcopy(HELPER_APPEARANCE)
    return {'kind': 'ref', 'elementId': eid}


def _scalar(builder, rec, owner, ast, refs):
    """Lower coordinates without changing the frozen numeric-expression op.

    For x(A), H=(0,y(A)), r=distance(A,H), B=(r,y(A)). Then
    x(A)=r-distance(A,B), including negative and zero coordinates. Projecting
    first avoids subtracting squared distances or depending on y(A)'s scale.
    The same construction with swapped coordinates gives y(A).
    """
    items, coordinates = [], {}

    def operand(ref):
        if ref not in items:
            items.append(ref)
        return {'ref': items.index(ref)}

    def lower(node):
        if node.get('fn') in ('x', 'y'):
            axis = node['fn']
            target = node['args'][0]
            key = (axis, repr(target))
            if key not in coordinates:
                suffix = f'coordinate/{len(coordinates)}'
                source = refs[target['ref']] if 'ref' in target else _helper(
                    builder, rec, owner, 'point', target, refs, suffix+'/input')
                other = {'fn': 'y' if axis == 'x' else 'x', 'args': [{'ref': 0}]}
                def pair(value):
                    return {'pair': [value, other] if axis == 'x' else [other, value]}
                h = _helper(builder, rec, owner, 'point', pair({'num': 0.}), [source], suffix+'/projection')
                r = _private(builder, rec, owner, 'measure.distance', 'number', {'point': source, 'to': h}, suffix+'/magnitude')
                b = _helper(builder, rec, owner, 'point', pair({'ref': 1}), [source, r], suffix+'/positive')
                distance = _private(builder, rec, owner, 'measure.distance', 'number', {'point': source, 'to': b}, suffix+'/distance')
                coordinates[key] = _helper(builder, rec, owner, 'number',
                    {'op': '-', 'args': [{'ref': 0}, {'ref': 1}]}, [r, distance], suffix+'/signed')
            return operand(coordinates[key])
        if 'ref' in node:
            return operand(refs[node['ref']])
        return {k: [lower(a) for a in value] if k == 'args' else value for k, value in node.items()}

    tree = lower(ast)
    if 'num' in tree:
        return {'kind': 'number', 'value': tree['num']}
    if 'ref' in tree:
        return items[tree['ref']]
    return _helper(builder, rec, owner, 'number', tree, items, 'x')


def _emit(builder, operation, args, outs, recs, ordinals, capacity):
    owner = operation_id(builder.ns, recs[0].key)
    repeated = operation in _REPEATED
    if repeated:
        args['count'] = {'kind': 'number', 'value': capacity}
    op = {'id': owner, 'op': operation, 'args': args, 'outputs': []}
    builder.doc['operations'][owner] = op
    bound = []
    for name, rec in zip(outs, recs):
        slot = f'tangent.{ordinals[name]+1}' if repeated else 'number' if operation == 'line.slope' else 'line'
        eid = builder.add_element(name, rec, owner, slot, 'number' if slot == 'number' else 'line')
        op['outputs'].append({'slot': slot, 'elementId': eid})
        rec.op_id = owner
        bound.append((name, slot))
    if repeated:
        builder.by_value[owner] = {'tangency': True, 'capacity': capacity, 'outputs': bound}


def build_tangency(builder, plan, outs, recs):
    from .construction import _Untranslated
    from ..expr.validate import problems

    if plan.error is not None:
        raise _Untranslated(*plan.error)

    def reference(name):
        if name in _AXES:
            from .ggb_conic import axis_ref
            return axis_ref(builder, name)
        eid = builder.element_of.get(name)
        if eid is None:
            raise _Untranslated('depends_on_unsupported', deps=[name])
        return {'kind': 'ref', 'elementId': eid}

    args = {slot: reference(name) for slot, name in plan.objects.items()}
    spec = plan.function if isinstance(plan.function, FunctionSpec) else None
    function_refs = [reference(n) for n in source_ref_names(spec, builder.ctx)] if spec else []
    if isinstance(plan.function, str):
        args['function'] = reference(plan.function)
    refs = [reference(n) for n in plan.number.refs] if plan.number else []
    if plan.number and problems(plan.number.ast, len(refs), operands=[
            builder.doc['elements'][r['elementId']]['type'] for r in refs], result='num'):
        raise _Untranslated('formula_unsupported', 'abscissa exceeds expression limits')
    # All references have been resolved before any helper is emitted.
    owner = operation_id(builder.ns, recs[0].key)
    if spec:
        args['function'] = _helper(builder, recs[0], owner, 'function', spec.ast, function_refs, 'function', spec.domain)
    if plan.number:
        args['x'] = _scalar(builder, recs[0], owner, plan.number.ast, refs)
    _emit(builder, plan.operation, args, outs, recs, plan.outputs, plan.capacity)


def build_classic_tangency(builder, row, inputs, outs, recs):
    """Use the same builder and matcher for the existing Python DSL factories."""
    from .construction import _Untranslated
    operation = row.get('op')
    if operation not in _OPERATIONS:
        return False
    if operation not in _REPEATED and len(outs) != 1:
        raise _Untranslated('unsupported_signature', 'the command has one output')
    if not 1 <= len(outs) <= 100:
        raise _Untranslated('unsupported_signature', 'invalid tangency output capacity')
    args = {slot: builder.arg_for(inp, slot, set()) for slot, inp in zip(row['args'], inputs)}
    if row.get('pointAbscissa'):
        owner = operation_id(builder.ns, recs[0].key)
        args['x'] = _scalar(builder, recs[0], owner, {'fn': 'x', 'args': [{'ref': 0}]}, [args['x']])
    ordinals = {name: builder.ctx.output_positions.get(name, i) for i, name in enumerate(outs)}
    _emit(builder, operation, args, outs, recs, ordinals, max(ordinals.values())+1)
    return True


def read_classic_curves(constr, ctx):
    """Read formula curves used by DSL tangents; other classic rows are unchanged."""
    from .ggb_conic import read_equations
    from .ggb_function import read_functions, source_report_value
    from .construction import _literal
    from .keys import KeyMaker

    commands = {str(getattr(o, 'name', o)): cmd for cmd in constr.commands for o in cmd.outputs}
    needed = set()
    pending = [i for cmd in constr.commands if cmd.name == 'Tangent' for i in cmd.inputs if isinstance(i, str)]
    if not pending:
        return
    while pending:
        name = pending.pop()
        if name in needed:
            continue
        needed.add(name)
        if name in commands:
            pending.extend(i for i in commands[name].inputs if isinstance(i, str))
    infos, domains = [], {}
    for obj in list(constr.elements) + list(constr.vars):
        label, data = obj.name, obj.data
        kind = type(data).__name__.lower()
        if _literal(data) is not None:
            kind = 'numeric'
            ctx.free_numbers[label] = {'value': _literal(data)}
        info = {'label': label, 'type': kind}
        cmd = commands.get(label)
        if label in needed and cmd is not None and cmd.name in ('Function', 'Conic') and cmd.inputs \
                and isinstance(cmd.inputs[0], str):
            # Classic appends formula references after its text. The native
            # reader discovers their identity from that text independently.
            info.update(command='Expression', inputs=cmd.inputs[:1])
            domain = getattr(data, 'explicit_domain', None)
            if cmd.name == 'Function' and domain is not None:
                dynamic = any(isinstance(i, str) and constr.objectByName(i) is not None
                              and not KeyMaker.is_phantom(i) for i in cmd.inputs[-2:])
                domains[label] = (domain, dynamic)
        infos.append(info)
    norm = {i['label']: i['label'] for i in infos}
    read_equations(infos, norm, ctx)
    read_functions(infos, norm, ctx)
    for name, (domain, dynamic) in domains.items():
        if dynamic:
            ctx.functions.pop(name, None)
            ctx.forced[name] = ('unsupported_signature', 'function domain depends on source objects')
        elif name in ctx.functions:
            ctx.functions[name].domain = list(domain)
            value = source_report_value(ctx.functions[name], ctx)
            if value is not None:
                ctx.expected[name] = value


def keep_owned_helpers(doc, keep):
    """Retain private DSL dependencies without adding them to the source report."""
    from ..document import iter_refs
    pending = list(keep)
    while pending:
        eid = pending.pop()
        op = doc['operations'][doc['elements'][eid]['producer']['operationId']]
        for arg in op['args'].values():
            for ref in iter_refs(arg):
                if ref not in keep and doc['elements'].get(ref, {}).get('origin', {}).get('kind') == 'auto':
                    keep.add(ref)
                    pending.append(ref)


def resolve_slots(builder, op_id, info, scale):
    """Bind a group injectively, prioritizing finite evidence then undefined.

    Missing coordinates give no evidence. An unmatched value keeps an unused
    ordinal and is reported as differs; a repeated saved line refuses the
    whole producer because native conic tangents are distinct.
    """
    from .construction import _drop_operation, _expected
    from ..kernel.evaluate import evaluate

    outputs = info['outputs']
    expected = {name: _expected(builder, builder.records[name]) for name, _ in outputs}
    finite = [exp for exp in expected.values() if exp is not None and exp.get('value') is not None]
    for i, exp in enumerate(finite):
        if any(compare(exp, other, scale)[0] == 'passed' for other in finite[:i]):
            _drop_operation(builder, op_id, 'unsupported_signature', 'saved line multiplicity requires coincident named outputs')
            return
    probe = copy.deepcopy(builder.doc)
    op = probe['operations'][op_id]
    capacity = max(2, info['capacity'])
    op['args']['count'] = {'kind': 'number', 'value': capacity}
    ids = {f'tangent.{i+1}': f'tangency-probe-{i}' for i in range(capacity)}
    op['outputs'] = [{'slot': slot, 'elementId': eid} for slot, eid in ids.items()]
    for slot, eid in ids.items():
        probe['elements'][eid] = {'id': eid, 'type': 'line', 'displayName': '',
                                  'producer': {'operationId': op_id, 'slot': slot}}
    ev = evaluate(probe)
    values = {slot: native_report_value('line', ev.elements[eid].get('value'))
              if ev.elements[eid]['state'] == 'defined' else None for slot, eid in ids.items()}
    selected, used = {}, set()
    for name, _ in outputs:
        exp = expected[name]
        if exp is None or exp.get('value') is None:
            continue
        matches = [s for s, v in values.items() if v is not None and compare(exp, v, scale)[0] == 'passed']
        if len(matches) > 1 or matches and matches[0] in used:
            _drop_operation(builder, op_id, 'unsupported_signature', 'saved lines do not identify distinct native slots')
            return
        if matches:
            selected[name] = matches[0]
            used.add(matches[0])
    for name, provisional in outputs:
        if name in selected:
            continue
        available = [s for s in ids if s not in used]
        exp = expected[name]
        if exp is not None and exp.get('value') is None:
            undefined = [s for s in available if values[s] is None]
            available = undefined or available
        slot = provisional if provisional in available else available[0]
        selected[name] = slot
        used.add(slot)
    op = builder.doc['operations'][op_id]
    op['args']['count']['value'] = max(info['capacity'], *(int(s.rsplit('.', 1)[1]) for s in selected.values()))
    for out in op['outputs']:
        name = next(n for n, _ in outputs if builder.element_of[n] == out['elementId'])
        out['slot'] = selected[name]
        builder.doc['elements'][out['elementId']]['producer']['slot'] = out['slot']
