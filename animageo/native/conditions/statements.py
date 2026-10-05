"""Statements (plan L3 §3.2): the AST shared with the web, its structural
rules, the compiler to ``check`` predicates and the measure of a statement
in an evaluated document (docs/native/conditions.md).

::

    Statement := {kind: "eq"|"ne", left: Expr, right: Expr}
               | {kind: "parallel"|"perpendicular"|"tangent"|"congruent", a: Obj, b: Obj}
               | {kind: "on", point: Ref, object: Obj}
               | {kind: "collinear"|"concyclic", points: [Ref…]}
               | {kind: "coincident", points: [Ref, Ref]}
               | {kind: "concurrent", lines: [Obj…]}
    Expr := an AST v1 node of number.expression (num, const pi, op, fn)
            | {len: Obj} | {angle: [Ref, Ref, Ref] | Ref} | {ref: id of a number} | {deg: number}
    Obj  := {ref: id} | {pair: [idP, idQ]}
    Ref  := {ref: id of a point}

A pair is a segment in ``len`` and the line ``PQ`` in ``∥ ⟂ tangent on
concurrent``; it creates no operation. ``eq`` compares ``|left − right|``
in the units of the expression: a length as is, an angle and a scalar times
``S`` (the scale contract of the checks).
"""
from __future__ import annotations

import math

from ..expr.evaluate import ExprError, evaluate as expr_evaluate
from ..kernel import relations as rel
from ..kernel.checks import classify

__all__ = ['KINDS', 'statement_problems', 'statement_elements', 'statement_checks', 'measure_statement',
           'mark_statement', 'pair_points']

KINDS = ('eq', 'ne', 'parallel', 'perpendicular', 'tangent', 'on', 'collinear', 'concyclic', 'concurrent',
         'congruent', 'coincident')
_OBJ2 = ('parallel', 'perpendicular', 'tangent', 'congruent')
_OPS = ('+', '-', '*', '/', '^')
_FNS = {'sqrt': 1, 'abs': 1, 'sin': 1, 'cos': 1, 'tan': 1, 'atan': 1, 'asin': 1, 'acos': 1, 'exp': 1,
        'ln': 1, 'lg': 1, 'min': 2, 'max': 2}
MAX_NODES = 256


def _is_id(value) -> bool:
    return isinstance(value, str) and bool(value)


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


# ── structure ─────────────────────────────────────────────────────────────

