"""Parity fixtures of space (``parity/v1/space``, 3D-1)."""
from __future__ import annotations

import copy
import json
import subprocess
import sys

import pytest

from animageo.native.space import fixtures as fx
from animageo.native.space.build import SpaceBuilder


@pytest.fixture(scope='module')
def shipped():
    return {path.name: json.loads(path.read_text(encoding='utf-8')) for path in sorted(fx.DEFAULT_DIR.glob('*.json'))}


def test_fixtures_are_fresh_and_replay():
    assert fx.check_fixtures() == []
    files, cases, mismatches = fx.verify_fixtures()
    assert mismatches == []
    assert files == 7 and cases >= 45


def test_counts_of_the_3d1_gate(shipped):
    values = [c for f in shipped.values() if f['kind'] == 'values' for c in f['cases']]
    flats = [c for f in shipped.values() if f['kind'] == 'flat' for c in f['cases']]
    assert len(values) >= 30
    assert len(flats) >= 15
    assert all(2 <= len(c['views']) <= 3 for c in flats)
    projections = {v['camera']['projection'] for c in flats for v in c['views']}
    assert projections == {'orthographic', 'oblique', 'perspective'}
    for f in shipped.values():
        assert f['format'] == 'animageo-space-parity/v1' and f['registry'] == '1.6'


def test_numbers_are_rounded_to_nine_decimals(shipped):
    def walk(value):
        if isinstance(value, float):
            assert round(value, 9) == value
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
    for f in shipped.values():
        for case in f['cases']:
            walk(case.get('expect'))
            for view in case.get('views', ()):
                walk(view['expect'])


def test_replay_catches_a_change(shipped):
    flat = copy.deepcopy(shipped['space_flat_solids.json'])
    view = flat['cases'][0]['views'][0]
    piece = next(p for s in view['expect']['strokes'] for p in s['pieces'] if p['visibility'] == 'hidden')
    piece['visibility'] = 'visible'
    _n, out = fx.verify_fixture(flat)
    assert out and 'visibility' in out[0]

    values = copy.deepcopy(shipped['space_values_solids.json'])
    values['cases'][0]['expect']['elements']['K']['value']['volume'] += 1e-6
    _n, out = fx.verify_fixture(values)
    assert out and 'volume' in out[0]


def test_near_degenerate_cases_are_refused(monkeypatch):
    b = SpaceBuilder('near')
    b.point('A', 0, 0, 0)
    b.point('B', 2, 0, 0)
    b.point('C', 1, 1e-9, 0)                    # nearly collinear, not exactly
    b.plane('P', 'A', 'B', 'C')
    monkeypatch.setattr(fx, 'value_themes', lambda: [('near', [('near', b)])])
    monkeypatch.setattr(fx, 'flat_themes', lambda: [])
    with pytest.raises(ValueError, match='near-degenerate'):
        fx.build_fixtures()


def test_cli_check():
    out = subprocess.run([sys.executable, '-m', 'animageo.native', 'fixtures', 'space', '--check'],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert '0 mismatches' in out.stdout
