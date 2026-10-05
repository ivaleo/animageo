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
L2A2_OPS = {'angle.by_points', 'mark.equal_segments', 'mark.equal_angles', 'mark.right_angle', 'circle.incircle'}
L2A4_OPS = {
    'point.divide', 'point.center', 'point.closest', 'point.at_distance', 'polygon.vertex',
    'line.angle_bisectors_of_lines', 'line.external_bisector', 'ray.at_angle', 'ray.by_vector',
    'line.tangents_from_point', 'line.tangent_at', 'segment.from_point_length', 'segment.midline',
    'polyline.by_points', 'circle.diameter', 'circle.center_segment', 'circle.excircle',
    'arc.center_two_points', 'arc.three_points', 'arc.semicircle', 'arc.on_circle',
    'sector.center_two_points', 'sector.from_angle', 'sector.three_points', 'sector.on_circle',
    'polygon.regular', 'polygon.regular_center', 'polygon.parallelogram', 'polygon.centroid',
    'intersect.line_sector',
}
L2A5_OPS = {
    'angle.between_lines', 'angle.between_vectors', 'angle.by_size', 'number.angle',
    'measure.length', 'measure.distance', 'measure.area', 'measure.perimeter', 'measure.angle',
    'measure.radius', 'measure.circumference', 'measure.polygon_angles',
    'transform.translate', 'transform.rotate', 'transform.reflect_line', 'transform.reflect_point',
    'transform.dilate',
}
ALL_OPS = L0_OPS | L1_OPS | L2A1_OPS | L2A2_OPS | L2A4_OPS | L2A5_OPS
# Registries 1.1–1.4 extend 1.0: earlier records and their hashes stay as they were.
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
L2A1_HASHES = {
    'circle.center_radius': 'sha256:c3cf41fefb5b9675a41b3eb39298640a6651d988efef6865edd85f6462746349',
    'circle.three_points': 'sha256:143575451176f3a78d933062a88a75fa09836dab57dfedcc5c4d759a8d4b484b',
    'line.angle_bisector': 'sha256:6ffd1703f1ee29ee4fb8c79821f0fec0ffe843603ddbcbc1e62b96e1d1bdc611',
    'line.parallel': 'sha256:accc08e8e25d6d93e61db4b712bf57d6c04040f795e331cde964388b3824ad08',
    'line.perpendicular': 'sha256:31a8254ebc3e153ebf3ec03ca88a34b0f172ecadb6ca75458dda8b49a7da7c21',
    'line.perpendicular_bisector': 'sha256:9483c6abef4e1451223fc437f8fb971b767b2b71e0a9f9bdfc63f7d605da8d4b',
    'number.free': 'sha256:1b23a21461be5d9d3b96461a10823bfc46c347a8bc7da320cffa91e36bca6f2a',
    'point.projection': 'sha256:d335c0ed75eeb527edd741676e32473b0fc8e3a23b4a46a36a8575f2f2d1bba5',
    'vector.by_points': 'sha256:7f2f4e4551fe968c3a7714fe613de1fc65218c5ad6dbc65e911f37d8e05aef11',
}
L2A2_HASHES = {
    'angle.by_points': 'sha256:6cff8a588d81eec06ee2b49dfdd3fd97f810f09a77d47ee7538efd69d8e19dd9',
    'circle.incircle': 'sha256:34708fea4fe868318bd751e18738c0e9281810946593126bfca83f0ab0a47ee6',
    'mark.equal_angles': 'sha256:15ac3c04805733999d86b498aba04faeb02ca31705673802ea5f312016c9c2e3',
    'mark.equal_segments': 'sha256:5ba6180e0246c4dc70cf392096184e1427760c4d9a39b6bb5842e3ddd4de668a',
    'mark.right_angle': 'sha256:22f1e524869af7e1d61fa1e6481c78e08b9c2094cbafaa8b4f41d899eec89915',
}
RECORD_FIELDS = {
    'op', 'status', 'since', 'inputs', 'params', 'outputs', 'branch', 'undefined', 'checks',
    'orientation', 'pathParam', 'stepKind', 'phrases', 'math', 'signatureHash',
}


