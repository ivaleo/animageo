"""Point/vector source formulas, independent of classic formula phantoms."""
from __future__ import annotations

import copy
import re
from types import SimpleNamespace

from .ggb_expr import MAX_CHARS, ExprError, _tokens, parse_number, parse_typed
from .keys import KeyMaker, operation_id

_VECTOR = re.compile(r'^\s*Vector\s*(?:\[(.*)\]|\((.*)\))\s*$', re.DOTALL)
_RECOVERABLE = {'parse_error', 'unsupported_signature', 'no_registry_op'}


def _two_arguments(source):
    """Recognize the existing Vector(A, B) form with the native tokenizer."""
    if len(source) > MAX_CHARS:
        return False
    tokens = _tokens(source)
    closes, commas = [], []
    for i, (kind, value) in enumerate(tokens):
        if kind != 'op':
            continue
        if value in ('(', '['):
            closes.append(')' if value == '(' else ']')
        elif value in (')', ']'):
            if not closes or closes.pop() != value:
                return False
        elif value == ',' and not closes:
            commas.append(i)
    return not closes and len(commas) == 1 and 0 < commas[0] < len(tokens) - 1


def read_expressions(infos, norm, ctx, constr):
    """Read XML formulas and single-argument Vector wrappers.

    Existing lowerings get the first attempt. A refused source formula is
    still a source definition, so a saved classic point cannot become free.
    Scripts and other source restrictions always take precedence.
    """
    kinds = {i['label']: i['type'] for i in infos}

    def read(name, text, kind):
        forced = ctx.forced.get(name)
        if forced and forced[0] not in _RECOVERABLE:
            return
        wrapper = _VECTOR.fullmatch(text) if kind == 'vector' else None
        source = (wrapper.group(1) if wrapper.group(1) is not None else wrapper.group(2)) if wrapper else text
        try:
            if wrapper and _two_arguments(source):
                return  # The existing Vector(A, B) lowering owns this form.
            ast, refs = parse_typed(source, kinds, result='vec')
        except ExprError as exc:
            ctx.typed_errors[name] = ('formula_unsupported', f'{text[:180]} ({exc.detail})')
        else:
            ctx.typed_formulas[name] = (ast, [norm[r] for r in refs], kind, text)
        ctx.forced.pop(name, None)

    commands = {str(getattr(o, 'name', o)): cmd for cmd in constr.commands for o in cmd.outputs}
    for info in infos:
        name, kind = norm[info['label']], info['type']
        inputs = info.get('inputs', [])
        if kind in ('point', 'vector') and info.get('command') == 'Expression' and len(inputs) == 1:
            read(name, inputs[0], kind)
        cmd = commands.get(name)
        if info.get('command') in (None, 'Expression'):
            continue
        if cmd is None:
            forced = ctx.forced.get(name)
            if forced and forced[0] not in _RECOVERABLE or not any(_VECTOR.fullmatch(t) for t in inputs):
                continue
            recovered = []
            helpers = []
            for i, text in enumerate(inputs):
                if _VECTOR.fullmatch(text):
                    counter = 900000 + len(ctx.source_commands) * 100 + i
                    while f'_{counter}' in commands or f'_{counter}' in ctx.keys or f'_{counter}' in ctx.display:
                        counter += 1
                    helper = f'_{counter}'
                    helpers.append((helper, text, i, 'vector'))
                    recovered.append(helper)
                elif text.strip() in norm:
                    recovered.append(norm[text.strip()])
                else:
                    from ..expr import evaluate
                    from ..expr.evaluate import ExprError as EvaluationError
                    try:
                        ast, refs = parse_number(text, kinds)
                        if refs:
                            if info['command'] != 'Rotate' or i != 1 or name not in ctx.angle_formulas:
                                break
                            counter = 900000 + len(ctx.source_commands) * 100 + i
                            while f'_{counter}' in commands or f'_{counter}' in ctx.keys or f'_{counter}' in ctx.display:
                                counter += 1
                            helper = f'_{counter}'
                            helpers.append((helper, text, i, 'angle'))
                            recovered.append(helper)
                            continue
                        recovered.append(evaluate(ast))
                    except (ExprError, EvaluationError):
                        break
            else:
                for helper, text, i, helper_kind in helpers:
                    ctx.keys[helper] = f'ggb:{info["label"]}/inline/{helper_kind}/{i}'
                    ctx.xml_types[helper] = helper_kind
                    if helper_kind == 'vector':
                        ctx.order[helper] = info['order'] - .5
                        read(helper, text, 'vector')
                ctx.forced.pop(name, None)
                ctx.source_commands.append(SimpleNamespace(name=info['command'], inputs=recovered, outputs=[name]))
            continue
        for text, inp in zip(inputs, cmd.inputs):
            if _VECTOR.fullmatch(text) and isinstance(inp, str) and inp.startswith('_'):
                read(inp, text, 'vector')


