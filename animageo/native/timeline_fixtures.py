"""Fixtures of stage 4 of plan L3 (§5.2, §8): ``animageo-timeline/v1`` in
``animageo/native/parity/v1/timeline``.

One file per document: ``{format, id, registry, generatedBy, document,
cases: [{name, timeline, samples: [t…], expect: {samples: [{t, inputs,
visible}], bridge}}]}`` — ``samples`` of :func:`sample_timeline` at each
``t``, ``bridge`` — :func:`timeline_to_bridge`; ``steps`` — the
:func:`steps_timeline` of the document with the default arguments. Numbers
compare with ``1e-9`` (absolute); everything else exactly. The documents
are built here; expectations are what this library gives.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .registry import REGISTRY_VERSION

__all__ = ['TIMELINE_FORMAT', 'DEFAULT_DIR', 'build_fixtures', 'write_fixtures', 'check_fixtures',
           'verify_fixture', 'verify_fixtures']

TIMELINE_FORMAT = 'animageo-timeline/v1'
DEFAULT_DIR = Path(__file__).resolve().parent / 'parity' / 'v1' / 'timeline'
TOLERANCE = 1e-9


def _ref(el_id):
    return {'kind': 'ref', 'elementId': el_id}


class _Doc:
    def __init__(self, doc_id, bounds=(-6, -4, 6, 4)):
        self.doc = {'format': 'animageo-construction/v1', 'documentId': doc_id,
                    'operationRegistryVersion': REGISTRY_VERSION, 'operations': {}, 'elements': {},
                    'inputs': {}, 'viewDefaults': {'bounds': list(bounds)}}

    def op(self, name, args, outputs, op_id=None):
        op_id = op_id or 'op_' + outputs[0][1]
        self.doc['operations'][op_id] = {'id': op_id, 'op': name, 'args': args,
                                         'outputs': [{'slot': s, 'elementId': e} for s, e, _t in outputs]}
        for slot, el_id, type_ in outputs:
            self.doc['elements'][el_id] = {'id': el_id, 'type': type_, 'displayName': el_id,
                                           'producer': {'operationId': op_id, 'slot': slot}}
        return self

    def free(self, el_id, x, y):
        self.op('point.free', {}, [('point', el_id, 'point')])
        self.doc['inputs'][el_id] = {'kind': 'point', 'value': [x, y]}
        return self

    def on(self, el_id, path, t):
        self.op('point.on_path', {'path': _ref(path)}, [('point', el_id, 'point')])
        self.doc['inputs'][el_id] = {'kind': 'pathParameter', 'value': t}
        return self

    def number(self, el_id, value, lo=None, hi=None):
        args = {}
        if lo is not None:
            args['min'] = {'kind': 'number', 'value': lo}
        if hi is not None:
            args['max'] = {'kind': 'number', 'value': hi}
        self.op('number.free', args, [('number', el_id, 'number')])
        self.doc['inputs'][el_id] = {'kind': 'number', 'value': value}
        return self

    def hide(self, el_id):
        self.doc.setdefault('appearance', {})[el_id] = {'visible': False}
        return self


def paths_document() -> dict:
    """A point on every path type, a free number, a hidden helper."""
    d = _Doc('timeline_paths')
    d.free('A', 0, 0).free('B', 3, 0).free('C', 1, 2).free('D', -2, 1)
    d.op('segment.by_points', {'a': _ref('A'), 'b': _ref('B')}, [('segment', 's', 'segment')])
    d.op('ray.by_points', {'origin': _ref('A'), 'through': _ref('C')}, [('ray', 'r', 'ray')])
    d.op('line.by_points', {'a': _ref('B'), 'b': _ref('C')}, [('line', 'l', 'line')])
    d.op('circle.center_point', {'center': _ref('A'), 'through': _ref('B')}, [('circle', 'c', 'circle')])
    d.op('polygon.by_points', {'vertices': {'kind': 'list', 'items': [_ref('A'), _ref('B'), _ref('C'), _ref('D')]}},
         [('polygon', 'q', 'polygon')])
    d.op('arc.center_two_points', {'center': _ref('A'), 'a': _ref('B'), 'b': _ref('C')}, [('arc', 'ar', 'arc')])
    d.op('sector.center_two_points', {'center': _ref('D'), 'a': _ref('A'), 'b': _ref('C')},
         [('sector', 'sc', 'sector')])
    d.op('polyline.by_points', {'points': {'kind': 'list', 'items': [_ref('D'), _ref('A'), _ref('C')]}},
         [('polyline', 'pl', 'polyline')])
    d.on('Ps', 's', 0.25).on('Pr', 'r', 0.5).on('Pl', 'l', 0.0).on('Pc', 'c', 0.5)
    d.on('Pq', 'q', 3.5).on('Pa', 'ar', 0.2).on('Psc', 'sc', 2.5).on('Ppl', 'pl', 0.5)
    d.number('k', 1.0, 0, 5)
    d.op('segment.by_points', {'a': _ref('C'), 'b': _ref('D')}, [('segment', 'h', 'segment')])
    d.hide('h')
    return d.doc


def triangle_document() -> dict:
    d = _Doc('timeline_triangle')
    d.free('A', -3, -2).free('B', 3, -2).free('C', 0, 2.5)
    d.op('polygon.by_points', {'vertices': {'kind': 'list', 'items': [_ref('A'), _ref('B'), _ref('C')]}},
         [('polygon', 't', 'polygon')])
    d.op('point.midpoint', {'a': _ref('A'), 'b': _ref('B')}, [('point', 'M', 'point')])
    d.op('segment.by_points', {'a': _ref('C'), 'b': _ref('M')}, [('segment', 'm', 'segment')])
    d.doc['steps'] = [{'id': 'median', 'kind': 'group', 'title': 'Медиана',
                       'operationIds': ['op_M', 'op_m'], 'text': 'Проводим медиану CM'}]
    return d.doc


def _kf(t, **kw):
    out = {'t': t}
    out.update(kw)
    return out


def _cases() -> list:
    """``[(document builder, [(name, timeline, samples)])]``."""
    grid = [0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0]
    paths = []
    for easing in ('linear', 'smooth', 'in_out', 'ease_out_back', 'ease_out_bounce', 'rush_into'):
        paths.append((f'point_{easing}', {'version': 2, 'keyframes': [
            _kf(0, values={'A': [0, 0]}), _kf(2, values={'A': [2, -1]}, easing=easing)]}, grid))
    for direction in ('short', 'long', 'cw', 'ccw'):
        paths.append((f'circle_{direction}', {'version': 2, 'keyframes': [
            _kf(0, values={'Pc': {'tparam': 0.5}}),
            _kf(2, values={'Pc': {'tparam': 5.5, 'direction': direction}}, easing='linear')]}, grid))
    for direction in ('short', 'long', 'cw', 'ccw'):
        paths.append((f'polygon_{direction}', {'version': 2, 'keyframes': [
            _kf(0, values={'Pq': {'tparam': 3.5}}),
            _kf(2, values={'Pq': {'tparam': 0.5, 'direction': direction}}, easing='linear')]}, grid))
    for direction in ('short', 'long'):
        paths.append((f'sector_{direction}', {'version': 2, 'keyframes': [
            _kf(0, values={'Psc': {'tparam': 2.5}}),
            _kf(2, values={'Psc': {'tparam': 0.5, 'direction': direction}}, easing='linear')]}, grid))
    for el_id, a, b in (('Ps', 0.0, 1.0), ('Pr', 0.5, 3.0), ('Pl', -1.0, 2.0), ('Pa', 0.0, 1.0),
                        ('Ppl', 0.0, 2.0)):
        paths.append((f'linear_path_{el_id}', {'version': 2, 'keyframes': [
            _kf(0, values={el_id: {'tparam': a}}),
            _kf(2, values={el_id: {'tparam': b, 'direction': 'ccw'}}, easing='smooth')]}, grid))
    paths.append(('number', {'version': 2, 'defaults': {'easing': 'linear'}, 'keyframes': [
        _kf(0), _kf(1, values={'k': 3}), _kf(3, values={'k': 0.5}, easing='in')]}, grid))
    paths.append(('carry_forward_values', {'version': 2, 'keyframes': [
        _kf(0, values={'A': [0, 0]}), _kf(1, values={'B': [4, 1]}), _kf(2, values={'C': [1, 3]}),
        _kf(3, values={'A': [-1, -1], 'Pc': {'tparam': 1.0}})]}, grid))
    paths.append(('visibility_carry_forward', {'version': 2, 'keyframes': [
        _kf(0, visible={'s': False, 'c': False}, hide=['q']),
        _kf(1, show=['s'], visible={'h': True}),
        _kf(2, visible={'c': True, 's': False}, enter={'c': {'effect': 'create', 'duration': 0.5, 'at': 0.2}}),
        _kf(3, hide=['h'], exit={'h': 'fade'}, visible={'gone': True})]}, grid))
    paths.append(('clamped_time', {'version': 2, 'keyframes': [
        _kf(1, values={'B': [3, 0]}), _kf(2, values={'B': [3, 2]}, easing='linear')]}, [-1.0, 0.5, 1.5, 2.0, 5.0]))
    paths.append(('styles_and_camera', {'version': 2, 'keyframes': [
        _kf(0, values={'@camera': {'width': 12}}),
        _kf(1, values={'@camera': {'width': 8}, 'A': [0.5, 0.5]}, styles={'c': {'stroke': '#ff0000'}},
            events=[{'effect': 'indicate', 'targets': ['A', 'k'], 'at': 0.1}])]}, [0.0, 0.5, 1.0]))
    triangle = [('steps_timeline', None, [0.0, 0.5, 1.1, 1.5, 2.2, 3.0, 4.0])]
    return [(paths_document, paths), (triangle_document, triangle)]


def _expect(document, timeline, samples) -> dict:
    from .timeline import sample_timeline, timeline_to_bridge
    return {'samples': [sample_timeline(document, timeline, t) for t in samples],
            'bridge': timeline_to_bridge(document, timeline)}


def build_fixtures() -> dict:
    """``{file name: fixture}``."""
    from .. import __version__
    from .timeline import steps_timeline
    out = {}
    for builder, cases in _cases():
        document = builder()
        steps = steps_timeline(document).to_dict()
        rows = []
        for name, timeline, samples in cases:
            if timeline is None:
                timeline = steps['keyframes']
            rows.append({'name': name, 'timeline': timeline, 'samples': samples,
                         'expect': _expect(document, timeline, samples)})
        out[document['documentId'] + '.json'] = {
            'format': TIMELINE_FORMAT, 'id': document['documentId'], 'registry': REGISTRY_VERSION,
            'generatedBy': f'animageo {__version__}', 'document': document, 'steps': steps, 'cases': rows}
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


def check_fixtures(directory=DEFAULT_DIR) -> list:
    """Files that differ from a fresh build (the version label aside)."""
    directory = Path(directory)
    problems = []
    for name, fixture in sorted(build_fixtures().items()):
        path = directory / name
        if not path.exists():
            problems.append(f'{path}: missing')
            continue
        old = json.loads(path.read_text(encoding='utf-8'))
        old.pop('generatedBy', None)
        new = dict(fixture)
        new.pop('generatedBy', None)
        if old != json.loads(json.dumps(new)):
            problems.append(f'{path}: out of date')
    return problems


def _compare(expected, actual, where) -> list:
    if isinstance(expected, bool) or isinstance(actual, bool) or expected is None or actual is None:
        return [] if expected == actual else [f'{where}: expected {expected!r}, got {actual!r}']
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        ok = math.isfinite(expected) and abs(expected - actual) <= TOLERANCE
        return [] if ok else [f'{where}: expected {expected!r}, got {actual!r}']
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f'{where}: expected {len(expected)} items, got {len(actual)}']
        out = []
        for i, (e, a) in enumerate(zip(expected, actual)):
            out += _compare(e, a, f'{where}[{i}]')
        return out
    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(expected) != set(actual):
            return [f'{where}: keys {sorted(expected)} != {sorted(actual)}']
        out = []
        for key in sorted(expected):
            out += _compare(expected[key], actual[key], f'{where}.{key}')
        return out
    return [] if expected == actual else [f'{where}: expected {expected!r}, got {actual!r}']


def verify_fixture(fixture: dict, label: str = '') -> tuple:
    """``(cases, mismatches)`` of one ``animageo-timeline/v1`` fixture."""
    from .timeline import steps_timeline
    label = label or str(fixture.get('id', '?'))
    document = fixture['document']
    out = []
    actual_steps = json.loads(json.dumps(steps_timeline(document).to_dict()))
    out += _compare(fixture.get('steps'), actual_steps, f'{label} steps')
    for case in fixture.get('cases') or []:
        where = f"{label} [{case.get('name')}]"
        try:
            actual = json.loads(json.dumps(_expect(document, case['timeline'], case['samples'])))
        except (KeyError, ValueError) as exc:
            out.append(f'{where}: {exc}')
            continue
        out += _compare(case.get('expect'), actual, where)
    return len(fixture.get('cases') or []), out


def verify_fixtures(directory=DEFAULT_DIR) -> tuple:
    """``(files, cases, mismatches)`` over the fixtures in ``directory``."""
    files = cases = 0
    mismatches = []
    for path in sorted(Path(directory).glob('*.json')):
        fixture = json.loads(path.read_text(encoding='utf-8'))
        n, out = verify_fixture(fixture, path.stem)
        files += 1
        cases += n
        mismatches += out
    return files, cases, mismatches
