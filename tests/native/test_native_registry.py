"""Registry ops/v1: records, signature hashes, INDEX.json, implementations."""
import json
import math
import shutil
import subprocess
import sys

import pytest

from animageo import native
from animageo.native.kernel.checks import CHECKS
from animageo.native.kernel.ops import IMPLEMENTATIONS
from animageo.native.registry import (
    build_index,
    registry,
    registry_problems,
    signature,
    signature_hash,
    write_index,
)
from tests.native.conftest import NATIVE_DIR, REPO_ROOT

OPS_DIR = NATIVE_DIR / 'ops' / 'v1'

L0_OPS = {
    'point.free', 'segment.by_points', 'line.by_points', 'circle.center_point',
    'point.midpoint', 'intersect.line_line', 'polygon.by_points',
}
L1_OPS = {'ray.by_points', 'intersect.line_circle', 'intersect.circle_circle', 'intersect.other_than',
          'point.on_path'}
L2A1_OPS = {'point.projection', 'line.parallel', 'line.perpendicular', 'line.perpendicular_bisector',
            'line.angle_bisector', 'vector.by_points', 'circle.center_radius', 'circle.three_points',
            'number.free'}
ALL_OPS = L0_OPS | L1_OPS | L2A1_OPS
# Registries 1.1 and 1.2 extend 1.0: the L0 and L1 records and their hashes stay as they were.
L0_HASHES = {
    'circle.center_point': 'sha256:f3b2e070e9310312708009adfc04cfd7411128d482a4b7522f7320af35ca9810',
    'intersect.line_line': 'sha256:be74b127f909906e8dfe346f7ad79043e483defde31d0aac29628ae550f925d2',
    'line.by_points': 'sha256:fcebec1d748517206963944a677642a99ed3277715db0b080587c3f92d4f1b6a',
    'point.free': 'sha256:8b74a96e3fc44081f156f70c28fd7ff0a313aa75c844bcf33a64077d8715bb63',
    'point.midpoint': 'sha256:487dfc5d3ce9f32ebae3ee47bfc7a5d5127675a88b55c996af6b8133f028ade7',
    'polygon.by_points': 'sha256:4108d41bea24861a3d178199e4f71555531690b60bc98da2328da512209ea272',
    'segment.by_points': 'sha256:be1a52a14b19e85053b0533d3dd3d8a0b12a43b1f5969fafcbe12c79988dcc0d',
}
L1_HASHES = {
    'intersect.circle_circle': 'sha256:aaf9cd94fe4397efd5334ab77080571b7bec01cd314cc8ee25ff781cbdbfb657',
    'intersect.line_circle': 'sha256:f02f846a64efd9254acce5e15862bd73b76e1da86dd91851d65720ef0cbdb8c8',
    'intersect.other_than': 'sha256:2f4d6797ee18797329eccd116a221f147f701ae15d6da0892528cb553b9700cd',
    'point.on_path': 'sha256:6be50eade341c6f39273693152fcb25f733d8875492505670e76c12b38916a72',
    'ray.by_points': 'sha256:799d3583f4263ffd7c7c9c71236851e44764de7e5136e02284c49fb4898bfa80',
}
RECORD_FIELDS = {
    'op', 'status', 'since', 'inputs', 'params', 'outputs', 'branch', 'undefined', 'checks',
    'orientation', 'pathParam', 'stepKind', 'phrases', 'math', 'signatureHash',
}


def test_version():
    assert native.__registry_version__ == '1.2'
    assert registry().version == '1.2'
    assert json.loads((OPS_DIR / 'INDEX.json').read_text())['registryVersion'] == '1.2'


def test_ops_and_files():
    reg = registry()
    assert set(reg.ops) == ALL_OPS
    assert set(reg.groups) == {'point', 'line', 'circle', 'intersect', 'polygon', 'number'}
    for name in ('_types', '_policies', '_reasons', '_numeric', 'INDEX'):
        assert (OPS_DIR / f'{name}.json').is_file()


