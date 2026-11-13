"""Grouped source plans for GeoGebra function analysis, independent of classic.

Saved coordinates are evidence for slot binding and value checks only. They
never supply free inputs to a function analysis operation.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
import re
from types import SimpleNamespace

from .ggb_expr import ExprError, parse_typed
from .ggb_function import FunctionSpec, _parse_domain, parse_function, source_ref_names
from .keys import element_id, operation_id

_RECOVERABLE = {'parse_error', 'unsupported_signature', 'no_registry_op'}
_COMMANDS = {'Root', 'Roots', 'Extremum'}
_INDEX = re.compile(r'\+?\d+(?:\.0*)?\Z')


@dataclass
class NumberSource:
    ast: dict
    refs: list


@dataclass
class AnalysisPlan:
    command: str
    outputs: dict                       # normalized name -> original zero-based ordinal
    signature: str = ''
    operation: str = ''
    function: str | FunctionSpec | None = None
    numbers: dict = field(default_factory=dict)
    index: int | None = None
    capacity: int = 1
    error: tuple | None = None

    def dependencies(self, ctx):
        names = [self.function] if isinstance(self.function, str) else (
            source_ref_names(self.function, ctx) if self.function is not None else [])
        for number in self.numbers.values():
            names.extend(number.refs)
        return list(dict.fromkeys(names))


def _number(text, kinds, norm):
    if text.strip() in kinds and kinds[text.strip()] not in ('numeric', 'angle'):
        raise ExprError('unsupported_signature', 'a search input must be numeric')
    try:
        ast, refs = _parse_domain(text, kinds)
    except ExprError as exc:
        if exc.reason == 'parse_error':
            try:
                parse_typed(text, kinds, result='vec')
            except ExprError:
                pass
            else:
                raise ExprError('unsupported_signature', 'a point is not a numeric search input') from None
        raise
    return NumberSource(ast, [norm[r] for r in refs])


def _function(text, kinds, norm, ctx):
    name = text.strip()
    if name in kinds:
        normalized = norm[name]
        if kinds[name] != 'function' or normalized not in ctx.functions:
            raise ExprError('unsupported_signature', 'a native function definition is required')
        return normalized
    return parse_function(text, kinds, label='')


def _polynomial_shape(ast):
    """Reject nonpolynomial syntax even while a coefficient is undefined.

    Numeric validity, exponent integrality and degree still belong to the
    kernel coefficient reader; an upstream value must not hide sin(x) or x/x.
    """
    def contains(node, key):
        if isinstance(node, list):
            return any(contains(item, key) for item in node)
        return isinstance(node, dict) and (key in node or any(contains(v, key) for v in node.values()))

    def polynomial(node):
        if not contains(node, 'var') or 'var' in node:
            return True
        op, args = node.get('op'), node.get('args', [])
        if op in ('+', '-', 'neg', '*'):
            return all(polynomial(a) for a in args)
        if op in ('/', '^'):
            return polynomial(args[0]) and not contains(args[1], 'var')
        return False

    return not contains(ast, 'if') and polynomial(ast)


def _arguments(node):
    """Argument attribute order is not significant; a missing input is invalid."""
    if node is None:
        return []
    attrs = node.attrib
    if set(attrs) != {f'a{i}' for i in range(len(attrs))}:
        raise ExprError('unsupported_signature', 'non-contiguous command inputs')
    return [attrs[f'a{i}'] for i in range(len(attrs))]


def _configure(plan, inputs, kinds, norm, ctx):
    name = plan.command
    if name == 'Intersect':
        if len(inputs) not in (2, 3):
            raise ExprError('unsupported_signature', 'axis intersection requires two inputs and an optional static index')
        axes = [i for i, text in enumerate(inputs[:2]) if text.strip() in ('xAxis', 'yAxis')]
        if len(axes) != 1:
            raise ExprError('unsupported_signature', 'one coordinate axis and one function are required')
        axis = inputs[axes[0]].strip()
        if len(inputs) == 3:
            text = inputs[2].strip()
            if not _INDEX.fullmatch(text) or text in kinds:
                raise ExprError('unsupported_signature', 'axis intersection index must be a positive integer literal')
            # Bound the source integer before converting untrusted text.
            if len(text) > 16 or not 1 <= float(text) <= 100:
                raise ExprError('unsupported_signature', 'axis intersection index is outside the supported slots')
            plan.index = int(float(text))
        if axis == 'yAxis' and plan.index not in (None, 1):
            raise ExprError('unsupported_signature', 'the y-axis intersection has only static output 1')
        plan.function = _function(inputs[1 - axes[0]], kinds, norm, ctx)
        plan.operation = 'point.expression' if axis == 'yAxis' else 'function.roots_polynomial'
    else:
        modes = {('Root', 1): 'roots_polynomial', ('Root', 2): 'root_near',
                 ('Root', 3): 'root_interval', ('Roots', 3): 'roots_interval',
                 ('Extremum', 1): 'extrema_polynomial', ('Extremum', 3): 'extrema_interval'}
        mode = modes.get((name, len(inputs)))
        if mode is None:
            raise ExprError('unsupported_signature', f'unsupported {name} signature')
        plan.operation = 'function.' + mode
        plan.function = _function(inputs[0], kinds, norm, ctx)
        slots = ('start',) if mode == 'root_near' else ('a', 'b')
        plan.numbers = {slot: _number(text, kinds, norm) for slot, text in zip(slots, inputs[1:])}
    repeated = plan.operation in ('function.roots_polynomial', 'function.roots_interval',
                                 'function.extrema_polynomial', 'function.extrema_interval')
    if not repeated and (len(plan.outputs) != 1 or next(iter(plan.outputs.values())) != 0):
        raise ExprError('unsupported_signature', 'the command has one output')


def _value_call(text, kinds, norm):
    """A top-level numeric f(a); arithmetic around calls keeps its prior reader."""
    ast, refs = parse_typed(text, kinds, result='num')
    if 'call' not in ast:
        return None
    name = refs[ast['call']]
    argument = ast['args'][0]
    labels = []

    def scalar(node):
        if 'call' in node or 'pair' in node or node.get('fn') in ('x', 'y'):
            raise ExprError('formula_unsupported', 'the function argument must be a native numeric expression')
        if 'ref' in node:
            source = refs[node['ref']]
            if kinds[source] not in ('numeric', 'angle'):
                raise ExprError('formula_unsupported', 'the function argument must reference numbers')
            if source not in labels:
                labels.append(source)
            return {'ref': labels.index(source)}
        return {k: [scalar(a) for a in value] if k == 'args' else value for k, value in node.items()}

    return name, NumberSource(scalar(argument), [norm[n] for n in labels])


def read_analysis(root, infos, norm, ctx):
    """Record one plan per XML command, including refused source definitions."""
    kinds = {info['label']: info['type'] for info in infos}
    by_label = {info['label']: info for info in infos}

    def add(plan):
        if not plan.outputs:
            return
        if plan.capacity > 100:
            from .ggb import ImportRefused
            raise ImportRefused('import_too_many_objects', 'function analysis output capacity exceeds 100')
        names = list(plan.outputs)
        for name in names:
            ctx.function_analysis[name] = plan
            forced = ctx.forced.get(name)
            if forced is not None and forced[0] in _RECOVERABLE:
                ctx.forced.pop(name)
            # Numeric f(a) belongs to function.value, never a saved number expression.
            ctx.formulas.pop(name, None)
        ctx.source_commands.append(SimpleNamespace(name=plan.command, inputs=plan.dependencies(ctx), outputs=names,
                                                   source_signature=plan.signature))

    for node in root.findall('./construction/command'):
        name = node.attrib.get('name')
        inp, out = node.find('input'), node.find('output')
        texts = [inp.attrib.get(f'a{i}', '') for i in range(2)] if inp is not None else []
        targeted = name in _COMMANDS or name == 'Intersect' and any(
            t.strip() in ('xAxis', 'yAxis') for t in texts[:2]) and any(
                kinds.get(t.strip()) == 'function' or 'x' in t and t.strip() not in kinds for t in texts[:2]
                if t.strip() not in ('xAxis', 'yAxis'))
        if not targeted or out is None:
            continue
        ordinals = {}
        for attr, label in out.attrib.items():
            if attr.startswith('a') and attr[1:].isdigit():
                ordinals[attr] = int(attr[1:])
        outputs = {norm[label]: ordinals[attr] for attr, label in sorted(
            out.attrib.items(), key=lambda item: ordinals.get(item[0], 0))
            if attr in ordinals and label in norm and by_label[label].get('command') == name
            and norm[label] not in ctx.function_analysis}
        plan = AnalysisPlan(name, outputs, capacity=max(ordinals.values(), default=0) + 1)
        try:
            inputs = _arguments(inp)
            plan.signature = f'{name}({", ".join(inputs)})'
            if len(ordinals) != len(out.attrib):
                raise ExprError('unsupported_signature', 'invalid output ordinal')
            expected_type = 'point'
            if any(kinds[ctx.display[n]] != expected_type for n in outputs):
                raise ExprError('unsupported_signature', 'function analysis requires point outputs outside CAS')
            _configure(plan, inputs, kinds, norm, ctx)
        except ExprError as exc:
            plan.error = (exc.reason, exc.detail)
        add(plan)

    for info in infos:
        if info['type'] != 'numeric' or info.get('command') != 'Expression' or len(info.get('inputs', [])) != 1:
            continue
        text = info['inputs'][0]
        try:
            call = _value_call(text, kinds, norm)
            if call is None:
                continue
            function, number = call
            plan = AnalysisPlan('Expression', {norm[info['label']]: 0}, operation='function.value',
                                function=_function(function, kinds, norm, ctx), numbers={'x': number})
        except ExprError as exc:
            # Claim only a leading call to a source function; ordinary numeric
            # expressions keep their existing parser and diagnostics.
            if not any(re.match(re.escape(label) + r'\s*[\[(]', text.strip()) for label in kinds
                       if kinds[label] == 'function'):
                continue
            plan = AnalysisPlan('Expression', {norm[info['label']]: 0}, error=(exc.reason, exc.detail))
        plan.signature = text
        name = norm[info['label']]
        if ctx.forced.get(name, (None,))[0] == 'formula_unsupported':
            # The legacy scalar reader cannot read function calls. This reader
            # owns that precise source form, including its language errors.
            ctx.forced.pop(name)
        add(plan)


def build_analysis(builder, plan, outs, recs):
    """Resolve every dependency before emitting the operation and private helpers."""
    from .construction import _Untranslated
    from ..expr.validate import problems
    from ..kernel.evaluate import evaluate
    from ..kernel.function_analysis import AnalysisError, Budget, coefficients

    if plan.error is not None:
        raise _Untranslated(*plan.error)
    ctx = builder.ctx
    owner = operation_id(builder.ns, recs[0].key)
    polynomial = plan.operation in ('function.roots_polynomial', 'function.extrema_polynomial')
    source = ctx.functions[plan.function] if isinstance(plan.function, str) else plan.function
    if polynomial and not _polynomial_shape(source.ast):
        raise _Untranslated('unsupported_signature', 'polynomial mode requires a native polynomial')

    def references(names):
        items = []
        for name in names:
            eid = builder.element_of.get(name)
            if eid is None:
                raise _Untranslated('depends_on_unsupported', deps=[name])
            if builder.doc['elements'][eid]['type'] != 'number':
                raise _Untranslated('formula_unsupported', 'a numeric dependency is required')
            items.append({'kind': 'ref', 'elementId': eid})
        return items

    # No mutation until all operands are resolved and the source AST is valid.
    if isinstance(plan.function, str):
        function_id = builder.element_of.get(plan.function)
        if function_id is None:
            raise _Untranslated('depends_on_unsupported', deps=[plan.function])
        function_arg = {'kind': 'ref', 'elementId': function_id}
        function_value = None
    else:
        spec = plan.function
        function_refs = references(source_ref_names(spec, ctx))
        function_value = {'expr': spec.ast, 'refs': [], 'domain': spec.domain}
        function_arg = None
    numbers = {}
    for slot, source in plan.numbers.items():
        refs = references(source.refs)
        if problems(source.ast, len(refs)):
            raise _Untranslated('formula_unsupported', 'numeric argument exceeds expression limits')
        numbers[slot] = (source.ast, refs)

    if polynomial:
        ev = evaluate(builder.doc)
        if function_arg is not None:
            state = ev.elements.get(function_id, {})
            function_value = state.get('value') if state.get('state') == 'defined' else None
        else:
            function_value = dict(function_value, refs=[ev.elements.get(r['elementId'], {}).get('value', {}).get('value')
                                                      for r in function_refs])
            if any(v is None for v in function_value['refs']):
                function_value = None
        if function_value is not None:
            try:
                coefficients(function_value, Budget())
            except AnalysisError as exc:
                if exc.reason == 'not_polynomial':
                    raise _Untranslated('unsupported_signature', 'polynomial mode requires a native polynomial') from None
                # A native numerical limit remains an explicit evaluated state.

    def helper(kind, ast, refs, suffix, domain=None):
        key = f'{recs[0].key}/inline/{suffix}'
        oid, eid = operation_id(builder.ns, key), element_id(builder.ns, key)
        args = {'expr': {'kind': 'expr', 'ast': copy.deepcopy(ast)}, 'refs': {'kind': 'list', 'items': refs}}
        if domain is not None:
            for bound, value in zip(('min', 'max'), domain):
                if value is not None:
                    args[bound] = {'kind': 'number', 'value': value}
        builder.doc['operations'][oid] = {'id': oid, 'op': 'function.expr' if kind == 'function' else 'number.expression',
                                          'args': args, 'outputs': [{'slot': kind, 'elementId': eid}]}
        builder.doc['elements'][eid] = {'id': eid, 'type': kind, 'displayName': '',
                                       'producer': {'operationId': oid, 'slot': kind},
                                       'origin': {'kind': 'auto', 'source': owner}}
        return {'kind': 'ref', 'elementId': eid}

    if function_arg is None:
        spec = plan.function
        function_arg = helper('function', spec.ast, function_refs, 'function', spec.domain)
    args = {'function': function_arg}
    for slot, (ast, refs) in numbers.items():
        if 'num' in ast:
            args[slot] = {'kind': 'number', 'value': ast['num']}
        elif 'ref' in ast:
            args[slot] = refs[ast['ref']]
        else:
            args[slot] = helper('number', ast, refs, slot)
    if plan.operation == 'point.expression':
        args = {'expr': {'kind': 'expr', 'ast': {'pair': [{'num': 0.}, {'call': 0, 'args': [{'num': 0.}]}]}},
                'refs': {'kind': 'list', 'items': [function_arg]}}
    repeated = plan.operation in ('function.roots_polynomial', 'function.roots_interval',
                                 'function.extrema_polynomial', 'function.extrema_interval')
    base = 'extremum' if 'extrema' in plan.operation else 'root'
    if repeated:
        args['count'] = {'kind': 'number', 'value': max(plan.capacity, plan.index or 1)}
    op = {'id': owner, 'op': plan.operation, 'args': args, 'outputs': []}
    builder.doc['operations'][owner] = op
    bound = []
    for name, rec in zip(outs, recs):
        slot = (f'{base}.{plan.index or plan.outputs[name] + 1}' if repeated else
                'number' if plan.operation == 'function.value' else
                'point' if plan.operation == 'point.expression' else 'root')
        kind = 'number' if slot == 'number' else 'point'
        eid = builder.add_element(name, rec, owner, slot, kind)
        op['outputs'].append({'slot': slot, 'elementId': eid})
        rec.op_id = owner
        bound.append((name, slot))
    if repeated and plan.index is None:
        builder.by_value[owner] = {'function_analysis': True, 'base': base, 'capacity': plan.capacity,
                                   'slots': [f'{base}.{i}' for i in range(1, 101)], 'outputs': bound}


def resolve_slots(builder, op_id, info, scale):
    """Match finite outputs uniquely, reserving undefined ranks without skipping.

    At most 100 by 100 comparisons replace the factorial intersection matcher.
    Insufficient or conflicting evidence explicitly refuses the grouped command.
    """
    from .construction import _drop_operation
    from .values import compare, native_report_value
    from ..kernel.evaluate import evaluate

    probe = copy.deepcopy(builder.doc)
    op = probe['operations'][op_id]
    op['args']['count'] = {'kind': 'number', 'value': 100}
    ids = {}
    for i, slot in enumerate(info['slots']):
        eid = f'function-probe-{i}'
        ids[slot] = eid
        probe['elements'][eid] = {'id': eid, 'type': 'point', 'displayName': '',
                                   'producer': {'operationId': op_id, 'slot': slot}}
    op['outputs'] = [{'slot': slot, 'elementId': eid} for slot, eid in ids.items()]
    ev = evaluate(probe)
    values = {slot: native_report_value('point', ev.elements.get(eid, {}).get('value'))
              if ev.elements.get(eid, {}).get('state') == 'defined' else None for slot, eid in ids.items()}
    selected, used = {}, set()
    for name, provisional in info['outputs']:
        expected = builder.ctx.expected.get(name)
        slot = provisional
        if expected is not None and expected.get('value') is not None:
            matches = [s for s, value in values.items() if value is not None
                       and compare(expected, value, scale)[0] == 'passed']
            if len(matches) > 1:
                _drop_operation(builder, op_id, 'unsupported_signature', 'saved output does not identify one native slot')
                return
            if matches:
                slot = matches[0]
        if slot in used:
            _drop_operation(builder, op_id, 'unsupported_signature', 'source outputs require the same native slot')
            return
        used.add(slot)
        selected[builder.element_of[name]] = slot
    op = builder.doc['operations'][op_id]
    op['args']['count']['value'] = max(info['capacity'], *(int(s.rsplit('.', 1)[1]) for s in selected.values()))
    for out in op['outputs']:
        out['slot'] = selected[out['elementId']]
        builder.doc['elements'][out['elementId']]['producer']['slot'] = out['slot']