class _Problems:
    def __init__(self, doc):
        self.doc = doc
        self.out = []          # [(code, path, message, elementId)]
        self.nodes = 0

    def add(self, path, message, code='condition_bad_statement', element_id=None):
        self.out.append((code, path, message, element_id))

    def element(self, el_id, path, types=None, what='an element'):
        if not _is_id(el_id):
            self.add(path, f'{what} must be an element ID')
            return
        if self.doc is None:
            return
        el = self.doc.elements.get(el_id)
        if el is None:
            self.add(path, f'element {el_id!r} does not exist', 'condition_unknown_element', el_id)
        elif types is not None and el['type'] not in types:
            self.add(path, f'element {el_id!r} is a {el["type"]}, not {what}', element_id=el_id)

    def ref(self, node, path, types=('point',), what='a point'):
        if not (isinstance(node, dict) and set(node) == {'ref'}):
            self.add(path, f'{what} must be {{"ref": id}}')
            return
        self.element(node['ref'], path + '/ref', types, what)

    def obj(self, node, path, types=None):
        if isinstance(node, dict) and set(node) == {'ref'}:
            self.element(node['ref'], path + '/ref', types, 'an object of this statement')
            return
        if isinstance(node, dict) and set(node) == {'pair'}:
            pair = node['pair']
            if not (isinstance(pair, list) and len(pair) == 2):
                self.add(path + '/pair', 'a pair is two point IDs')
                return
            for k, el_id in enumerate(pair):
                self.element(el_id, f'{path}/pair/{k}', ('point',), 'a point')
            if pair[0] == pair[1]:
                self.add(path + '/pair', 'the two points of a pair must differ')
            return
        self.add(path, 'an object must be {"ref": id} or {"pair": [idP, idQ]}')

    def expr(self, node, path, depth=1):
        self.nodes += 1
        if self.nodes > MAX_NODES or depth > 32:
            self.add(path, 'the expression is too large')
            return
        if not isinstance(node, dict) or len(node) == 0:
            self.add(path, 'an expression node must be an object')
            return
        keys = set(node)
        if keys == {'num'}:
            if not _num(node['num']):
                self.add(path + '/num', 'num must be a finite number')
        elif keys == {'deg'}:
            if not _num(node['deg']):
                self.add(path + '/deg', 'deg must be a finite number')
        elif keys == {'const'}:
            if node['const'] != 'pi':
                self.add(path + '/const', 'the only constant is pi')
        elif keys == {'ref'}:
            self.element(node['ref'], path + '/ref', ('number',), 'a number')
        elif keys == {'len'}:
            self.obj(node['len'], path + '/len', ('segment', 'vector'))
        elif keys == {'angle'}:
            arg = node['angle']
            if isinstance(arg, list):
                if len(arg) != 3:
                    self.add(path + '/angle', 'an angle is three points')
                for k, item in enumerate(arg if isinstance(arg, list) else ()):
                    self.ref(item, f'{path}/angle/{k}')
            else:
                self.ref(arg, path + '/angle', ('angle',), 'an angle')
        elif keys == {'op', 'args'}:
            args = node['args']
            arity = 1 if node['op'] == 'neg' else 2
            if node['op'] not in _OPS + ('neg',) or not isinstance(args, list) or len(args) != arity:
                self.add(path, 'an operator node is {op: + - * / ^ | neg, args}')
                return
            for k, child in enumerate(args):
                self.expr(child, f'{path}/args/{k}', depth + 1)
        elif keys == {'fn', 'args'}:
            args = node['args']
            if node['fn'] not in _FNS or not isinstance(args, list) or len(args) != _FNS[node['fn']]:
                self.add(path, 'a function node is {fn, args} with a known function and its arity')
                return
            for k, child in enumerate(args):
                self.expr(child, f'{path}/args/{k}', depth + 1)
        else:
            self.add(path, f'unknown expression node with keys {sorted(keys)}')


def statement_problems(statement, doc=None, path='') -> list:
    """``[(code, path, message, elementId)]``: ``condition_bad_statement``
    (shape, kinds, types) and ``condition_unknown_element``; types and
    existence are checked only with ``doc``."""
    p = _Problems(doc)
    if not isinstance(statement, dict):
        p.add(path, 'a statement must be an object')
        return p.out
    kind = statement.get('kind')
    if kind not in KINDS:
        p.add(path + '/kind', f'kind must be one of {", ".join(KINDS)}')
        return p.out
    if kind in ('eq', 'ne'):
        allowed = {'kind', 'left', 'right'}
        for side in ('left', 'right'):
            if side not in statement:
                p.add(path, f'{side} is missing')
            else:
                p.expr(statement[side], f'{path}/{side}')
    elif kind in _OBJ2:
        allowed = {'kind', 'a', 'b'}
        types = {'parallel': None, 'perpendicular': None, 'tangent': None, 'congruent': None}[kind]
        for side in ('a', 'b'):
            if side not in statement:
                p.add(path, f'{side} is missing')
            else:
                p.obj(statement[side], f'{path}/{side}', types)
    elif kind == 'on':
        allowed = {'kind', 'point', 'object'}
        if 'point' not in statement or 'object' not in statement:
            p.add(path, 'point and object are required')
        else:
            p.ref(statement['point'], path + '/point')
            p.obj(statement['object'], path + '/object')
    elif kind in ('collinear', 'concyclic', 'coincident'):
        allowed = {'kind', 'points'}
        least = {'collinear': 3, 'concyclic': 4, 'coincident': 2}[kind]
        pts = statement.get('points')
        if not isinstance(pts, list) or len(pts) < least or (kind == 'coincident' and len(pts) != 2):
            p.add(path + '/points', f'{kind} takes {"two" if kind == "coincident" else f"at least {least}"} points')
        else:
            for k, item in enumerate(pts):
                p.ref(item, f'{path}/points/{k}')
    else:  # concurrent
        allowed = {'kind', 'lines'}
        lines = statement.get('lines')
        if not isinstance(lines, list) or len(lines) < 3:
            p.add(path + '/lines', 'concurrent takes at least three lines')
        else:
            for k, item in enumerate(lines):
                p.obj(item, f'{path}/lines/{k}')
    extra = sorted(set(statement) - allowed)
    if extra:
        p.add(path, f'unknown keys {extra}')
    return p.out


