"""Fixtures of :func:`~animageo.native.drag` (1.12.0): ``animageo-drag-parity/v1``
in ``animageo/native/parity/v1/drag``.

One file per case: ``{format, id, generatedBy, text, doc, inputs, element,
target, expect: {status, inputs}}`` — ``expect`` is ``native.drag(doc,
inputs, element, target)``. The status compares exactly; on ``ok`` and
``clamped`` the inputs compare by key, ``kind``, ``branch`` and ``pathKind`` exactly and
every number within ``1e-9`` (absolute; world units for a point, parameter
units for a path parameter); on ``no_convergence`` and ``singular``
``expect.inputs`` is ``inputs`` and the call returns that very object.
The numbers of a success are written rounded to 10 digits after the point.
Each document declares the lowest registry version its operations need.
The cases: a free point, a point on a path without a hint (projected,
stopped at an end), the fourth vertex of ``polygon.parallelogram`` through
``C``, a vertex of a triangle reflected by ``transform.reflect_point``
through the original, a translated point, a point built from a point on a
circle (one parameter: the nearest point it can reach), the same on a
segment stopped at its end (``clamped``), a midpoint through both ends (the
least change), an incenter moved through a vertex (several steps), and the
refusals: an incenter outside its reach (``no_convergence``) and the foot of
a perpendicular moved through the point it drops from (``singular``); a point
on a graph (``point.on_function``) without a hint (the x of the target, then
stopped at the end of the domain) and a point reflected from it through its x;
registry 1.9: a point on an ellipse, a hyperbola (the nearest branch) and a
parabola, a point on a graph by ``point.on_path`` (the nearest point across a
gap, stopped at the end of the domain), and a midpoint through a point on an
ellipse (the parameter wraps) and on a hyperbola (the branch stays).
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

__all__ = ['DRAG_PARITY_FORMAT', 'DEFAULT_DIR', 'TOLERANCE', 'build_fixtures', 'write_fixtures',
           'check_fixtures', 'verify_fixture', 'verify_fixtures']

DRAG_PARITY_FORMAT = 'animageo-drag-parity/v1'
DEFAULT_DIR = Path(__file__).resolve().parent / 'parity' / 'v1' / 'drag'
TOLERANCE = 1e-9
DIGITS = 10
REFUSALS = ('no_convergence', 'singular')


def _ref(el_id):
    return {'kind': 'ref', 'elementId': el_id}


def _pt(x, y):
    return {'kind': 'point', 'value': [x, y]}


def _par(t):
    return {'kind': 'pathParameter', 'value': t}


def _version(text):
    major, minor = text.split('.')
    return int(major), int(minor)


class _Doc:
    def __init__(self, doc_id, bounds=(-10, -10, 10, 10)):
        self.doc = {'format': 'animageo-construction/v1', 'documentId': doc_id,
                    'operationRegistryVersion': '1.0', 'operations': {}, 'elements': {},
                    'inputs': {}, 'viewDefaults': {'bounds': list(bounds)}}

    def op(self, name, args, outputs, op_id=None):
        from .registry import registry
        since = registry().get(name)['since']
        if _version(since) > _version(self.doc['operationRegistryVersion']):
            self.doc['operationRegistryVersion'] = since
        op_id = op_id or 'op_' + outputs[0][1]
        self.doc['operations'][op_id] = {'id': op_id, 'op': name, 'args': args,
                                         'outputs': [{'slot': s, 'elementId': e} for s, e, _t in outputs]}
        for slot, el_id, type_ in outputs:
            self.doc['elements'][el_id] = {'id': el_id, 'type': type_, 'displayName': el_id,
                                           'producer': {'operationId': op_id, 'slot': slot}}
        return self

    def free(self, el_id, x, y):
        self.op('point.free', {}, [('point', el_id, 'point')])
        self.doc['inputs'][el_id] = _pt(x, y)
        return self

    def on_path(self, el_id, path, t, **extra):
        self.op('point.on_path', {'path': _ref(path)}, [('point', el_id, 'point')])
        self.doc['inputs'][el_id] = dict(_par(t), **extra)
        return self

    def conic(self, name, el_id, **refs):
        """A conic; registry 1.9 for a point on it (the family ``path``)."""
        self.args(name, el_id, 'conic', **refs)
        if _version(self.doc['operationRegistryVersion']) < (1, 9):
            self.doc['operationRegistryVersion'] = '1.9'
        return self

    def args(self, name, el_id, type_, slot=None, **refs):
        return self.op(name, {k: _ref(v) for k, v in refs.items()}, [(slot or type_, el_id, type_)])

    def via(self, el_id, *ids):
        self.doc.setdefault('appearance', {}).setdefault(el_id, {})['drag'] = \
            {'via': ids[0] if len(ids) == 1 else list(ids)}
        return self


def _parallelogram():
    d = _Doc('drag_parallelogram').free('A', 0, 0).free('B', 4, 0).free('C', 5, 3)
    d.op('polygon.parallelogram', {'a': _ref('A'), 'b': _ref('B'), 'c': _ref('C')},
         [('polygon', 'P', 'polygon'), ('vertex', 'D', 'point')])
    return d.via('D', 'C')


def _reflected():
    d = _Doc('drag_reflect_point').free('A', 0, 0).free('B', 4, 0).free('C', 1, 3).free('O', 2, -1)
    d.op('polygon.by_points', {'vertices': {'kind': 'list', 'items': [_ref('A'), _ref('B'), _ref('C')]}},
         [('polygon', 'T', 'polygon')])
    d.op('transform.reflect_point', {'obj': _ref('T'), 'point': _ref('O')},
         [('image', 'T1', 'polygon'), ('vertex.1', 'A1', 'point'), ('vertex.2', 'B1', 'point'),
          ('vertex.3', 'C1', 'point')])
    return d.via('A1', 'A').via('B1', 'B').via('C1', 'C')


def _translated():
    d = _Doc('drag_translate').free('A', 1, 1).free('U', 0, 0).free('V', 2, 1)
    d.args('vector.by_points', 'v', 'vector', a='U', b='V')
    d.op('transform.translate', {'obj': _ref('A'), 'vector': _ref('v')}, [('image', 'A1', 'point')])
    return d.via('A1', 'A')


def _segment(doc_id):
    d = _Doc(doc_id).free('A', 0, 0).free('B', 4, 0).free('O', 2, 1)
    d.args('segment.by_points', 's', 'segment', a='A', b='B').on_path('P', 's', 0.25)
    d.op('transform.reflect_point', {'obj': _ref('P'), 'point': _ref('O')}, [('image', 'Q', 'point')])
    return d.via('Q', 'P')


def _circle():
    d = _Doc('drag_on_path').free('O', 0, 0).free('R', 3, 0).free('C', 1, 1)
    d.args('circle.center_point', 'k', 'circle', center='O', through='R').on_path('P', 'k', 0.5)
    d.args('point.midpoint', 'M', 'point', slot='point', a='P', b='C')
    return d.via('M', 'P')


def _midpoint():
    d = _Doc('drag_two_inputs').free('A', 0, 0).free('B', 4, 2)
    d.args('point.midpoint', 'M', 'point', slot='point', a='A', b='B')
    return d.via('M', 'A', 'B')


def _incenter(doc_id):
    d = _Doc(doc_id).free('A', 1, 3).free('B', 0, 0).free('C', 4, 0)
    d.args('triangle.incenter', 'I', 'point', slot='point', a='A', b='B', c='C')
    return d.via('I', 'A')


_X = {'var': 'x'}


def _cubic(doc_id, x=1.0):
    """``P`` on the graph of ``x³/4 − x`` on ``[−3, 3]``; ``Q`` is ``P`` reflected in ``O``."""
    def o(name, *args):
        return {'op': name, 'args': list(args)}
    d = _Doc(doc_id).free('O', 0, 0)
    ast = o('-', o('/', o('^', _X, {'num': 3}), {'num': 4}), _X)
    d.op('function.expr', {'expr': {'kind': 'expr', 'ast': ast}, 'refs': {'kind': 'list', 'items': []},
                           'min': {'kind': 'number', 'value': -3}, 'max': {'kind': 'number', 'value': 3}},
         [('function', 'f', 'function')])
    d.op('point.on_function', {'function': _ref('f')}, [('point', 'P', 'point')])
    d.doc['inputs']['P'] = _par(x)
    d.op('transform.reflect_point', {'obj': _ref('P'), 'point': _ref('O')}, [('image', 'Q', 'point')])
    return d.via('Q', 'P')


def _ellipse(doc_id):
    """``P`` on the ellipse with foci ``(±4, 0)`` through ``(0, 3)`` (a = 5, b = 3); ``M`` the
    midpoint of ``P`` and ``C``, dragged through ``P``."""
    d = _Doc(doc_id).free('F1', -4, 0).free('F2', 4, 0).free('T', 0, 3).free('C', 1, 1)
    d.conic('conic.ellipse_foci_point', 'e', f1='F1', f2='F2', through='T').on_path('P', 'e', 6.0, pathKind='ellipse')
    d.args('point.midpoint', 'M', 'point', slot='point', a='P', b='C')
    return d.via('M', 'P')


def _hyperbola(doc_id):
    """``P`` on the left branch of x²/9 − y²/16 = 1; ``M`` the midpoint of ``P`` and ``C``."""
    d = _Doc(doc_id).free('F1', -5, 0).free('F2', 5, 0).free('T', 3, 0).free('C', 1, 1)
    d.conic('conic.hyperbola_foci_point', 'h', f1='F1', f2='F2', through='T')
    d.on_path('P', 'h', 0.2, branch=-1, pathKind='hyperbola')
    d.args('point.midpoint', 'M', 'point', slot='point', a='P', b='C')
    return d.via('M', 'P')


def _parabola(doc_id):
    """``P`` on the parabola with focus ``(0, 1)`` and directrix ``y = −1`` (y = x²/4)."""
    d = _Doc(doc_id).free('F', 0, 1).free('A', -1, -1).free('B', 1, -1)
    d.args('line.by_points', 'l', 'line', a='A', b='B')
    return d.conic('conic.parabola_focus_directrix', 'q', focus='F', directrix='l').on_path('P', 'q', 0.0,
                                                                                            pathKind='parabola')


def _graph_path(doc_id):
    """``P`` on the graph of ``x < 0: −x; x ≥ 1: x − 1`` (no value between) on ``[−3, 4]``."""
    def o(name, *args):
        return {'op': name, 'args': list(args)}
    ast = {'if': [{'cmp': '<', 'args': [_X, {'num': 0}]}, o('-', {'num': 0}, _X),
                  {'if': [{'cmp': '>=', 'args': [_X, {'num': 1}]}, o('-', _X, {'num': 1})]}]}
    d = _Doc(doc_id)
    d.op('function.expr', {'expr': {'kind': 'expr', 'ast': ast}, 'refs': {'kind': 'list', 'items': []},
                           'min': {'kind': 'number', 'value': -3}, 'max': {'kind': 'number', 'value': 4}},
         [('function', 'f', 'function')])
    d.doc['operationRegistryVersion'] = '1.9'
    return d.on_path('P', 'f', -1.0)


def _foot():
    d = _Doc('drag_singular').free('P', 1, 3).free('B', -2, -1).free('C', 5, 1)
    d.args('line.by_points', 'l', 'line', a='B', b='C')
    d.args('line.perpendicular', 'm', 'line', point='P', base='l')
    d.args('intersect.line_line', 'F', 'point', slot='point', first='m', second='l')
    return d.via('F', 'P')


# (name, text, builder, inputs, element, target)
def _locus(doc_id):
    d = _Doc(doc_id).free('A', 0, 0).free('B', 4, 0).free('C', 0, 2)
    d.args('segment.by_points', 's', 'segment', a='A', b='B').on_path('M', 's', .25)
    d.args('point.midpoint', 'T', 'point', a='M', b='C')
    d.args('locus.of_point', 'g', 'locus', trace='T', mover='M').on_path('P', 'g', .375)
    d.doc['operationRegistryVersion'] = '1.10'
    d.args('point.midpoint', 'D', 'point', a='P', b='C')
    return d.via('D', 'P')


CASES = (
    ('drag_locus', 'project onto a continuous link of the locus',
     lambda: _locus('drag_locus'), {}, 'P', [1.25, 2]),
    ('drag_locus_clamped', 'a normalized locus parameter stops at its end',
     lambda: _locus('drag_locus_clamped'), {}, 'P', [4, 1]),
    ('drag_via_locus', 'a dependent midpoint through a continuous locus parameter',
     lambda: _locus('drag_via_locus'), {}, 'D', [.625, 1.5]),
    ('drag_free', 'a free point goes to the target', _parallelogram, {'B': _pt(4, 0.5)}, 'A', [0.5, -1.25]),
    ('drag_projection', 'a point on a segment without a hint: the nearest point of the segment',
     lambda: _segment('drag_projection'), {}, 'P', [3, 2]),
    ('drag_projection_clamped', 'the nearest point is the end of the segment',
     lambda: _segment('drag_projection_clamped'), {'P': _par(0.5)}, 'P', [6, 1]),
    ('drag_parallelogram', 'the fourth vertex of a parallelogram through C: one step',
     _parallelogram, {'C': _pt(5, 3.5)}, 'D', [1.5, 4]),
    ('drag_reflect_point', 'a vertex of the reflected triangle through the original vertex: one step',
     _reflected, {}, 'A1', [3.25, -2.5]),
    ('drag_translate', 'a translated point through the original: one step', _translated, {}, 'A1', [-2, 0.5]),
    ('drag_on_path', 'one path parameter drives the point: the nearest point it reaches',
     _circle, {}, 'M', [4, 4]),
    ('drag_clamped', 'the path parameter stops at the end of its segment',
     lambda: _segment('drag_clamped'), {}, 'Q', [-3, 2]),
    ('drag_two_inputs', 'a midpoint through both ends: the least change moves both alike',
     _midpoint, {'B': _pt(4, 2)}, 'M', [3, 3]),
    ('drag_incenter', 'an incenter through a vertex: several steps',
     lambda: _incenter('drag_incenter'), {}, 'I', [1.8, 1.2]),
    ('drag_no_convergence', 'an incenter outside the circle on the diameter BC: angle BIC > 90 degrees',
     lambda: _incenter('drag_no_convergence'), {'B': _pt(0, 0)}, 'I', [2, 2.5]),
    ('drag_singular', 'the foot of a perpendicular moves along a fixed line only: rank 1 < 2',
     _foot, {'P': _pt(1, 3)}, 'F', [0, 3]),
    ('drag_on_function', 'a point on a graph without a hint takes the x of the target',
     lambda: _cubic('drag_on_function'), {}, 'P', [2, 5]),
    ('drag_on_function_clamped', 'the x of the target lies past the domain [-3, 3]: x stops at its end',
     lambda: _cubic('drag_on_function_clamped'), {}, 'P', [5, 0]),
    ('drag_via_on_function', 'a point reflected from a point on a graph, through its x: Q = -P, x = 2.5',
     lambda: _cubic('drag_via_on_function'), {}, 'Q', [-2.5, -1.40625]),
    ('drag_conic_ellipse', 'a point on an ellipse without a hint: the nearest point, its kind written',
     lambda: _ellipse('drag_conic_ellipse'), {}, 'P', [1, 0.5]),
    ('drag_conic_branch', 'a point on a hyperbola without a hint: the nearest point of the nearest branch',
     lambda: _hyperbola('drag_conic_branch'), {}, 'P', [4.5, -2]),
    ('drag_conic_parabola', 'a point on a parabola without a hint, above the vertex past the centre of curvature',
     lambda: _parabola('drag_conic_parabola'), {}, 'P', [0, 5]),
    ('drag_graph_path', 'a point on a graph (point.on_path) without a hint: the nearest point, across a gap',
     lambda: _graph_path('drag_graph_path'), {}, 'P', [0.8, -0.5]),
    ('drag_graph_path_clamped', 'the nearest point of the graph is the end of its domain [-3, 4]',
     lambda: _graph_path('drag_graph_path_clamped'), {}, 'P', [6, 1]),
    ('drag_via_ellipse', 'a midpoint through a point on an ellipse: the parameter wraps into [0, 2pi)',
     lambda: _ellipse('drag_via_ellipse'), {}, 'M', [(5 * math.cos(0.3) + 1) / 2, (3 * math.sin(0.3) + 1) / 2]),
    ('drag_via_hyperbola', 'a midpoint through a point on a hyperbola: the branch stays, the nearest point it reaches',
     lambda: _hyperbola('drag_via_hyperbola'), {}, 'M', [3, 2]),
)


def _rounded(value):
    if isinstance(value, bool) or value is None or isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f'a non-finite number {value!r} in a drag fixture')
        return round(value, DIGITS) + 0.0
    if isinstance(value, dict):
        return {k: _rounded(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_rounded(v) for v in value]
    raise TypeError(f'{type(value).__name__} in a drag fixture')


def _run(doc, inputs, element, target) -> dict:
    from .drag import drag
    return drag(doc, inputs, element, target)


def build_fixtures() -> dict:
    """``{file name: fixture}``."""
    from .. import __version__
    out = {}
    for name, text, make, inputs, element, target in CASES:
        doc = make().doc
        result = _run(doc, copy.deepcopy(inputs), element, target)
        expect_inputs = copy.deepcopy(inputs) if result['status'] in REFUSALS else _rounded(result['inputs'])
        out[name + '.json'] = json.loads(json.dumps({
            'format': DRAG_PARITY_FORMAT, 'id': name, 'generatedBy': f'animageo {__version__}', 'text': text,
            'doc': doc, 'inputs': inputs, 'element': element, 'target': target,
            'expect': {'status': result['status'], 'inputs': expect_inputs}}))
    return out


def _dump(fixture) -> str:
    return json.dumps(fixture, ensure_ascii=False, indent=1) + '\n'


def write_fixtures(directory=DEFAULT_DIR) -> list:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fixture in sorted(build_fixtures().items()):
        path = directory / name
        path.write_text(_dump(fixture), encoding='utf-8')
        written.append(path)
    return written


def _unlabelled(fixture: dict) -> dict:
    out = dict(fixture)
    out.pop('generatedBy', None)
    return out


def check_fixtures(directory=DEFAULT_DIR) -> list:
    """Files that differ from a fresh build (the version label aside)."""
    directory = Path(directory)
    problems = []
    built = build_fixtures()
    for name, fixture in sorted(built.items()):
        path = directory / name
        if not path.exists():
            problems.append(f'{path}: missing')
            continue
        if _unlabelled(json.loads(path.read_text(encoding='utf-8'))) != _unlabelled(fixture):
            problems.append(f'{path}: out of date')
    for path in sorted(directory.glob('*.json')):
        if path.name not in built:
            problems.append(f'{path}: not built here')
    return problems


def _compare_inputs(expected, actual, where) -> list:
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return [f'{where}: expected {expected!r}, got {actual!r}']
    if set(expected) != set(actual):
        return [f'{where}: keys {sorted(expected)} != {sorted(actual)}']
    out = []
    for key in sorted(expected):
        want, have = expected[key], actual[key]
        if not isinstance(want, dict) or not isinstance(have, dict) or set(want) != set(have) \
                or any(want.get(k) != have.get(k) for k in ('kind', 'branch', 'pathKind')):
            out.append(f'{where}.{key}: expected {want!r}, got {have!r}')
            continue
        a = want.get('value')
        b = have.get('value')
        a = a if isinstance(a, list) else [a]
        b = b if isinstance(b, list) else [b]
        if len(a) != len(b) or not all(abs(x - y) <= TOLERANCE for x, y in zip(a, b)):
            out.append(f'{where}.{key}: expected {want!r}, got {have!r}')
    return out


def verify_fixture(fixture: dict, label: str = '') -> list:
    """Mismatches of one ``animageo-drag-parity/v1`` fixture."""
    label = label or str(fixture.get('id', '?'))
    inputs = copy.deepcopy(fixture.get('inputs'))
    before = copy.deepcopy(inputs)
    try:
        result = _run(fixture['doc'], inputs, fixture['element'], fixture['target'])
    except (KeyError, ValueError) as exc:
        return [f'{label}: {exc}']
    expect = fixture.get('expect') or {}
    out = []
    if inputs != before:
        out.append(f'{label}: the inputs were changed')
    if result['status'] != expect.get('status'):
        out.append(f"{label}: status {expect.get('status')!r} expected, got {result['status']!r}")
    if result['status'] in REFUSALS:
        if result['inputs'] is not inputs:
            out.append(f'{label}: a refusal must return the given inputs object')
        if result['inputs'] != expect.get('inputs'):
            out.append(f"{label}: inputs {expect.get('inputs')!r} expected, got {result['inputs']!r}")
        return out
    if result['inputs'] is inputs:
        out.append(f'{label}: a success must return a new inputs object')
    return out + _compare_inputs(expect.get('inputs'), result['inputs'], f'{label} inputs')


def verify_fixtures(directory=DEFAULT_DIR) -> tuple:
    """``(files, cases, mismatches)`` of the fixtures in ``directory``."""
    files = 0
    mismatches = []
    for path in sorted(Path(directory).glob('*.json')):
        fixture = json.loads(path.read_text(encoding='utf-8'))
        files += 1
        mismatches.extend(verify_fixture(fixture, path.stem))
    return files, files, mismatches
