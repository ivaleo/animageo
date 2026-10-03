"""Registry ops/v1: records, signature hashes, INDEX.json, implementations."""
import json
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
RECORD_FIELDS = {
    'op', 'status', 'since', 'inputs', 'params', 'outputs', 'branch', 'undefined', 'checks',
    'orientation', 'pathParam', 'stepKind', 'phrases', 'math', 'signatureHash',
}


def test_version():
    assert native.__registry_version__ == '1.0'
    assert registry().version == '1.0'
    assert json.loads((OPS_DIR / 'INDEX.json').read_text())['registryVersion'] == '1.0'


def test_l0_ops_and_files():
    reg = registry()
    assert set(reg.ops) == L0_OPS
    assert set(reg.groups) == {'point', 'line', 'circle', 'intersect', 'polygon'}
    for name in ('_types', '_policies', '_reasons', '_numeric', 'INDEX'):
        assert (OPS_DIR / f'{name}.json').is_file()


@pytest.mark.parametrize('op', sorted(L0_OPS))
def test_record_fields(op):
    record = registry().get(op)
    assert RECORD_FIELDS <= set(record) <= RECORD_FIELDS | {'free'}
    assert record['status'] == 'stable' and record['since'] == '1.0'
    assert record['branch'] is None and record['pathParam'] is None and record['params'] == []
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
    assert reg.families == {'linear': ['line', 'segment']}


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
