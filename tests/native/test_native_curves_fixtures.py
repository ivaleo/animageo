"""Parity fixtures of graphs and conics, registry 1.6 (``parity/v1/curves``,
``fixtures curves``; docs/native/kernel.md §14)."""
import json
import math

from animageo import native
from animageo.native import curves_fixtures
from animageo.native.cli import main
from animageo.native.parity import PARITY_FORMAT, verify

CURVES = curves_fixtures.DEFAULT_DIR
G2_OPS = {op for op, record in native.registry().ops.items() if record['since'] == '1.6'}


def _fixtures():
    return {p.name: json.loads(p.read_text(encoding='utf-8')) for p in sorted(CURVES.glob('*.json'))}


def _floats(value):
    if isinstance(value, float):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _floats(item)
    elif isinstance(value, list):
        for item in value:
            yield from _floats(item)


def test_fixtures_are_up_to_date_and_replay():
    assert curves_fixtures.check_fixtures() == []
    files, cases, mismatches = curves_fixtures.verify_fixtures()
    assert mismatches == []
    assert files == len(_fixtures()) and cases >= 100


def test_twelve_scenes_of_each_kind_and_every_new_op():
    fixtures = _fixtures()
    assert sum(name.startswith('fn_') for name in fixtures) >= 12
    assert sum(name.startswith('conic_') for name in fixtures) >= 12
    used = {op['op'] for f in fixtures.values() for op in f['document']['operations'].values()}
    assert G2_OPS <= used


def test_shape_of_the_parity_fixtures():
    for name, fixture in _fixtures().items():
        assert list(fixture) == ['format', 'id', 'registry', 'generatedBy', 'document', 'cases']
        assert fixture['format'] == PARITY_FORMAT and fixture['id'] + '.json' == name
        assert fixture['registry'] == native.__registry_version__
        assert fixture['document']['operationRegistryVersion'] == native.__registry_version__
        graphs = {e for e, el in fixture['document']['elements'].items() if el['type'] == 'function'}
        for case in fixture['cases']:
            assert set(case) <= {'name', 'inputs', 'scale', 'expect', 'checks', 'samples'}
            assert ('samples' in case) == bool(graphs)
            defined = {e for e in graphs if case['expect'][e]['state'] == 'defined'}
            assert set(case.get('samples', {})) == defined
            for rows in case.get('samples', {}).values():
                assert len(rows) in (0, 33) and all(len(row) == 2 for row in rows)   # 0: the domain is off view


def test_numbers_are_rounded():
    for fixture in _fixtures().values():
        for value in _floats(fixture['document']['inputs']):
            assert round(value, 6) == value
        for case in fixture['cases']:
            for value in _floats([case['expect'], case.get('samples', {}), case['scale']]):
                assert math.isfinite(value) and round(value, 9) == value
                assert math.copysign(1.0, value) > 0 or value != 0.0       # no -0.0


def test_parity_verify_reads_them(capsys):
    files, cases, mismatches = verify([CURVES])
    assert (files, mismatches) == (len(_fixtures()), [])
    assert main(['fixtures', 'verify', str(CURVES)]) == 0


def test_cli_check(tmp_path, capsys):
    assert main(['fixtures', 'curves', '--check']) == 0
    assert '0 mismatches' in capsys.readouterr().out
    assert main(['fixtures', 'curves', '-o', str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.glob('*.json')) == sorted(_fixtures())
    first = sorted(tmp_path.glob('*.json'))[0]
    data = json.loads(first.read_text(encoding='utf-8'))
    data['cases'][0]['scale'] += 1.0
    first.write_text(json.dumps(data), encoding='utf-8')
    (tmp_path / 'extra.json').write_text('{"format": "x", "cases": []}', encoding='utf-8')
    assert main(['fixtures', 'curves', '--check', '-o', str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert 'out of date' in out and 'not built here' in out


def test_samples_mismatch_is_reported():
    fixture = _fixtures()['fn_parabola_k.json']
    fixture['cases'][0]['samples']['f'][3][1] += 1e-3
    problems = curves_fixtures.verify_fixture(fixture)
    assert problems and all('samples f[3]' in p for p in problems)
