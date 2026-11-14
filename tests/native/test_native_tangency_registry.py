"""Complete tangency catalog and frozen earlier signatures."""
import copy
import json

import pytest

from animageo import native
from animageo.native.kernel.ops import IMPLEMENTATIONS
from animageo.native.registry import registry, registry_problems, signature_hash, _MODULE_GROUPS
from tests.native.conftest import NATIVE_DIR

NAMES = {'line.' + name for name in ('tangent_function_at', 'tangent_conic_at',
         'tangents_from_point_conic', 'tangents_parallel_conic', 'slope')}
ACTIVE = NAMES


def catalog():
    return {r['op']: r for r in json.loads((NATIVE_DIR / 'ops/v1/tangency.json').read_text())}


def test_catalog_and_active_registry_are_honest():
    assert native.__registry_version__ == '1.12'
    assert native.has('tangency')
    assert set(catalog()) == NAMES
    assert {k for k, v in _MODULE_GROUPS.items() if v == 'tangency'} == NAMES
    assert set(registry().groups['tangency']) == ACTIVE
    assert set(IMPLEMENTATIONS) == set(registry().ops)
    assert registry_problems() == []
    for name, r in catalog().items():
        assert r['since'] == '1.12' and r['status'] == 'beta'
        assert r['moduleGroup'] == 'tangency'
        assert r['free'] is None and r['pathParam'] is None
        assert signature_hash(r) == r['signatureHash']
        assert signature_hash(dict(r, moduleGroup='changed')) == r['signatureHash']
        assert (registry().get(name) is not None) == (name in ACTIVE)


def test_all_operations_through_1_11_keep_hash_and_since():
    frozen = json.loads((NATIVE_DIR.parents[1] / 'tests/native/registry_frozen_1_11.json').read_text())
    assert frozen['registryVersion'] == '1.11' and len(frozen['ops']) == 122
    old = {k: v for k, v in registry().ops.items() if v['since'] != '1.12'}
    assert set(old) == set(frozen['ops'])
    for name, record in old.items():
        assert {'signatureHash': signature_hash(record), 'since': record['since']} == frozen['ops'][name]


def test_conic_contract_and_polar_order():
    records = catalog()
    assert records['line.tangent_conic_at']['outputs'] == [{'slot': 'line', 'type': 'line'}]
    for name in ('line.tangents_from_point_conic', 'line.tangents_parallel_conic'):
        record = records[name]
        assert record['params'][0]['default'] == 2
        assert record['outputs'] == [{'slot': 'tangent', 'type': 'line', 'repeat': 'count'},
                                     {'slot': 'touch', 'type': 'point', 'repeat': 'count'}]
        assert record['branch']['policy'] in registry().policies
        assert record['branch']['slots'] == ['tangent', 'touch']
    assert records['line.tangents_from_point_conic']['branch']['policy'] == 'polar_contacts_descending'
    assert records['line.tangents_parallel_conic']['branch']['policy'] == 'oriented_conic_support'
    assert registry().families['conic_section'] == ['circle', 'conic']
    assert registry().families['conical'] == ['conic', 'circle', 'arc']
    assert [(r['op'], i['slot']) for r in records.values() for i in r['inputs']
            if i['type'] == 'conic_section'] == [('line.tangents_parallel_conic', 'conic')]


def test_tangency_profile_is_additive():
    assert registry().numeric['tangency'] == dict(maxRefinements=24, initialStep=2**-8,
        directionAbs=1e-10, continuityRel=1e-10, requiredStableLevels=3, maxEvaluations=262144,
        gridCells=512, maxResults=100, xAbs=1e-12, xRel=1e-12, residualRel=1e-12)
    for reason in ('no_tangent', 'not_differentiable', 'vertical_line'):
        assert registry().reasons[reason]['state'] == 'undefined'


@pytest.mark.parametrize('name', sorted(ACTIVE))
def test_tangency_requires_its_module_group(name):
    reg = copy.deepcopy(registry())
    reg.ops[name]['moduleGroup'] = 'wrong'
    assert any(name in p and 'moduleGroup' in p for p in registry_problems(reg))
