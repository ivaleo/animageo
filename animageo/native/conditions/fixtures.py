"""Fixtures of stage 2 of plan L3 (§3.8, §8): ``animageo-recipes/v1``,
``animageo-general/v1`` and ``animageo-marks/v1`` in
``animageo/native/parity/v1/{recipes,general,marks}``.

The documents are built here; expectations are what this library gives.
Documents after an edit are written as they are, with the default IDs of
the library (``c<n>``, ``op_<c>_<k>``, ``<c>_<name>``; marks ``op_mark_<source>``,
``mark_<source>``, helpers ``aux_<source>``, ``_2``… on a clash) — part of
the contract (docs/native/conditions.md §7); numbers compare with
``tol.parity``.

- recipes: ``{name, document, condition, receiver, expect: {refusal, document,
  values, shift, check}}``; a release case has ``release`` (a condition ID)
  instead of ``condition``; a shape case has ``shape: {polygon, shape}`` and
  ``expect.conditions`` (``shape_conditions``) — the document after applying
  them in order;
- general: ``{name, document, check, seed, trials, statement?, expect: {status,
  passed, failed, undefined, inconclusive, counterexample, seed}}``;
  ``check`` is a condition ID, a mark operation ID, or the ID of
  ``statement``; ``seed`` ``null`` — the seed of the check; seeds are
  decimal strings (64-bit, beyond the 2⁵³ of JSON numbers);
- marks: ``{name, document, sources, expect: {operations, warnings}}``.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from ..canonical import canonical_json
from ..registry import REGISTRY_VERSION

__all__ = ['RECIPES_FORMAT', 'GENERAL_FORMAT', 'MARKS_FORMAT', 'DEFAULT_ROOT', 'build_fixtures',
           'write_fixtures', 'check_fixtures', 'verify_fixtures', 'replay_case']

RECIPES_FORMAT = 'animageo-recipes/v1'
GENERAL_FORMAT = 'animageo-general/v1'
MARKS_FORMAT = 'animageo-marks/v1'
DEFAULT_ROOT = Path(__file__).resolve().parent.parent / 'parity' / 'v1'
BOUNDS = [-6, -4, 6, 4]
TRIALS = 50


# ── documents ────────────────────────────────────────────────────────────

class _Doc:
    def __init__(self, doc_id):
        self.doc = {'format': 'animageo-construction/v1', 'documentId': doc_id,
                    'operationRegistryVersion': REGISTRY_VERSION, 'operations': {}, 'elements': {}, 'inputs': {},
                    'viewDefaults': {'bounds': list(BOUNDS)}}

    def op(self, op_id, name, args, outputs):
        self.doc['operations'][op_id] = {'id': op_id, 'op': name, 'args': args,
                                         'outputs': [{'slot': s, 'elementId': e} for s, e, _t in outputs]}
        for slot, el_id, type_ in outputs:
            self.doc['elements'][el_id] = {'id': el_id, 'type': type_, 'displayName': el_id,
                                           'producer': {'operationId': op_id, 'slot': slot}}
        return self

    def free(self, el_id, x, y):
        self.op('op_' + el_id, 'point.free', {}, [('point', el_id, 'point')])
        self.doc['inputs'][el_id] = {'kind': 'point', 'value': [round(x, 6), round(y, 6)]}
        return self

    def two(self, op, el_id, a, b, type_, slots=('a', 'b'), out='segment'):
        return self.op('op_' + el_id, op, {slots[0]: _r(a), slots[1]: _r(b)}, [(out, el_id, type_)])

    def number(self, el_id, value, lo, hi):
        self.op('op_' + el_id, 'number.free', {'min': {'kind': 'number', 'value': lo},
                                               'max': {'kind': 'number', 'value': hi}}, [('number', el_id, 'number')])
        self.doc['inputs'][el_id] = {'kind': 'number', 'value': value}
        return self


def _r(el_id):
    return {'kind': 'ref', 'elementId': el_id}


def _base(v: int) -> dict:
    d = _Doc(f'recipes-{v}')
    d.free('A', -3 + 0.3 * v, -2 + 0.1 * v).free('B', 3 - 0.2 * v, -2 + 0.15 * v)
    d.free('C', 0.5 + 0.25 * v, 2 - 0.1 * v).free('D', 1 - 0.3 * v, -0.5 + 0.2 * v)
    d.two('circle.center_point', 'k', 'A', 'B', 'circle', slots=('center', 'through'), out='circle')
    d.number('n', 2.0, 1, 4)
    d.free('O', 4 - 0.1 * v, 2.5 - 0.05 * v)
    d.op('op_w', 'circle.center_radius', {'center': _r('O'), 'radius': {'kind': 'number', 'value': 0.8}},
         [('circle', 'w', 'circle')])
    return d.doc


def P(x):
    return {'ref': x}


def _pair(p, q):
    return {'pair': [p, q]}


def _len(p, q):
    return {'len': _pair(p, q)}


def _angle(a, b, c):
    return {'angle': [P(a), P(b), P(c)]}


RECIPE_CASES = [
    ('on_object', {'kind': 'on', 'point': P('C'), 'object': P('k')}),
    ('on_line', {'kind': 'on', 'point': P('C'), 'object': _pair('A', 'B')}),
    ('length.value', {'kind': 'eq', 'left': _len('A', 'C'), 'right': {'num': 5}}),
    ('length.value-ref', {'kind': 'eq', 'left': {'ref': 'n'}, 'right': _len('C', 'A')}),
    ('equal_length.vertex', {'kind': 'eq', 'left': _len('A', 'B'), 'right': _len('A', 'C')}),
    ('equal_length.free', {'kind': 'eq', 'left': _len('A', 'B'), 'right': _len('C', 'D')}),
    ('equal_length.apex', {'kind': 'eq', 'left': _len('D', 'A'), 'right': _len('D', 'B')}),
    ('parallel', {'kind': 'parallel', 'a': _pair('A', 'B'), 'b': _pair('C', 'D')}),
    ('perpendicular', {'kind': 'perpendicular', 'a': _pair('D', 'C'), 'b': _pair('B', 'A')}),
    ('right_angle.vertex', {'kind': 'eq', 'left': _angle('A', 'D', 'B'), 'right': {'deg': 90}}),
    ('right_angle.side', {'kind': 'eq', 'left': _angle('B', 'A', 'D'), 'right': {'deg': 90}}),
    ('angle.value', {'kind': 'eq', 'left': _angle('B', 'A', 'D'), 'right': {'deg': 40}}),
    ('angle.value-reversed', {'kind': 'eq', 'left': {'deg': 125}, 'right': _angle('D', 'A', 'B')}),
    ('angle.equal', {'kind': 'eq', 'left': _angle('B', 'A', 'C'), 'right': _angle('A', 'B', 'D')}),
    ('tangent', {'kind': 'tangent', 'a': _pair('C', 'D'), 'b': P('w')}),
]


def _point(ev, el_id):
    state = ev.elements.get(el_id)
    if state is None or state['state'] != 'defined':
        return None
    v = state['value']
    return [v['x'], v['y']] if isinstance(v, dict) else [v[0], v[1]]


def _apply_case(name, doc, condition, receiver):
    from .. import evaluate
    from ..sampling import check_general
    from .apply import apply_condition
    r = apply_condition(doc, condition, receiver=receiver)
    case = {'name': name, 'document': copy.deepcopy(doc.data if hasattr(doc, 'data') else doc),
            'condition': condition, 'receiver': receiver}
    if r.refusal is not None:
        case['expect'] = {'refusal': {'code': r.refusal.code, 'options': r.refusal.options}}
        return case, None
    ev = evaluate(r.document)
    rec = r.condition['receiver']
    case['expect'] = {'refusal': None, 'document': copy.deepcopy(r.document.data),
                      'values': {rec: _point(ev, rec)}, 'shift': r.effects['shift'],
                      'check': check_general(r.document, [r.condition['id']], trials=TRIALS)[r.condition['id']]['status']}
    return case, r


def _recipe_fixtures() -> dict:
    from .. import evaluate
    from .apply import SHAPES, release_condition, shape_conditions
    by_recipe = []
    releases = []
    for name, st in RECIPE_CASES:
        for v in range(5):
            case, r = _apply_case(f'{name}-{v}', _base(v), {'statement': st, 'mode': 'construct', 'source': 'panel'},
                                  None)
            by_recipe.append(case)
            if r is not None and v == 0:
                released = release_condition(r.document, r.condition['id'], ev=evaluate(r.document))
                rec = r.condition['receiver']
                releases.append({'name': f'release-{name}', 'document': copy.deepcopy(r.document.data),
                                 'release': r.condition['id'], 'withValues': True,
                                 'expect': {'document': copy.deepcopy(released.document.data),
                                            'values': {rec: _point(evaluate(released.document), rec)},
                                            'warnings': released.effects['warnings']}})
    # refusals
    refusals = []
    ref = _Doc('refusals')
    ref.free('A', -3, -2).free('B', 3, -2).free('C', 0.5, 2).free('E', -1, 3)
    ref.two('point.midpoint', 'M', 'A', 'B', 'point', out='point')
    rdoc = ref.doc
    unsupported = [
        {'kind': 'collinear', 'points': [P('A'), P('B'), P('C')]},
        {'kind': 'concyclic', 'points': [P('A'), P('B'), P('C'), P('E')]},
        {'kind': 'ne', 'left': _len('A', 'C'), 'right': _len('B', 'C')},
        {'kind': 'congruent', 'a': _pair('A', 'C'), 'b': _pair('B', 'E')},
        {'kind': 'eq', 'left': {'op': '+', 'args': [_len('A', 'C'), _len('B', 'C')]}, 'right': {'num': 9}},
    ]
    for i, st in enumerate(unsupported):
        refusals.append(_apply_case(f'unsupported-{i}', rdoc, {'statement': st, 'mode': 'construct'}, None)[0])
    for i, (st, rec) in enumerate([({'kind': 'eq', 'left': _len('A', 'M'), 'right': {'num': 2}}, 'M'),
                                   ({'kind': 'on', 'point': P('M'), 'object': _pair('C', 'E')}, 'M'),
                                   ({'kind': 'eq', 'left': _len('C', 'M'), 'right': _len('C', 'E')}, 'M')]):
        refusals.append(_apply_case(f'receiver_not_free-{i}', rdoc, {'statement': st, 'mode': 'construct'}, rec)[0])
    for i, st in enumerate([{'kind': 'eq', 'left': _len('A', 'M'), 'right': _len('M', 'B')},
                            {'kind': 'eq', 'left': _len('A', 'M'), 'right': {'num': 2}},
                            {'kind': 'parallel', 'a': _pair('A', 'M'), 'b': _pair('C', 'E')}]):
        refusals.append(_apply_case(f'receiver_is_ancestor-{i}', rdoc, {'statement': st, 'mode': 'construct'},
                                    'A')[0])
    from .apply import apply_condition
    two = []
    first = {'kind': 'eq', 'left': _len('A', 'C'), 'right': {'num': 4}}
    seconds = [{'kind': 'eq', 'left': _len('B', 'C'), 'right': {'num': 4}},
               {'kind': 'on', 'point': P('C'), 'object': _pair('E', 'M')},
               {'kind': 'parallel', 'a': _pair('A', 'E'), 'b': _pair('M', 'C')},
               {'kind': 'eq', 'left': _len('E', 'C'), 'right': _len('E', 'A')},
               {'kind': 'eq', 'left': _angle('B', 'M', 'C'), 'right': {'deg': 70}},
               {'kind': 'eq', 'left': _len('B', 'C'), 'right': {'num': 6}}]
    d1 = apply_condition(rdoc, {'statement': first, 'mode': 'construct'}, receiver='C').document
    for i, st in enumerate(seconds):
        case, r = _apply_case(f'two-{i}', d1, {'statement': st, 'mode': 'construct'}, 'C')
        two.append(case)
    d2 = apply_condition(d1, {'statement': seconds[0], 'mode': 'construct'}, receiver='C').document
    for i, st in enumerate(seconds[1:4]):
        refusals.append(_apply_case(f'too_many_conditions-{i}', d2, {'statement': st, 'mode': 'construct'}, 'C')[0])
    for i, st in enumerate([{'kind': 'eq', 'left': _len('B', 'C'), 'right': {'num': 0.5}},
                            {'kind': 'eq', 'left': _len('E', 'C'), 'right': {'num': 0.2}},
                            {'kind': 'eq', 'left': _len('B', 'C'), 'right': {'num': 11}}]):
        refusals.append(_apply_case(f'no_intersection_now-{i}', d1, {'statement': st, 'mode': 'construct'}, 'C')[0])
    # releases without values and of one of two
    r1 = apply_condition(_base(0), {'statement': RECIPE_CASES[2][1], 'mode': 'construct'})
    back = release_condition(r1.document, r1.condition['id'])
    releases.append({'name': 'release-restored-origin', 'document': copy.deepcopy(r1.document.data),
                     'release': r1.condition['id'], 'withValues': False,
                     'expect': {'document': copy.deepcopy(back.document.data), 'values': {},
                                'warnings': back.effects['warnings']}})
    for cid in ('c1', 'c2'):
        back = release_condition(d2, cid, ev=evaluate(d2))
        releases.append({'name': f'release-one-of-two-{cid}', 'document': copy.deepcopy(d2.data), 'release': cid,
                         'withValues': True,
                         'expect': {'document': copy.deepcopy(back.document.data),
                                    'values': {'C': _point(evaluate(back.document), 'C')},
                                    'warnings': back.effects['warnings']}})
    shapes = []
    for shape in sorted(SHAPES):
        n = SHAPES[shape][0]
        for v in range(2):
            d = _Doc(f'shape-{shape}-{v}')
            pts = [('A', -3 + 0.4 * v, -2), ('B', 3, -1.5 + 0.3 * v), ('C', 2.5 - 0.2 * v, 2.2),
                   ('D', -2.2, 1.8 - 0.3 * v)][:n]
            for name, x, y in pts:
                d.free(name, x, y)
            d.op('op_T', 'polygon.by_points', {'vertices': {'kind': 'list', 'items': [_r(p[0]) for p in pts]}},
                 [('polygon', 'T', 'polygon')])
            doc = d.doc
            items = shape_conditions(doc, 'T', shape)
            cur = doc
            for item in items:
                cur = apply_condition(cur, {'statement': item['statement'], 'mode': 'construct', 'source': 'shape',
                                            'shapeId': 'T'}, receiver=item['receiver']).document
            from ..sampling import check_general
            statuses = sorted({v_['status'] for v_ in check_general(cur, trials=TRIALS).values()})
            shapes.append({'name': f'shape-{shape}-{v}', 'document': doc, 'shape': {'polygon': 'T', 'shape': shape},
                           'expect': {'conditions': items, 'document': copy.deepcopy(cur.data if hasattr(cur, 'data')
                                                                                      else cur),
                                      'check': statuses[0] if len(statuses) == 1 else 'mixed'}})
    return {'recipes': by_recipe, 'refusals': refusals, 'two': two, 'release': releases, 'shapes': shapes}


def _seed_text(seed):
    """A 64-bit seed is written as a decimal string (JSON numbers stop at 2⁵³)."""
    return None if seed is None else str(seed)


def _general_expect(result) -> dict:
    out = {k: result[k] for k in ('status', 'passed', 'failed', 'undefined', 'inconclusive', 'counterexample')}
    out['seed'] = _seed_text(result['seed'])
    return out


def _general_fixtures() -> list:
    from ..sampling import check_general
    from .apply import apply_condition
    cases = []

    def add(name, doc, check, statement=None, seed=None, trials=TRIALS):
        target = [(check, statement)] if statement is not None else [check]
        result = check_general(doc, target, seed=seed, trials=trials)[check]
        case = {'name': name, 'document': copy.deepcopy(doc.data if hasattr(doc, 'data') else doc),
                'check': check, 'seed': _seed_text(seed), 'trials': trials}
        if statement is not None:
            case['statement'] = statement
        case['expect'] = _general_expect(result)
        cases.append(case)

    for name, st in RECIPE_CASES:
        r = apply_condition(_base(1), {'statement': st, 'mode': 'construct'})
        if r.refusal is None:
            add(f'recipe-{name}', r.document, r.condition['id'])
    tri = _Doc('general')
    tri.free('A', -3, -2).free('B', 3, -2).free('C', 0, 2)
    tri.two('point.midpoint', 'M', 'A', 'B', 'point', out='point')
    tri.number('k', 0.5, -1.0, 1.0)
    tri.op('op_c', 'circle.center_radius', {'center': _r('C'), 'radius': _r('k')}, [('circle', 'c', 'circle')])
    tri.op('op_T', 'point.on_path', {'path': _r('c')}, [('point', 'T', 'point')])
    tri.doc['inputs']['T'] = {'kind': 'pathParameter', 'value': 1.0}
    doc = tri.doc
    false_now = [
        ('iso', {'kind': 'eq', 'left': _len('A', 'C'), 'right': _len('B', 'C')}),
        ('right', {'kind': 'perpendicular', 'a': _pair('C', 'M'), 'b': _pair('A', 'B')}),
        ('par', {'kind': 'parallel', 'a': _pair('A', 'B'), 'b': _pair('M', 'C')}),
        ('len3', {'kind': 'eq', 'left': _len('A', 'M'), 'right': {'num': 3}}),
        ('angle', {'kind': 'eq', 'left': _angle('A', 'C', 'B'), 'right': _angle('C', 'A', 'B')}),
    ]
    for check, st in false_now:
        add(f'failed-{check}', doc, check, st)
    true_always = [
        ('half', {'kind': 'eq', 'left': _len('A', 'M'), 'right': _len('M', 'B')}),
        ('on', {'kind': 'collinear', 'points': [P('A'), P('M'), P('B')]}),
        ('ne', {'kind': 'ne', 'left': _len('A', 'B'), 'right': {'num': 0}}),
    ]
    for check, st in true_always:
        add(f'passed-{check}', doc, check, st)
    add('inconclusive-on-circle', doc, 'onc', {'kind': 'on', 'point': P('T'), 'object': P('c')})
    add('level1-failed', doc, 'par1', {'kind': 'parallel', 'a': _pair('A', 'B'), 'b': _pair('A', 'C')})
    for seed in (0, 1, 2 ** 63, 12345):
        add(f'seed-{seed}', doc, 'iso', false_now[0][1], seed=seed)
    for trials in (1, 10, 100):
        add(f'trials-{trials}', doc, 'iso', false_now[0][1], trials=trials)
    return cases


def _marks_fixtures() -> list:
    from .marks import add_auto_marks
    cases = []
    for v in range(3):
        d = _Doc(f'marks-{v}')
        d.free('A', -3 + 0.5 * v, -2).free('B', 3, -2 + 0.2 * v).free('C', 0.5 - 0.6 * v, 2)
        d.two('segment.by_points', 's', 'A', 'B', 'segment')
        d.op('op_h', 'triangle.altitude', {'vertex': _r('C'), 'side': _r('s')},
             [('altitude', 'h', 'segment'), ('foot', 'H', 'point')])
        d.op('op_P', 'point.projection', {'point': _r('C'), 'base': _r('s')}, [('foot', 'F', 'point')])
        d.two('segment.by_points', 'cf', 'C', 'F', 'segment')
        d.op('op_p', 'line.perpendicular', {'point': _r('C'), 'base': _r('s')}, [('line', 'p', 'line')])
        d.op('op_X', 'intersect.line_line', {'first': _r('p'), 'second': _r('s')}, [('point', 'X', 'point')])
        d.op('op_k', 'circle.diameter', {'a': _r('A'), 'b': _r('B')}, [('circle', 'k', 'circle'),
                                                                         ('center', 'O', 'point')])
        d.op('op_Q', 'point.on_path', {'path': _r('k')}, [('point', 'Q', 'point')])
        d.doc['inputs']['Q'] = {'kind': 'pathParameter', 'value': 1.0 + 0.5 * v}
        d.free('Z', -4, 3 - 0.3 * v)
        d.op('op_t', 'line.tangents_from_point', {'point': _r('Z'), 'circle': _r('k')},
             [('tangent.1', 't1', 'line'), ('tangent.2', 't2', 'line'), ('touch.1', 'T1', 'point'),
              ('touch.2', 'T2', 'point')])
        d.two('point.midpoint', 'M', 'A', 'B', 'point', out='point')
        d.op('op_m', 'triangle.median', {'vertex': _r('C'), 'side': _r('s')},
             [('median', 'm', 'segment'), ('midpoint', 'K', 'point')])
        d.op('op_b', 'triangle.bisector', {'vertex': _r('C'), 'side': _r('s')},
             [('bisector', 'l', 'segment'), ('foot', 'L', 'point')])
        d.op('op_g', 'line.angle_bisector', {'a': _r('A'), 'vertex': _r('C'), 'b': _r('B')}, [('line', 'g', 'line')])
        doc = d.doc
        for source in ('op_h', 'op_P', 'op_p', 'op_k', 'op_t', 'op_M', 'op_m', 'op_b', 'op_g'):
            r = add_auto_marks(doc, [source])
            cases.append({'name': f'{source[3:]}-{v}', 'document': doc, 'sources': [source],
                          'expect': {'operations': r.operations, 'warnings': r.warnings}})
        r = add_auto_marks(doc, ['op_M', 'op_m', 'op_b', 'op_g', 'op_h'])
        cases.append({'name': f'classes-{v}', 'document': doc, 'sources': ['op_M', 'op_m', 'op_b', 'op_g', 'op_h'],
                      'expect': {'operations': r.operations, 'warnings': r.warnings}})
        suppressed = copy.deepcopy(doc)
        suppressed['suppressedMarks'] = [{'source': 'op_M', 'kind': 'equal_segments'}]
        r = add_auto_marks(suppressed, ['op_M', 'op_h'])
        cases.append({'name': f'suppressed-{v}', 'document': suppressed, 'sources': ['op_M', 'op_h'],
                      'expect': {'operations': r.operations, 'warnings': r.warnings}})
    # classes exhausted
    d = _Doc('marks-classes')
    for i, (x, length) in enumerate([(-5, 1), (-3, 1.5), (-1, 2), (1, 2.5)]):
        d.free(f'P{i}', x, -3).free(f'Q{i}', x, -3 + length)
        d.two('point.midpoint', f'M{i}', f'P{i}', f'Q{i}', 'point', out='point')
    sources = [f'op_M{i}' for i in range(4)]
    r = add_auto_marks(d.doc, sources)
    cases.append({'name': 'classes-exhausted', 'document': d.doc, 'sources': sources,
                  'expect': {'operations': r.operations, 'warnings': r.warnings}})
    return cases


SCENE_SHAPES = ('right_triangle', 'equilateral', 'parallelogram', 'square')


def _moved(doc, el_id, dx, dy):
    x, y = doc['inputs'][el_id]['value']
    return {el_id: {'kind': 'point', 'value': [round(x + dx, 6), round(y + dy, 6)]}}


def build_scenes() -> dict:
    """``{scene id: animageo-parity/v1 scene}``: a document after each recipe
    (``recipe_*``, base 0, the first case of the recipe) and after four
    shapes (``shape_*``), with the free inputs moved."""
    from .apply import apply_condition, shape_conditions
    out = {}
    seen = set()
    for name, st in RECIPE_CASES:
        recipe = name.split('-')[0]
        if recipe in seen:
            continue
        seen.add(recipe)
        r = apply_condition(_base(0), {'statement': st, 'mode': 'construct', 'source': 'panel'})
        doc = copy.deepcopy(r.document.data)
        sid = 'recipe_' + recipe.replace('.', '_')
        doc['documentId'] = sid
        rec = r.condition['receiver']
        cases = [{'name': 'now'}, {'name': 'move_a', 'inputs': _moved(doc, 'A', 0.4, 0.3)},
                 {'name': 'move_b', 'inputs': _moved(doc, 'B', -0.3, 0.4)}]
        value = doc['inputs'].get(rec)
        if value is not None and value['kind'] == 'pathParameter':
            moved = dict(value, value=round(value['value'] + 0.3, 6))
            cases.append({'name': 'move_receiver', 'inputs': {rec: moved}})
        out[sid] = {'format': 'animageo-parity/v1', 'id': sid, 'document': doc, 'cases': cases}
    for shape in SCENE_SHAPES:
        from .apply import SHAPES
        n = SHAPES[shape][0]
        d = _Doc('shape_' + shape)
        pts = [('A', -3, -2), ('B', 3, -1.5), ('C', 2.5, 2.2), ('D', -2.2, 1.8)][:n]
        for nm, x, y in pts:
            d.free(nm, x, y)
        d.op('op_T', 'polygon.by_points', {'vertices': {'kind': 'list', 'items': [_r(p[0]) for p in pts]}},
             [('polygon', 'T', 'polygon')])
        cur = d.doc
        for item in shape_conditions(cur, 'T', shape):
            cur = apply_condition(cur, {'statement': item['statement'], 'mode': 'construct', 'source': 'shape',
                                        'shapeId': 'T'}, receiver=item['receiver']).document
        doc = copy.deepcopy(cur.data)
        sid = 'shape_' + shape
        out[sid] = {'format': 'animageo-parity/v1', 'id': sid, 'document': doc,
                    'cases': [{'name': 'now'}, {'name': 'move_a', 'inputs': _moved(doc, 'A', 0.4, 0.3)},
                              {'name': 'move_b', 'inputs': _moved(doc, 'B', -0.3, 0.4)}]}
    return out


def build_fixtures() -> dict:
    """``{relative path: fixture}`` of the three formats."""
    gen = f'animageo {_version()}'
    out = {}
    for fid, cases in _recipe_fixtures().items():
        out[f'recipes/{fid}.json'] = {'format': RECIPES_FORMAT, 'id': fid, 'registry': REGISTRY_VERSION,
                                      'generatedBy': gen, 'cases': cases}
    out['general/general.json'] = {'format': GENERAL_FORMAT, 'id': 'general', 'registry': REGISTRY_VERSION,
                                   'generatedBy': gen, 'cases': _general_fixtures()}
    out['marks/marks.json'] = {'format': MARKS_FORMAT, 'id': 'marks', 'registry': REGISTRY_VERSION,
                               'generatedBy': gen, 'cases': _marks_fixtures()}
    for sid, scene in build_scenes().items():
        out[f'scenes/{sid}.json'] = scene
    return out


def _version() -> str:
    from ... import __version__
    return __version__


def _text(data) -> str:
    return json.dumps(json.loads(canonical_json(data)), ensure_ascii=False, indent=1) + '\n'


def write_fixtures(root=DEFAULT_ROOT) -> list:
    root = Path(root)
    paths = []
    for rel, data in build_fixtures().items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_text(data), encoding='utf-8')
        paths.append(path)
    return paths


def check_fixtures(root=DEFAULT_ROOT) -> list:
    """Paths whose content differs from a fresh build (missing included)."""
    root = Path(root)
    problems = []
    for rel, data in build_fixtures().items():
        path = root / rel
        if not path.exists() or path.read_text(encoding='utf-8') != _text(data):
            problems.append(str(path))
    return problems


# ── replay (what the web does with a fixture) ────────────────────────────

def _same(a, b) -> bool:
    return canonical_json(a) == canonical_json(b)


def replay_case(fmt: str, case: dict) -> dict:
    """The ``expect`` of ``case`` recomputed from its inputs alone."""
    from .. import evaluate
    from ..sampling import check_general
    from .apply import apply_condition, release_condition, shape_conditions
    from .marks import add_auto_marks
    if fmt == RECIPES_FORMAT:
        if 'release' in case:
            doc = case['document']
            r = release_condition(doc, case['release'], ev=evaluate(doc) if case.get('withValues') else None)
            values = {k: _point(evaluate(r.document), k) for k in case['expect']['values']}
            return {'document': r.document.data, 'values': values, 'warnings': r.effects['warnings']}
        if 'shape' in case:
            items = shape_conditions(case['document'], case['shape']['polygon'], case['shape']['shape'])
            cur = case['document']
            for item in items:
                cur = apply_condition(cur, {'statement': item['statement'], 'mode': 'construct', 'source': 'shape',
                                            'shapeId': case['shape']['polygon']}, receiver=item['receiver']).document
            statuses = sorted({v['status'] for v in check_general(cur, trials=TRIALS).values()})
            return {'conditions': items, 'document': cur.data if hasattr(cur, 'data') else cur,
                    'check': statuses[0] if len(statuses) == 1 else 'mixed'}
        r = apply_condition(case['document'], case['condition'], receiver=case['receiver'])
        if r.refusal is not None:
            return {'refusal': {'code': r.refusal.code, 'options': r.refusal.options}}
        ev = evaluate(r.document)
        rec = r.condition['receiver']
        return {'refusal': None, 'document': r.document.data, 'values': {rec: _point(ev, rec)},
                'shift': r.effects['shift'],
                'check': check_general(r.document, [r.condition['id']], trials=TRIALS)[r.condition['id']]['status']}
    if fmt == GENERAL_FORMAT:
        target = [(case['check'], case['statement'])] if 'statement' in case else [case['check']]
        seed = int(case['seed']) if case['seed'] is not None else None
        result = check_general(case['document'], target, seed=seed, trials=case['trials'])[case['check']]
        return _general_expect(result)
    if fmt == MARKS_FORMAT:
        r = add_auto_marks(case['document'], case['sources'])
        return {'operations': r.operations, 'warnings': r.warnings}
    raise ValueError(f'unknown format {fmt!r}')


def verify_fixtures(root=DEFAULT_ROOT) -> tuple:
    """``(files, cases, mismatches)``: every case of the three formats under
    ``root`` replayed from its inputs and compared with ``expect``."""
    root = Path(root)
    files = cases = 0
    mismatches = []
    for sub in ('recipes', 'general', 'marks'):
        for path in sorted((root / sub).glob('*.json')):
            data = json.loads(path.read_text(encoding='utf-8'))
            files += 1
            for case in data['cases']:
                cases += 1
                got = replay_case(data['format'], case)
                if not _same(got, case['expect']):
                    mismatches.append(f"{path.name}: {case['name']}")
    return files, cases, mismatches