def test_version():
    assert native.__registry_version__ == '1.4'
    assert registry().version == '1.4'
    assert json.loads((OPS_DIR / 'INDEX.json').read_text())['registryVersion'] == '1.4'


def test_ops_and_files():
    reg = registry()
    assert set(reg.ops) == ALL_OPS
    assert set(reg.groups) == {'point', 'line', 'circle', 'intersect', 'polygon', 'number', 'angle', 'mark',
                               'arc', 'measure', 'transform'}
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
    for op, digest in L2A1_HASHES.items():
        assert reg.get(op)['signatureHash'] == digest
        assert reg.index['ops'][op] == digest
        assert reg.get(op)['since'] == '1.2'
    assert set(L2A1_HASHES) == L2A1_OPS
    for op, digest in L2A2_HASHES.items():
        assert reg.get(op)['signatureHash'] == digest
        assert reg.index['ops'][op] == digest
        assert reg.get(op)['since'] == '1.3'
    assert set(L2A2_HASHES) == L2A2_OPS
    for op in L2A4_OPS | L2A5_OPS:
        assert reg.get(op)['since'] == '1.4'


@pytest.mark.parametrize('op', sorted(ALL_OPS))
def test_record_fields(op):
    record = registry().get(op)
    assert RECORD_FIELDS <= set(record) <= RECORD_FIELDS | {'free'}
    assert record['status'] == ('beta' if op in ('ray.by_vector', 'angle.between_vectors') else 'stable')
    if op not in ('point.projection', 'number.free', 'mark.equal_segments', 'mark.equal_angles',
                  'polygon.vertex', 'polygon.regular', 'polygon.regular_center', 'number.angle'):
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
    assert reg.families == {     # registry 1.4 adds arc, sector, polyline and two families
        'linear': ['line', 'segment', 'ray'],
        'circular': ['circle', 'arc'],
        'curve': ['line', 'segment', 'ray', 'circle', 'arc'],
        'path': ['line', 'segment', 'ray', 'circle', 'polygon', 'arc', 'sector', 'polyline'],
        'round': ['circle', 'arc', 'sector'],
        'vertexed': ['segment', 'polyline', 'polygon'],
        'measurable': ['segment', 'vector', 'polyline', 'arc'],
        'bounded': ['polygon', 'circle', 'sector'],
        'figure': ['point', 'line', 'segment', 'ray', 'circle', 'polygon', 'arc', 'sector', 'polyline'],
        'transformable': ['point', 'segment', 'ray', 'line', 'vector', 'circle', 'arc', 'sector', 'polygon'],
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


def test_contract_table_l2a2():
    """The slot table of the L2 plan (§4.1, registry 1.3)."""
    reg = registry()

    def summary(op):
        r = reg.get(op)
        return ([(i['slot'], i['type'], i.get('list', False), i.get('min')) for i in r['inputs']],
                [(p['slot'], p.get('unit'), p.get('optional', False), p.get('default')) for p in r['params']],
                [(o['slot'], o['type']) for o in r['outputs']],
                r['undefined'], [c['id'] for c in r['checks']], r['orientation'], r['stepKind'])

    avb = [('a', 'point', False, None), ('vertex', 'point', False, None), ('b', 'point', False, None)]
    count = [('count', 'count', True, 1)]
    assert summary('angle.by_points') == (
        avb, [], [('angle', 'angle')], ['coincident_points', 'upstream'], ['sides'], 'ccw_from_a', 'angle')
    assert summary('mark.equal_segments') == (
        [('segments', 'segment', True, 2)], count, [('mark', 'mark')], ['invalid_parameter', 'upstream'],
        ['equal'], None, 'mark')
    assert summary('mark.equal_angles') == (
        [('angles', 'angle', True, 2)], count, [('mark', 'mark')], ['invalid_parameter', 'upstream'],
        ['equal'], None, 'mark')
    assert summary('mark.right_angle') == (
        avb, [], [('mark', 'mark')], ['coincident_points', 'upstream'], ['right'], None, 'mark')
    assert summary('circle.incircle') == (
        [('a', 'point', False, None), ('b', 'point', False, None), ('c', 'point', False, None)], [],
        [('circle', 'circle'), ('center', 'point'), ('touch_a', 'point'), ('touch_b', 'point'),
         ('touch_c', 'point')],
        ['collinear_points', 'upstream'], ['tangent_sides'], None, 'incircle')
    for op in L2A2_OPS:
        record = reg.get(op)
        assert record['branch'] is None and record['pathParam'] is None and 'free' not in record
        assert not {i['slot'] for i in record['inputs'] + record['params']} & {o['slot'] for o in record['outputs']}, op


def test_l2a2_types():
    reg = registry()
    assert reg.types['angle']['value'] == {'vertex': 'length', 'a0': 'scalar', 'a1': 'scalar', 'size': 'scalar'}
    assert reg.types['mark']['value'] == {}
    assert reg.mark_kinds == {'equal_segments': 'mark.equal_segments', 'equal_angles': 'mark.equal_angles',
                              'right_angle': 'mark.right_angle'}
    assert 'angle' not in reg.families['path'] and 'mark' not in reg.families['path']
    from animageo.native.kernel.values import compare_values

    def tol(kind):
        return {'length': 1e-9, 'scalar': 1e-9}[kind]

    a = {'vertex': [0.0, 0.0], 'a0': 0.0, 'a1': 1.0, 'size': 1.0}
    assert compare_values(reg.types['angle'], a, dict(a, a0=1e-12), tol) == []
    assert compare_values(reg.types['angle'], a, dict(a, size=1.1), tol)
    m = {'kind': 'equal_segments', 'count': 1}
    assert compare_values(reg.types['mark'], m, dict(m), tol) == []
    assert compare_values(reg.types['mark'], m, dict(m, count=2), tol) == ["value.count: expected 1, got 2"]
    assert compare_values(reg.types['mark'], m, dict(m, kind='equal_angles'), tol)


def test_registry_problems_catch_bad_mark_kinds(tmp_path):
    copy_dir = tmp_path / 'v1'
    shutil.copytree(OPS_DIR, copy_dir)
    types = json.loads((copy_dir / '_types.json').read_text())
    types['markKinds']['arrow'] = 'mark.arrow'
    types['markKinds']['angle'] = 'angle.by_points'
    (copy_dir / '_types.json').write_text(json.dumps(types))
    from animageo.native.registry import _load
    problems = registry_problems(_load(copy_dir))
    assert "mark kind 'arrow': 'mark.arrow' is not an operation with a mark output" in problems
    assert "mark kind 'angle': 'angle.by_points' is not an operation with a mark output" in problems


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
    assert set(reg.policies) == {'single', 'line_param_order', 'circle_side', 'other_than',
                                 'tangent_side', 'bisector_kind', 'vertex_index', 'sector_sides'}
    assert set(reg.paths) == set(reg.families['path'])
    kinds = {'segment': 'affine', 'line': 'affine', 'ray': 'affine', 'circle': 'angle', 'polygon': 'perimeter',
             'arc': 'arc', 'sector': 'sector', 'polyline': 'polyline'}
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
    types['families']['path'].append('spiral')
    del types['paths']['ray']
    (copy_dir / '_types.json').write_text(json.dumps(types))
    line = json.loads((copy_dir / 'line.json').read_text())
    next(r for r in line if r['op'] == 'ray.by_points')['since'] = '1.9'
    (copy_dir / 'line.json').write_text(json.dumps(line))
    from animageo.native.registry import _load
    problems = registry_problems(_load(copy_dir))
    assert "family 'path': unknown type 'spiral'" in problems
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