def _walk_ids(node, out):
    if isinstance(node, dict):
        if set(node) == {'ref'} and isinstance(node['ref'], str):
            out.append(node['ref'])
            return
        if set(node) == {'pair'} and isinstance(node['pair'], list):
            out.extend(x for x in node['pair'] if isinstance(x, str))
            return
        for key in sorted(node):
            if key != 'kind':
                _walk_ids(node[key], out)
    elif isinstance(node, list):
        for item in node:
            _walk_ids(item, out)


def statement_elements(statement) -> list:
    """The element IDs a statement names, in the order of the statement,
    without repeats (the order of the keys: ``a``/``b``, ``left``/``right``,
    ``point``/``object``, ``points``, ``lines``)."""
    out = []
    order = ('a', 'b', 'left', 'right', 'point', 'object', 'points', 'lines')
    for key in order:
        if key in statement:
            _walk_ids(statement[key], out)
    seen = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def pair_points(statement) -> list:
    """``[(idP, idQ)]`` of the pairs of a statement."""
    out = []

    def walk(node):
        if isinstance(node, dict):
            if set(node) == {'pair'} and isinstance(node['pair'], list) and len(node['pair']) == 2:
                out.append(tuple(node['pair']))
                return
            for key in sorted(node):
                walk(node[key])
        elif isinstance(node, list):
            for item in node:
                walk(item)
    walk(statement)
    return out


# ── compiler to predicates ────────────────────────────────────────────────

def statement_checks(doc, statement) -> list:
    """The predicates a statement compiles to: ``[{predicate, args}]`` where
    an argument is an element ID, ``{"pair": [P, Q]}`` or, for
    ``equal_value``, the two expressions; ``ne`` is ``not`` around
    ``equal_value``. Structural."""
    kind = statement['kind']
    if kind in ('eq', 'ne'):
        inner = {'predicate': 'equal_value', 'args': [statement['left'], statement['right']]}
        return [inner] if kind == 'eq' else [{'predicate': 'not', 'args': [inner]}]

    def arg(node):
        return node['ref'] if set(node) == {'ref'} else {'pair': list(node['pair'])}
    if kind in _OBJ2:
        return [{'predicate': kind, 'args': [arg(statement['a']), arg(statement['b'])]}]
    if kind == 'on':
        return [{'predicate': 'incident', 'args': [arg(statement['point']), arg(statement['object'])]}]
    if kind in ('collinear', 'concyclic', 'coincident'):
        return [{'predicate': kind, 'args': [arg(x) for x in statement['points']]}]
    return [{'predicate': 'concurrent', 'args': [arg(x) for x in statement['lines']]}]


# ── measure ───────────────────────────────────────────────────────────────

class _Undefined(Exception):
    def __init__(self, ids):
        super().__init__('undefined')
        self.ids = ids


def _value(ev, el_id):
    state = ev.elements.get(el_id)
    if state is None or state['state'] != 'defined':
        raise _Undefined([el_id])
    return state['value']


def _point(ev, el_id):
    return rel._xy(_value(ev, el_id))