def test_l0_records_unchanged():
    reg = registry()
    for op, digest in L0_HASHES.items():
        assert reg.get(op)['signatureHash'] == digest
        assert reg.index['ops'][op] == digest
        assert reg.get(op)['since'] == '1.0'
    for op, digest in L1_HASHES.items():
        assert reg.get(op)['signatureHash'] == digest
        assert reg.index['ops'][op] == digest
        assert reg.get(op)['since'] == '1.1'
    for op in L2A1_OPS:
        assert reg.get(op)['since'] == '1.2'


@pytest.mark.parametrize('op', sorted(ALL_OPS))
def test_record_fields(op):
    record = registry().get(op)
    assert RECORD_FIELDS <= set(record) <= RECORD_FIELDS | {'free'}
    assert record['status'] == 'stable'
    if op not in ('point.projection', 'number.free'):
        assert record['params'] == []
    for param in record['params']:
        assert {'slot', 'type', 'unit', 'text'} <= set(param) <= {'slot', 'type', 'unit', 'optional',
                                                                   'default', 'text'}
        assert param['type'] == 'number'
    branch = record['branch']
    assert branch is None or (set(branch) >= {'policy', 'slots', 'text'}
                              and branch['policy'] in registry().policies)
    if op in L0_OPS:
        assert branch is None and record['pathParam'] is None
    assert (record['pathParam'] is not None) == (op == 'point.on_path')
    assert record['math'] == f'docs/native/ops/{op}.md'
    assert (REPO_ROOT / record['math']).is_file()
    assert set(record['phrases']) == {'ru'}
    for check in record['checks']:
        assert set(check) == {'id', 'text'}
    for reason in record['undefined']:
        assert reason in registry().reasons


def test_contract_table():
    """The slot table of the plan (§4): inputs, outputs, reasons, checks."""
    reg = registry()

    def summary(op):
        r = reg.get(op)
        return ([(i['slot'], i['type'], i.get('list', False), i.get('min')) for i in r['inputs']],
                [(o['slot'], o['type'], o.get('repeat')) for o in r['outputs']],
                r['undefined'], [c['id'] for c in r['checks']], r.get('free'))

    assert summary('point.free') == ([], [('point', 'point', None)], [], [], {'kind': 'point'})
    assert summary('segment.by_points') == (
        [('a', 'point', False, None), ('b', 'point', False, None)], [('segment', 'segment', None)],
        ['upstream'], ['ends'], None)
    assert summary('line.by_points') == (
        [('a', 'point', False, None), ('b', 'point', False, None)], [('line', 'line', None)],
        ['coincident_points', 'upstream'], ['through_a', 'through_b'], None)
    assert summary('circle.center_point') == (
        [('center', 'point', False, None), ('through', 'point', False, None)], [('circle', 'circle', None)],
        ['nonpositive_radius', 'upstream'], ['through_on_circle'], None)
    assert summary('point.midpoint') == (
        [('a', 'point', False, None), ('b', 'point', False, None)], [('point', 'point', None)],
        ['upstream'], ['equidistant', 'collinear'], None)
    assert summary('intersect.line_line') == (
        [('first', 'linear', False, None), ('second', 'linear', False, None)], [('point', 'point', None)],
        ['parallel', 'coincident', 'outside_part', 'zero_length', 'upstream'], ['incident_both'], None)
    assert summary('polygon.by_points') == (
        [('vertices', 'point', True, 3)], [('polygon', 'polygon', None), ('side', 'segment', 'vertices')],
        ['upstream'], ['sides_match'], None)
    assert summary('ray.by_points') == (
        [('origin', 'point', False, None), ('through', 'point', False, None)], [('ray', 'ray', None)],
        ['coincident_points', 'upstream'], ['origin', 'through'], None)
    assert reg.get('ray.by_points')['orientation'] == 'origin_to_through'
    two_points = [('first', 'point', None), ('second', 'point', None)]
    assert summary('intersect.line_circle') == (
        [('line', 'linear', False, None), ('circle', 'circular', False, None)], two_points,
        ['no_intersection', 'outside_part', 'zero_length', 'upstream'], ['on_both'], None)
    assert summary('intersect.circle_circle') == (
        [('first', 'circular', False, None), ('second', 'circular', False, None)], two_points,
        ['no_intersection', 'concentric', 'coincident', 'upstream'], ['on_both'], None)
    assert summary('intersect.other_than') == (
        [('first', 'curve', False, None), ('second', 'curve', False, None), ('known', 'point', False, None)],
        [('point', 'point', None)],
        ['branch_absent', 'no_intersection', 'parallel', 'coincident', 'concentric', 'outside_part',
         'zero_length', 'upstream'], ['on_both'], None)
    assert summary('point.on_path') == (
        [('path', 'path', False, None)], [('point', 'point', None)], ['upstream'], ['on_path'],
        {'kind': 'pathParameter'})
    assert reg.get('point.on_path')['pathParam'] == 'carrier/v1'
    branches = {op: reg.get(op)['branch'] for op in L1_OPS}
    assert branches['ray.by_points'] is None
    assert branches['intersect.line_circle']['policy'] == 'line_param_order'
    assert branches['intersect.line_circle']['slots'] == ['first', 'second']
    assert branches['intersect.circle_circle']['policy'] == 'circle_side'
    assert branches['intersect.other_than']['policy'] == 'other_than'
    assert branches['intersect.other_than']['slots'] == ['point']
    assert reg.families == {
        'linear': ['line', 'segment', 'ray'],
        'circular': ['circle'],
        'curve': ['line', 'segment', 'ray', 'circle'],
        'path': ['line', 'segment', 'ray', 'circle', 'polygon'],
    }
    assert reg.accepts('linear', 'ray') and not reg.accepts('circular', 'ray')


