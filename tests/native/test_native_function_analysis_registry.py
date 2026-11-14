"""Function analysis registry metadata and additive numerical profile."""
import copy

import pytest

from animageo import native
from animageo.native.registry import registry, registry_problems, signature_hash

GROUPS = {
    'region.by_boundary': 'regions', 'function.area_between': 'regions',
    'point.expression': 'expressions', 'vector.expression': 'expressions',
    'line.equation': 'expressions', 'point.on_locus': 'locus',
}
ANALYSIS_OPS = ('roots_polynomial', 'extrema_polynomial', 'value', 'root_near',
                'root_interval', 'roots_interval', 'extrema_interval')
GROUPS.update({'line.tangent_function_at': 'tangency', 'line.slope': 'tangency'})
GROUPS.update({'function.' + name: 'function_analysis' for name in ANALYSIS_OPS})


def test_registry_version_and_complete_feature():
    assert native.__registry_version__ == '1.12'
    assert native.has('function_analysis')


def test_registry_module_groups_are_exact():
    reg = registry()
    assert {op: r['moduleGroup'] for op, r in reg.ops.items() if 'moduleGroup' in r} == {
        op: group for op, group in GROUPS.items() if op in reg.ops}


@pytest.mark.parametrize('op,group', [('point.expression', None), ('point.expression', 'wrong'),
                                      ('point.free', 'regions'), ('point.free', None)])
def test_registry_rejects_missing_wrong_and_extra_groups(op, group):
    reg = copy.deepcopy(registry())
    if op == 'point.expression' and group is None:
        reg.ops[op].pop('moduleGroup', None)
    else:
        reg.ops[op]['moduleGroup'] = group
    assert any('moduleGroup' in p and op in p for p in registry_problems(reg))


def test_registry_group_does_not_change_signatures():
    for op, group in GROUPS.items():
        if op in registry().ops:
            record = registry().get(op)
            assert signature_hash(record) == signature_hash(dict(record, moduleGroup=group + '_changed'))


def test_registry_additive_numeric_profile_and_reasons():
    profile = registry().numeric['functionAnalysis']
    assert profile == dict(maxPolynomialDegree=64, maxResults=100, gridCells=512, pieceGridCells=512,
                          bisectionSteps=200, continuitySteps=2200, goldenSteps=100, newtonSteps=128,
                          backtrackSteps=16, bracketInitialStep=1.0, bracketMaxStep=1048576.0,
                          bracketMaxDoublings=20, xAbs=1e-12, xRel=1e-12, residualRel=1e-12,
                          maxEvaluations=262144)
    for reason in ('not_polynomial', 'no_root', 'no_extremum', 'no_convergence'):
        assert registry().reasons[reason]['state'] == 'undefined'
    assert 'not_bracketed' not in registry().reasons
    assert 'distinct_roots_ascending' in registry().policies


def test_registry_complete_function_analysis_contract():
    reg = registry()
    assert set(reg.groups['function_analysis']) == {'function.' + name for name in ANALYSIS_OPS}
    assert reg.get('function.value')['undefined'] == ['out_of_domain', 'upstream']
    for name, base in [('roots_polynomial', 'root'), ('extrema_polynomial', 'extremum'),
                       ('roots_interval', 'root'), ('extrema_interval', 'extremum')]:
        record = reg.get('function.' + name)
        assert record['since'] == '1.11' and record['moduleGroup'] == 'function_analysis'
        assert record['outputs'] == [{'slot': base, 'type': 'point', 'repeat': 'count'}]
        assert record['branch']['policy'] == 'distinct_roots_ascending'
        assert record['branch']['slots'] == [base]
        assert record['params'][0]['default'] == 100
        assert [check['id'] for check in record['checks']] == ['on_graph']
        assert not set(record['undefined']) & {'not_bracketed', 'out_of_domain', 'discontinuous'}
