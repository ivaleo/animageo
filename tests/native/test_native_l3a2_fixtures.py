"""1.9.0a2: the shipped fixtures of recipes, general case and marks are up to
date and replay from their inputs (plan L3 §3.8)."""
import collections
import json

from animageo.native.conditions.fixtures import DEFAULT_ROOT, check_fixtures, verify_fixtures
from animageo.native.conditions.recipes import recipes


def _cases(sub):
    out = []
    for path in sorted((DEFAULT_ROOT / sub).glob('*.json')):
        out += json.loads(path.read_text(encoding='utf-8'))['cases']
    return out


def test_fixtures_are_fresh_and_replay():
    assert check_fixtures() == []
    files, cases, mismatches = verify_fixtures()
    assert files == 7 and cases >= 107 + 30 + 30 and mismatches == []


def test_fixture_counts():
    rec = _cases('recipes')
    assert len(rec) >= 107
    applied = collections.Counter(c['expect']['document']['conditions'][-1]['recipe'] for c in rec
                                  if 'condition' in c and c['expect'].get('refusal') is None)
    assert all(applied[r['recipe']] >= 5 for r in recipes()), applied
    codes = collections.Counter(c['expect']['refusal']['code'] for c in rec if c['expect'].get('refusal'))
    assert set(codes) == {'unsupported_condition', 'receiver_not_free', 'receiver_is_ancestor',
                          'too_many_conditions', 'no_intersection_now'} and sum(codes.values()) >= 15
    assert all(c['expect']['check'] == 'passed' for c in rec if c['expect'].get('check'))
    general = _cases('general')
    statuses = collections.Counter(c['expect']['status'] for c in general)
    assert len(general) >= 30 and set(statuses) == {'passed', 'failed', 'inconclusive'}
    marks = _cases('marks')
    sources = collections.Counter(s for c in marks if len(c['sources']) == 1 for s in c['sources'])
    assert len(sources) == 9 and min(sources.values()) >= 3
