"""Point/vector source formulas, independent of classic formula phantoms."""
from __future__ import annotations

import copy
import re

from .ggb_expr import ExprError, parse_typed
from .keys import operation_id

_VECTOR = re.compile(r'^\s*Vector\s*[\[(](.*)[\])]\s*$', re.DOTALL)
_RECOVERABLE = {'parse_error', 'unsupported_signature', 'no_registry_op'}


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
        source = wrapper.group(1) if wrapper else text
        try:
            ast, refs = parse_typed(source, kinds, result='vec')
        except ExprError as exc:
            ctx.typed_errors[name] = ('formula_unsupported', f'{text[:180]} ({exc.detail})')
        else:
            ctx.typed_formulas[name] = (ast, [norm[r] for r in refs], kind)
        ctx.forced.pop(name, None)

    commands = {str(getattr(o, 'name', o)): cmd for cmd in constr.commands for o in cmd.outputs}
    for info in infos:
        name, kind = norm[info['label']], info['type']
        inputs = info.get('inputs', [])
        if kind in ('point', 'vector') and info.get('command') == 'Expression' and len(inputs) == 1:
            read(name, inputs[0], kind)
        cmd = commands.get(name)
        if cmd is None or info.get('command') == 'Expression':
            continue
        for text, inp in zip(inputs, cmd.inputs):
            if _VECTOR.fullmatch(text) and isinstance(inp, str) and inp.startswith('_'):
                read(inp, text, 'vector')


def build_expression(builder, name):
    """Emit one typed source definition after resolving all operands."""
    from .construction import _Untranslated
    from ..expr.validate import problems

    ctx = builder.ctx
    rec = builder.record(name, key=builder.key_for(name))
    rec.command, rec.signature = 'Expression', None
    rec.status, rec.reason, rec.detail, rec.free = 'translated', None, None, False
    try:
        if name in ctx.forced:
            raise _Untranslated(*ctx.forced[name])
        if name in ctx.typed_errors:
            raise _Untranslated(*ctx.typed_errors[name])
        ast, names, kind = ctx.typed_formulas[name]
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
            raise _Untranslated('formula_unsupported', issues[0][1] if issues else 'операнд вне языка формул')
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