def test_contract_table_l2a1():
    """The slot table of the L2 plan (§3.1): inputs, params, outputs, reasons, checks."""
    reg = registry()

    def summary(op):
        r = reg.get(op)
        return ([(i['slot'], i['type']) for i in r['inputs']],
                [(p['slot'], p.get('unit'), p.get('optional', False), p.get('default')) for p in r['params']],
                [(o['slot'], o['type']) for o in r['outputs']],
                r['undefined'], [c['id'] for c in r['checks']], r.get('free'), r['orientation'])

    pl = [('point', 'point'), ('base', 'linear')]
    assert summary('point.projection') == (
        pl, [('strict', None, True, 0)], [('foot', 'point')],
        ['zero_length', 'outside_part', 'invalid_parameter', 'upstream'], ['on_carrier', 'perpendicular'],
        None, None)
    assert summary('line.parallel') == (
        pl, [], [('line', 'line')], ['zero_length', 'upstream'], ['through_point', 'parallel'], None,
        'carrier_dir')
    assert summary('line.perpendicular') == (
        pl, [], [('line', 'line')], ['zero_length', 'upstream'], ['through_point', 'perpendicular'], None,
        'carrier_dir_ccw90')
    assert summary('line.perpendicular_bisector') == (
        [('a', 'point'), ('b', 'point')], [], [('line', 'line')], ['coincident_points', 'upstream'],
        ['through_midpoint', 'perpendicular'], None, 'ab_ccw90')
    assert summary('line.angle_bisector') == (
        [('a', 'point'), ('vertex', 'point'), ('b', 'point')], [], [('line', 'line')],
        ['coincident_points', 'upstream'], ['through_vertex', 'equal_angles'], None, 'into_angle')
    assert summary('vector.by_points') == (
        [('a', 'point'), ('b', 'point')], [], [('vector', 'vector')], ['upstream'], ['ends'], None, 'a_to_b')
    assert summary('circle.center_radius') == (
        [('center', 'point'), ('radius', 'number')], [], [('circle', 'circle')],
        ['nonpositive_radius', 'upstream'], ['matches'], None, None)
    assert summary('circle.three_points') == (
        [('a', 'point'), ('b', 'point'), ('c', 'point')], [], [('circle', 'circle'), ('center', 'point')],
        ['collinear_points', 'upstream'], ['through_all'], None, None)
    assert summary('number.free') == (
        [], [('min', None, True, None), ('max', None, True, None), ('step', None, True, None)],
        [('number', 'number')], ['invalid_parameter'], [], {'kind': 'number'}, None)
    for op in L2A1_OPS:
        assert reg.get(op)['branch'] is None
        assert reg.get(op)['pathParam'] is None