def commands_with_source(constr, ctx):
    """Insert recovered commands before the next classic command's helpers."""
    pending = sorted(ctx.source_commands, key=lambda c: ctx.order[c.outputs[0]])
    result, chunk = [], []
    for cmd in constr.commands:
        chunk.append(cmd)
        names = [str(getattr(o, 'name', o)) for o in cmd.outputs]
        order = [ctx.order[o] for o in names if o in ctx.order]
        if order:
            while pending and ctx.order[pending[0].outputs[0]] < min(order):
                result.append(pending.pop(0))
            result.extend(chunk)
            chunk = []
    return result + pending + chunk


def build_expression(builder, name):
    """Emit one typed source definition after resolving all operands."""
    from .construction import _Untranslated
    from ..expr.validate import problems

    ctx = builder.ctx
    rec = builder.record(name, key=builder.key_for(name))
    if KeyMaker.is_phantom(name):
        # Helpers have no construction-protocol position. Source scheduling
        # uses ctx.order, while their optional seq follows all named objects.
        rec.order = 10 ** 6 + len(builder.records)
    rec.command, rec.signature = 'Expression', None
    rec.status, rec.reason, rec.detail, rec.free = 'translated', None, None, False
    try:
        if name in ctx.forced:
            raise _Untranslated(*ctx.forced[name])
        if name in ctx.typed_errors:
            raise _Untranslated(*ctx.typed_errors[name])
        ast, names, kind, text = ctx.typed_formulas[name]
        rec.inputs = list(names)
        items = []
        for source in names:
            eid = builder.element_of.get(source)
            if eid is None:
                raise _Untranslated('depends_on_unsupported', deps=[source])
            items.append({'kind': 'ref', 'elementId': eid})
        operands = [builder.doc['elements'][r['elementId']]['type'] for r in items]
        issues = problems(ast, len(items), operands=operands, result='vec')
        if issues or any(t not in ('number', 'point', 'vector', 'function') for t in operands):
            detail = issues[0][1] if issues else 'операнд вне языка формул'
            raise _Untranslated('formula_unsupported', f'{text[:180]} ({detail})')
    except _Untranslated as exc:
        rec.status = 'closure' if exc.reason == 'depends_on_unsupported' else 'untranslated'
        rec.reason, rec.detail = exc.reason, exc.detail
        return
    if kind == 'point' and not names:
        xy = ctx.free_points.get(name)
        if xy is not None:
            builder.free_point(name, rec, xy)
            return
    oid = operation_id(builder.ns, rec.key)
    builder.doc['operations'][oid] = {
        'id': oid, 'op': kind + '.expression',
        'args': {'expr': {'kind': 'expr', 'ast': copy.deepcopy(ast)}, 'refs': {'kind': 'list', 'items': items}},
        'outputs': []}
    eid = builder.add_element(name, rec, oid, kind, kind)
    builder.doc['operations'][oid]['outputs'].append({'slot': kind, 'elementId': eid})
    rec.op_id = oid
