"""Fixtures of typed expressions (``parity/v1/expr``, ``animageo-expr-cases/v1``) and the
scenes ``typed_*`` (registry 1.10)."""
import json
import subprocess
import sys

from animageo import native
from animageo.native import expr_fixtures, parity
from animageo.native.edit import delete
from tests.native.conftest import EXPECTED_DIR, read_json

FIXTURE = expr_fixtures.DEFAULT_DIR / 'typed.json'
SCENES_DIR = EXPECTED_DIR.parent / 'scenes'


def cases():
    return read_json(FIXTURE)['cases']


def test_up_to_date_and_verified():
    assert expr_fixtures.check_fixtures() == []
    files, count, mismatches = expr_fixtures.verify_fixtures()
    assert (files, mismatches) == (1, []) and count >= 60
    assert parity.verify([expr_fixtures.DEFAULT_DIR]) == (1, count, [])


def test_the_format():
    fixture = read_json(FIXTURE)
    assert list(fixture) == ['format', 'registry', 'generatedBy', 'tolerance', 'cases']
    assert fixture['format'] == 'animageo-expr-cases/v1' and fixture['registry'] == '1.12'
    names = [case['name'] for case in fixture['cases']]
    assert len(names) == len(set(names))
    for case in fixture['cases']:
        assert list(case) == ['name', 'ast', 'operands', 'result', 'expect'], case['name']
        assert case['result'] in ('num', 'vec')
        assert all(list(item) == ['name', 'type', 'value'] for item in case['operands'])
        assert list(case['expect']) in (['value', 'text', 'exact'], ['reason'], ['problems']), case['name']


def _nodes(ast):
    stack = [ast]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(node.get('args') or ())
        stack.extend(node.get('pair') or ())


def test_every_new_node_has_a_value_and_a_text():
    seen = set()
    for case in cases():
        if 'value' not in case['expect']:
            continue
        assert case['expect']['text'] == native.expr.to_text(case['ast'], [o['name'] for o in case['operands']])
        types = {o['type'] for o in case['operands']}
        for node in _nodes(case['ast']):
            if 'pair' in node:
                seen.add('pair')
            if 'call' in node:
                seen.add('call')
            if node.get('fn') in ('x', 'y', 'abs'):
                seen.add(node['fn'])
            if 'op' in node:
                seen.add(node['op'])
        seen |= {f'operand:{t}' for t in types}
    assert {'pair', 'call', 'x', 'y', 'abs', '+', '-', '*', '/', 'neg', '^',
            'operand:point', 'operand:vector', 'operand:number', 'operand:function'} <= seen


def test_reasons_and_problems_are_covered():
    reasons = {c['expect']['reason'] for c in cases() if 'reason' in c['expect']}
    assert reasons == {'out_of_domain', 'non_finite'}
    pointers = [p for c in cases() if 'problems' in c['expect'] for p in c['expect']['problems']]
    assert '' in pointers and any(p.startswith('/pair/') for p in pointers) and any(p.startswith('/args/') for p in pointers)


def test_a_changed_expectation_is_reported():
    fixture = read_json(FIXTURE)
    case = next(c for c in fixture['cases'] if c['name'] == 'point_plus_vector')
    case['expect']['text'] = 'A+u'
    assert expr_fixtures.verify_fixture(fixture) == ["typed [point_plus_vector]: expected text 'A+u', got 'A + u'"]
    case['expect']['text'] = 'A + u'
    case['expect']['value'] = [4.0, 6.000001]
    assert len(expr_fixtures.verify_fixture(fixture)) == 1


def test_cli_check():
    out = subprocess.run([sys.executable, '-m', 'animageo.native', 'fixtures', 'expr', '--check'],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert '0 mismatches' in out.stdout


# ── the scenes typed_* ─────────────────────────────────────────────────────

def test_scenes_reach_every_reason():
    states = {}
    for name in ('typed_point_expression', 'typed_vector_expression'):
        fixture = read_json(EXPECTED_DIR / f'{name}.json')
        assert len(fixture['cases']) >= 3
        for case in fixture['cases']:
            for el_id, rec in case['expect'].items():
                op = fixture['document']['operations'][fixture['document']['elements'][el_id]['producer']['operationId']]
                if op['op'].endswith('.expression') and op['op'] != 'number.expression':
                    states.setdefault(op['op'], set()).add((rec['state'], rec.get('reason')))
    for op in ('point.expression', 'vector.expression'):
        assert {('defined', None), ('undefined', 'out_of_domain'), ('undefined', 'non_finite'),
                ('undefined', 'upstream'), ('error', 'formula')} <= states[op], op


def test_deleting_the_rotation_removes_its_hidden_angle():
    doc = read_json(SCENES_DIR / 'typed_expr_chain.json')['document']
    assert doc['elements']['mu']['origin'] == {'kind': 'auto', 'source': 'op_v1'}
    assert doc['appearance']['mu']['role'] == 'aux'
    result = delete(doc, ['v1'])
    elements = set(result.document.elements)
    assert 'mu' not in elements and 'op_mu' not in result.document.operations
    assert {'N', 's', 'T'}.isdisjoint(elements)                     # the dependents of the turned vector
    assert {'M', 'v', 'alpha', 'Y'} <= elements
    assert native.validate(result.document) == []
    assert json.dumps(doc, sort_keys=True) == json.dumps(read_json(SCENES_DIR / 'typed_expr_chain.json')['document'],
                                                         sort_keys=True)