def test_l2a1_types_and_frames():
    reg = registry()
    assert reg.types['vector']['value'] == {'a': 'length', 'b': 'length', 'length': 'length'}
    assert reg.types['number']['value'] == {'value': 'by_unit'}
    assert reg.number_units == {'scalar': 'scalar', 'length': 'length', 'area': 'area', 'angle': 'scalar',
                                'count': 'scalar'}
    frames = reg.paths['line']['frames']
    assert frames['line.parallel'] == {'origin': 'args.point', 'vector': 'value.dir'}
    for op in L2A1_OPS:          # new ops keep input and output slot names apart (phrases)
        record = reg.get(op)
        assert not {i['slot'] for i in record['inputs'] + record['params']} & {o['slot'] for o in record['outputs']}, op
    assert frames['line.perpendicular'] == {'origin': 'args.point', 'vector': 'value.dir'}
    assert frames['line.perpendicular_bisector'] == {'origin': 'mid(args.a, args.b)', 'vector': 'value.dir'}
    assert frames['line.angle_bisector'] == {'origin': 'args.vertex', 'vector': 'value.dir'}
    for op in frames:
        assert op == '*' or op in reg.ops


def test_registry_problems_catch_bad_params(tmp_path):
    copy_dir = tmp_path / 'v1'
    shutil.copytree(OPS_DIR, copy_dir)
    point = json.loads((copy_dir / 'point.json').read_text())
    projection = next(r for r in point if r['op'] == 'point.projection')
    projection['params'][0]['type'] = 'point'
    del projection['params'][0]['optional']
    (copy_dir / 'point.json').write_text(json.dumps(point))
    number = json.loads((copy_dir / 'number.json').read_text())
    number[0]['params'][0]['default'] = 'low'
    number[0]['params'][1]['optional'] = False          # a required param without a default is fine
    (copy_dir / 'number.json').write_text(json.dumps(number))
    from animageo.native.registry import _load
    problems = registry_problems(_load(copy_dir))
    assert "point.projection: param 'strict' must have type 'number'" in problems
    assert "point.projection: param 'strict' is required and has a default" in problems
    assert "number.free: param 'min' default must be a number" in problems
    assert not any("'max'" in p for p in problems)
    assert any(p.startswith('INDEX.json') for p in problems)


def test_types_and_policies_catalogs():
    reg = registry()
    assert reg.types['ray']['value'] == {'origin': 'length', 'dir': 'scalar'}
    assert set(reg.policies) == {'single', 'line_param_order', 'circle_side', 'other_than'}
    assert set(reg.paths) == set(reg.families['path'])
    kinds = {'segment': 'affine', 'line': 'affine', 'ray': 'affine', 'circle': 'angle', 'polygon': 'perimeter'}
    assert {t: reg.paths[t]['kind'] for t in reg.paths} == kinds
    assert reg.paths['segment']['default'] == 0.5 and reg.paths['line']['default'] == 0.5
    assert reg.paths['circle']['default'] == math.pi / 4
    for type_, entry in reg.paths.items():
        lo, hi = entry['min'], entry['max']
        assert lo is None or entry['default'] >= lo
        assert not isinstance(hi, (int, float)) or entry['default'] <= hi
        if entry['kind'] == 'affine':
            assert '*' in entry['frames']
            for frame in entry['frames'].values():
                assert set(frame) == {'origin', 'vector'}


