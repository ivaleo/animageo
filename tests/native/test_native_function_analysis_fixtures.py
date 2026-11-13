"""Analytical answers of the shared function-analysis curves fixtures."""
import math

import pytest

from animageo.native import curves_fixtures
from animageo.native.parity import verify_fixture


@pytest.fixture(scope='module')
def fixtures():
    return {name: f for name, f in curves_fixtures.build_fixtures().items()
            if name.startswith('function_')}


def test_function_fixtures_cover_all_three_implemented_operations(fixtures):
    assert {'function_roots_poly.json', 'function_extrema_poly.json', 'function_poly_limits.json',
            'function_found_slots.json', 'function_value.json', 'function_value_domain.json',
            'function_value_branches.json', 'function_poly_rank_changes.json',
            'function_poly_upstream.json'} <= set(fixtures)
    defined = {}
    for fixture in fixtures.values():
        assert verify_fixture(fixture) == []
        for op in fixture['document']['operations'].values():
            if op['op'] not in ('function.roots_polynomial', 'function.extrema_polynomial', 'function.value'):
                continue
            for case in fixture['cases']:
                if any(case['expect'][out['elementId']]['state'] == 'defined' for out in op['outputs']):
                    defined[op['op']] = defined.get(op['op'], 0) + 1
    assert set(defined) == {'function.roots_polynomial', 'function.extrema_polynomial', 'function.value'}
    assert min(defined.values()) >= 3


def test_function_roots_fixture_uses_exact_independent_answers(fixtures):
    expect = fixtures['function_roots_poly.json']['cases'][0]['expect']
    for key, x in {'A1': 1, 'A2': 3, 'B1': 0, 'B2': 2, 'Far1': 1000}.items():
        assert expect[key]['value'] == {'x': x, 'y': 0}
    expect = fixtures['function_poly_limits.json']['cases'][0]['expect']
    for key, x in {'T1': 1e12, 'S1': -math.sqrt(2), 'S2': math.sqrt(2)}.items():
        assert expect[key]['value'] == {'x': round(x, 9), 'y': 0}


def test_function_extrema_fixture_uses_exact_independent_answers(fixtures):
    expect = fixtures['function_extrema_poly.json']['cases'][0]['expect']
    assert expect['E1']['value'] == {'x': -1, 'y': 2}
    assert expect['E1']['detail'] == {'found': 2, 'kind': 'max'}
    assert expect['E2']['value'] == {'x': 1, 'y': -2}
    assert expect['E2']['detail'] == {'found': 2, 'kind': 'min'}
    assert expect['Q1']['value'] == {'x': 0, 'y': 0}
    assert expect['Q1']['detail'] == {'found': 1, 'kind': 'min'}
    assert expect['I1']['reason'] == 'no_extremum'


def test_function_found_count_and_absent_slots_are_independent(fixtures):
    expect = fixtures['function_found_slots.json']['cases'][0]['expect']
    assert expect['R1']['detail'] == {'found': 3}
    assert expect['R1']['value'] == {'x': -1, 'y': 0}
    assert expect['All4']['reason'] == 'branch_absent' and 'detail' not in expect['All4']
    assert expect['N1']['reason'] == 'no_root' and 'detail' not in expect['N1']
    assert expect['M1']['detail'] == {'found': 2, 'kind': 'max'}


def test_function_rank_fixture_has_fixed_ids_and_analytic_frames(fixtures):
    fixture = fixtures['function_poly_rank_changes.json']
    cases = fixture['cases']
    assert [c['expect']['R1'].get('value', {}).get('x') for c in cases] == [-1, 0, None, -1]
    assert [c['expect']['R2'].get('reason') for c in cases] == [None, 'branch_absent', 'no_root', None]
    assert all(set(c['expect']) == set(fixture['document']['elements']) for c in cases)


def test_function_value_fixture_varies_argument_and_coefficient(fixtures):
    cases = fixtures['function_value.json']['cases']
    assert [c['expect']['v']['value'] for c in cases] == [
        {'value': 12, 'unit': 'scalar'}, {'value': 48, 'unit': 'scalar'}, {'value': -32, 'unit': 'scalar'}]
    assert all(c['expect']['Y']['value'] == {'x': 0, 'y': 0} for c in cases)
    assert cases[-1]['expect']['P']['value'] == {'x': 4, 'y': -32}


def test_function_fixtures_cover_every_declared_failure(fixtures):
    from animageo.native.registry import registry

    for name in ('function.roots_polynomial', 'function.extrema_polynomial', 'function.value'):
        reasons = set()
        for fixture in fixtures.values():
            for op in fixture['document']['operations'].values():
                if op['op'] == name:
                    reasons.update(c['expect'][out['elementId']].get('reason') for out in op['outputs']
                                   for c in fixture['cases'])
        assert set(registry().get(name)['undefined']) <= reasons


def test_function_literal_ast_coefficients_survive_fixture_rounding(fixtures):
    fixture = fixtures['function_poly_limits.json']
    tree = fixture['document']['operations']['op_tiny_leading']['args']['expr']['ast']
    assert tree['args'][0]['args'][0] == {'num': 1e-12}
    assert fixture['cases'][0]['expect']['tiny_leading']['value']['expr'] == tree
    tiny = fixtures['function_roots_poly.json']
    assert tiny['document']['operations']['op_tiny']['args']['expr']['ast'] == {'num': 1e-30}


def test_function_shared_fixture_pins_rounding_guard_and_scaling(fixtures):
    fixture = fixtures['function_poly_close_roots.json']
    assert fixture['cases'][0]['scale'] == 1
    expect = fixture['cases'][0]['expect']
    for prefix in ('unit_', 'scaled_'):
        assert expect[prefix + 'square1']['detail'] == {'found': 1}
        assert expect[prefix + 'mixed1']['value'] == {'x': -2, 'y': 0}
        assert expect[prefix + 'mixed2']['value'] == {'x': 1, 'y': 0}
        for k, x in [(1, 1), (2, 1 + 1e-6)]:
            rec = expect[prefix + 'close' + str(k)]
            assert rec['value'] == {'x': x, 'y': 0}
            assert rec['detail'] == {'found': 2}
        assert expect[prefix + 'unresolved1']['detail'] == {'found': 1}
        assert expect[prefix + 'unresolved2']['reason'] == 'branch_absent'