def _item(doc, ev, arg, tol, *, as_segment=False):
    """``(type, value)`` of an argument; a pair is a line (or a segment)."""
    if isinstance(arg, str):
        return doc.elements[arg]['type'], _value(ev, arg)
    p, q = arg['pair']
    (px, py), (qx, qy) = _point(ev, p), _point(ev, q)
    length = math.hypot(qx - px, qy - py)
    if as_segment:
        return 'segment', {'a': [px, py], 'b': [qx, qy], 'length': length}
    if length <= tol.decide_length:
        raise rel._Inconclusive('coincident_points')
    return 'line', {'p': [px, py], 'dir': [(qx - px) / length, (qy - py) / length]}


def _convex_angle(a, b, c):
    ux, uy = a[0] - b[0], a[1] - b[1]
    vx, vy = c[0] - b[0], c[1] - b[1]
    return math.atan2(abs(ux * vy - uy * vx), ux * vx + uy * vy)


def _unit_of(node) -> str:
    """``length`` when a ``len`` leaf is in the tree, else ``angle`` with an
    ``angle`` or ``deg`` leaf, else ``scalar``."""
    found = set()

    def walk(n):
        if isinstance(n, dict):
            if 'len' in n:
                found.add('length')
                return
            if 'angle' in n or 'deg' in n:
                found.add('angle')
                return
            for child in n.get('args', ()) if isinstance(n.get('args'), list) else ():
                walk(child)
    walk(node)
    return 'length' if 'length' in found else 'angle' if 'angle' in found else 'scalar'


def _to_ast(doc, ev, node, refs, tol):
    """The AST v1 tree of a statement expression; leaves become ``ref`` items."""
    keys = set(node)
    if keys in ({'num'}, {'const'}):
        return dict(node)
    if keys == {'deg'}:
        refs.append(node['deg'] * math.pi / 180)
        return {'ref': len(refs) - 1}
    if keys == {'ref'}:
        refs.append(float(_value(ev, node['ref'])['value']))
        return {'ref': len(refs) - 1}
    if keys == {'len'}:
        target = node['len']
        if set(target) == {'ref'}:
            refs.append(float(_value(ev, target['ref'])['length']))
        else:
            refs.append(_item(doc, ev, {'pair': target['pair']}, tol, as_segment=True)[1]['length'])
        return {'ref': len(refs) - 1}
    if keys == {'angle'}:
        arg = node['angle']
        if isinstance(arg, list):
            a, b, c = (_point(ev, x['ref']) for x in arg)
            if min(math.hypot(a[0] - b[0], a[1] - b[1]), math.hypot(c[0] - b[0], c[1] - b[1])) <= tol.decide_length:
                raise rel._Inconclusive('coincident_points')
            refs.append(_convex_angle(a, b, c))
        else:
            refs.append(float(_value(ev, arg['ref'])['size']))
        return {'ref': len(refs) - 1}
    if 'op' in node:
        return {'op': node['op'], 'args': [_to_ast(doc, ev, c, refs, tol) for c in node['args']]}
    return {'fn': node['fn'], 'args': [_to_ast(doc, ev, c, refs, tol) for c in node['args']]}


def _expr_value(doc, ev, node, tol) -> float:
    refs: list = []
    ast = _to_ast(doc, ev, node, refs, tol)
    try:
        return expr_evaluate(ast, refs)
    except (ExprError, ZeroDivisionError, OverflowError, ValueError) as exc:
        raise rel._Inconclusive('expression') from exc


def _equal_value(doc, ev, left, right, tol) -> float:
    lv = _expr_value(doc, ev, left, tol)
    rv = _expr_value(doc, ev, right, tol)
    units = {_unit_of(left), _unit_of(right)}
    factor = 1.0 if 'length' in units else tol.scale
    return abs(lv - rv) * factor


def _measure_check(doc, ev, check, tol) -> float:
    name = check['predicate']
    if name == 'equal_value':
        return _equal_value(doc, ev, check['args'][0], check['args'][1], tol)
    fn = rel.PREDICATES[name]
    items = [_item(doc, ev, a, tol, as_segment=(name == 'congruent')) for a in check['args']]
    return float(fn(items, tol))