def test_registry_problems_catch_bad_catalogs(tmp_path):
    copy_dir = tmp_path / 'v1'
    shutil.copytree(OPS_DIR, copy_dir)
    types = json.loads((copy_dir / '_types.json').read_text())
    types['families']['path'].append('arc')
    del types['paths']['ray']
    (copy_dir / '_types.json').write_text(json.dumps(types))
    line = json.loads((copy_dir / 'line.json').read_text())
    next(r for r in line if r['op'] == 'ray.by_points')['since'] = '1.9'
    (copy_dir / 'line.json').write_text(json.dumps(line))
    from animageo.native.registry import _load
    problems = registry_problems(_load(copy_dir))
    assert "family 'path': unknown type 'arc'" in problems
    assert "path type 'ray' has no entry in _types.json paths" in problems
    assert any(p.startswith("ray.by_points: since '1.9'") for p in problems)


def test_implementations_both_ways():
    reg = registry()
    assert set(IMPLEMENTATIONS) == set(reg.ops)
    declared = {(op, c['id']) for op, r in reg.ops.items() for c in r['checks']}
    assert set(CHECKS) == declared


def test_signature_hash_is_stable():
    record = registry().get('point.midpoint')
    assert signature(record) == {
        'op': 'point.midpoint',
        'inputs': [{'slot': 'a', 'type': 'point', 'list': False, 'min': None},
                   {'slot': 'b', 'type': 'point', 'list': False, 'min': None}],
        'params': [],
        'outputs': [{'slot': 'point', 'type': 'point', 'repeat': None}],
        'free': None, 'branch': None, 'orientation': None, 'pathParam': None,
    }
    assert signature_hash(record) == record['signatureHash']
    # descriptive fields are outside the hash
    changed = dict(record, phrases={'ru': 'другое'}, checks=[], status='beta', math='x.md')
    assert signature_hash(changed) == record['signatureHash']
    assert signature_hash(dict(record, orientation='a_to_b')) != record['signatureHash']
    # explicit defaults hash like omitted ones
    explicit = dict(record, inputs=[dict(i, list=False) for i in record['inputs']])
    assert signature_hash(explicit) == record['signatureHash']


def test_index_is_up_to_date():
    assert registry_problems() == []
    assert registry().index == build_index()
    assert write_index(check=True) == []


def test_write_index_refreshes_a_copy(tmp_path):
    copy_dir = tmp_path / 'v1'
    shutil.copytree(OPS_DIR, copy_dir)
    point = json.loads((copy_dir / 'point.json').read_text())
    point[0]['signatureHash'] = 'sha256:stale'
    point[0]['outputs'][0]['slot'] = 'p'
    (copy_dir / 'point.json').write_text(json.dumps(point, ensure_ascii=False, indent=2) + '\n')
    assert write_index(copy_dir, check=True) == ['point.json', 'INDEX.json']
    assert write_index(copy_dir) == ['point.json', 'INDEX.json']
    assert write_index(copy_dir, check=True) == []
    index = json.loads((copy_dir / 'INDEX.json').read_text())
    assert index['ops']['point.free'] != registry().index['ops']['point.free']
    assert index['ops']['point.midpoint'] == registry().index['ops']['point.midpoint']


def test_cli_registry_index_check():
    proc = subprocess.run([sys.executable, '-m', 'animageo.native', 'registry', 'index', '--check'],
                          cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert 'up to date' in proc.stdout


def test_numeric_catalog():
    numeric = registry().numeric
    assert numeric['tolerances'] == {
        'decide': {'length': 1e-10, 'scalar': 1e-10},
        'check': {'passed': 1e-9, 'failed': 1e-6},
        'parity': {'length': 1e-9, 'area': 1e-9, 'scalar': 1e-9},
    }
    assert numeric['generator']['decisionMargin'] == 1000
    assert numeric['defaultBounds'] == [-10, -10, 10, 10]


def test_reasons_catalog_states():
    reasons = registry().reasons
    assert reasons['upstream']['state'] == 'inherited'
    assert {reasons[r]['state'] for r in ('unknown_op', 'newer_registry')} == {'unsupported'}
    assert {reasons[r]['state'] for r in ('schema', 'dangling_ref', 'cycle', 'type_mismatch', 'internal')} == {'error'}
    for op in registry().ops.values():
        for reason in op['undefined']:
            assert reasons[reason]['state'] in ('undefined', 'inherited')
