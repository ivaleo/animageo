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
        assert f['format'] == 'animageo-space-parity/v1' and f['registry'] == '1.0'


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


# Authored input sources, not computed expectations. Each seed is used by
# at least one existing construction; names/prefixes do not affect its bits.
REGULAR_INPUT_SOURCES = [
    ((3, 1.0, 0.0, 0.0, 0.0, 0.3), 'space_values_solids.json', 'prism_3', 'P'),
    ((3, 1.0, 0.0, 0.0, 0.0, 0.1), 'space_values_solids.json', 'pyramid_3', 'P'),
    ((4, 1.0, 0.0, 0.0, 0.0, 0.3), 'space_values_solids.json', 'prism_4', 'P'),
    ((4, 1.0, 0.0, 0.0, 0.0, 0.1), 'space_values_solids.json', 'pyramid_4', 'P'),
    ((5, 1.0, 0.0, 0.0, 0.0, 0.3), 'space_values_solids.json', 'prism_5', 'P'),
    ((5, 1.0, 0.0, 0.0, 0.0, 0.1), 'space_values_solids.json', 'pyramid_5', 'P'),
    ((6, 1.0, 0.0, 0.0, 0.0, 0.3), 'space_values_solids.json', 'prism_6', 'P'),
    ((6, 1.0, 0.0, 0.0, 0.0, 0.1), 'space_values_solids.json', 'pyramid_6', 'P'),
    ((6, 1.5, 0.0, 0.0, 0.0, 0.0), 'space_values_solids.json', 'prism_right', 'P'),
    ((5, 1.5, 0.0, 0.0, 0.0, 0.0), 'space_values_sections.json', 'prism_slanted', 'P'),
    ((4, 2.0, 0.0, 0.0, 0.0, 0.0), 'space_values_sections.json', 'pyramid_horizontal', 'P'),
    ((4, 1.0, 0.0, 0.0, 0.0, 0.0), 'space_values_reasons.json', 'prism_flat', 'P'),
    ((3, 1.5, 0.0, 0.0, 0.0, 0.0), 'space_flat_solids.json', 'prism_3', 'P'),
    ((4, 1.5, 0.0, 0.0, 0.0, 0.2), 'space_flat_solids.json', 'pyramid_4', 'P'),
    ((5, 1.5, 0.0, 0.0, 0.0, 0.2), 'space_flat_solids.json', 'pyramid_5', 'P'),
    ((4, 1.0, 0.0, -2.5, 3.5, 0.0), 'space_flat_solids.json', 'two_solids', 'Q'),
]


def _input_bits(value):
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, (list, tuple)):
        return [_input_bits(v) for v in value]
    if isinstance(value, dict):
        return {k: _input_bits(v) for k, v in value.items()}
    return value


@pytest.mark.parametrize('key, filename, case_name, prefix', REGULAR_INPUT_SOURCES)
def test_regular_source_coordinates_are_exact(key, filename, case_name, prefix, shipped):
    from animageo.native.space.fixture_inputs import REGULAR_POINTS

    case = next(c for c in shipped[filename]['cases'] if c['name'] == case_name)
    inputs = case['document']['inputs']
    expected = [inputs[f'{prefix}{k}']['value'] for k in range(key[0])]
    assert _input_bits(REGULAR_POINTS[key]) == _input_bits(expected)

    class Points:
        def __init__(self):
            self.inputs = {}

        def point(self, name, *xyz):
            self.inputs[name] = xyz
            return name

    # Prefix is naming only: both P and Q must use the same authored data.
    for name_prefix in ('P', 'Q'):
        b = Points()
        n, r, z, cx, cy, phase = key
        ids = fx._regular(b, n, r=r, z=z, cx=cx, cy=cy, phase=phase, prefix=name_prefix)
        assert ids == [f'{name_prefix}{k}' for k in range(n)]
        assert _input_bits(list(b.inputs.values())) == _input_bits(expected)


def test_top_and_tetrahedron_source_coordinates_are_exact(shipped):
    from animageo.native.space.fixture_inputs import PRISM_TOP, TETRAHEDRON_POINTS

    cases = {c['name']: c for c in shipped['space_values_solids.json']['cases']}
    for n in (3, 4, 5, 6):
        assert _input_bits(PRISM_TOP) == _input_bits(cases[f'prism_{n}']['document']['inputs']['T']['value'])
    inputs = cases['tetra_regular']['document']['inputs']
    assert _input_bits(TETRAHEDRON_POINTS) == _input_bits([inputs[name]['value'] for name in 'ABCD'])


def test_source_seed_set_matches_every_actual_use(monkeypatch):
    from animageo.native.space.fixture_inputs import REGULAR_POINTS

    seen = set()
    original = fx._regular

    def record(b, n, **kwargs):
        seen.add((n, kwargs.get('r', 1.0), kwargs.get('z', 0.0),
                  kwargs.get('cx', 0.0), kwargs.get('cy', 0.0), kwargs.get('phase', 0.0)))
        return original(b, n, **kwargs)

    monkeypatch.setattr(fx, '_regular', record)
    fx.value_themes()
    fx.flat_themes()
    assert seen == set(REGULAR_POINTS) == {row[0] for row in REGULAR_INPUT_SOURCES}
    assert len(seen) == 16


def test_all_source_documents_keep_exact_input_bits(shipped):
    for stem, cases in fx.value_themes() + fx.flat_themes():
        saved = {c['name']: c['document']['inputs'] for c in shipped[stem + '.json']['cases']}
        assert {row[0] for row in cases} == set(saved)
        for name, item, *rest in cases:
            document = item.data() if isinstance(item, SpaceBuilder) else item
            assert _input_bits(document['inputs']) == _input_bits(saved[name]), (stem, name)


@pytest.mark.parametrize('n, kwargs', [
    (7, {}), (4, {'r': 3.0}), (4, {'z': 1.0}), (4, {'cx': 1.0}),
    (4, {'cy': 1.0}), (4, {'phase': 0.4}),
])
def test_unregistered_source_seed_fails_loudly(n, kwargs):
    with pytest.raises(ValueError, match='unregistered regular fixture seed'):
        fx._regular(None, n, **kwargs)


def test_missing_registered_seed_has_no_fallback(monkeypatch):
    from animageo.native.space.fixture_inputs import REGULAR_POINTS

    monkeypatch.delitem(REGULAR_POINTS, (4, 1.0, 0.0, 0.0, 0.0, 0.0))
    with pytest.raises(ValueError, match='unregistered regular fixture seed'):
        fx._regular(None, 4)


def test_fixture_source_data_is_literal_and_has_no_libm_calls():
    import ast
    import inspect
    from animageo.native.space import fixture_inputs

    source = ast.parse(inspect.getsource(fixture_inputs))
    assert isinstance(source.body[0], ast.Expr) and isinstance(source.body[0].value, ast.Constant)
    assert all(isinstance(node, ast.Assign) for node in source.body[1:])
    for node in source.body[1:]:
        ast.literal_eval(node.value)
    tree = ast.parse(inspect.getsource(fx))
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and isinstance(node.func.value, ast.Name) and node.func.value.id == 'math'
                   and node.func.attr in {'sin', 'cos', 'sqrt'} for node in ast.walk(tree))