def measure_statement(doc, statement, ev) -> tuple:
    """``(status, error | None, detail | None)`` of a statement in the
    evaluated document ``ev``: ``passed``, ``failed`` or ``inconclusive`` by
    ``tol.check``, ``unsupported`` for argument types a predicate does not
    take. ``ne`` turns ``passed`` and ``failed`` round (``not``)."""
    tol = ev.tolerances
    checks = statement_checks(doc, statement)
    negate = checks[0]['predicate'] == 'not'
    check = checks[0]['args'][0] if negate else checks[0]
    try:
        error = _measure_check(doc, ev, check, tol)
    except _Undefined as exc:
        return 'inconclusive', None, {'reason': 'undefined', 'elementIds': exc.ids}
    except rel._Unsupported as exc:
        return 'unsupported', None, {'reason': exc.reason}
    except rel._Inconclusive as exc:
        return 'inconclusive', None, {'reason': exc.reason}
    status = classify(error, tol)
    if negate:
        status = {'passed': 'failed', 'failed': 'passed'}.get(status, status)
    return status, error, None


def mark_statement(doc, op_id):
    """The statement a mark operation asserts, or ``None``:
    ``mark.right_angle(a, vertex, b)`` — ``vertex a ⟂ vertex b``;
    ``mark.equal_segments`` — the lengths of the first two segments;
    ``mark.equal_angles`` — the sizes of the first two angles (a mark of more
    targets compares the first with each, see :func:`mark_statements`)."""
    items = mark_statements(doc, op_id)
    return items[0] if items else None


def mark_statements(doc, op_id) -> list:
    from ..document import iter_refs
    op = doc.operations.get(op_id)
    if op is None:
        return []
    args = op.get('args') or {}
    if op['op'] == 'mark.right_angle':
        a, v, b = (next(iter(iter_refs(args.get(s) or {})), None) for s in ('a', 'vertex', 'b'))
        if not (a and v and b):
            return []
        return [{'kind': 'perpendicular', 'a': {'pair': [v, a]}, 'b': {'pair': [v, b]}}]
    if op['op'] in ('mark.equal_segments', 'mark.equal_angles'):
        slot = 'segments' if op['op'] == 'mark.equal_segments' else 'angles'
        targets = list(iter_refs(args.get(slot) or {}))
        leaf = 'len' if slot == 'segments' else 'angle'
        return [{'kind': 'eq', 'left': {leaf: {'ref': targets[0]}}, 'right': {leaf: {'ref': t}}}
                for t in targets[1:]]
    return []


RELATION_ORDER = ('coincident', 'incident', 'parallel', 'perpendicular', 'tangent', 'congruent')


def relation(doc, a, b, ev) -> list:
    """``check.relation``: the predicates of :data:`RELATION_ORDER` that hold
    (``passed``) for the objects ``a`` and ``b`` (element IDs or pairs) in
    ``ev``, in that order."""
    out = []
    for name in RELATION_ORDER:
        if name == 'incident':
            statement = {'kind': 'on', 'point': _obj(a), 'object': _obj(b)}
            if not (isinstance(a, str) and doc.elements.get(a, {}).get('type') == 'point'):
                statement = {'kind': 'on', 'point': _obj(b), 'object': _obj(a)}
        elif name == 'coincident':
            statement = {'kind': 'coincident', 'points': [_obj(a), _obj(b)]}
        else:
            statement = {'kind': name, 'a': _obj(a), 'b': _obj(b)}
        if statement_problems(statement, doc):
            continue
        if measure_statement(doc, statement, ev)[0] == 'passed':
            out.append(name)
    return out


def _obj(arg):
    return {'ref': arg} if isinstance(arg, str) else {'pair': list(arg['pair'] if isinstance(arg, dict) else arg)}
