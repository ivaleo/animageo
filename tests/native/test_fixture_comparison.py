"""Float portability must not hide stale fixtures or structural changes."""
import copy
import json
import math

import pytest

from animageo.native._fixture_compare import same_fixture
from animageo.native.conditions import fixtures


@pytest.mark.parametrize(('old', 'new', 'same'), [
    (1.0, math.nextafter(1.0, math.inf), True),
    (0.0, 2**-52, True),  # cancellation near zero
    (1e6, 1e6 + 1e-7, True),  # relative tolerance
    (1.0, 1.0 + 1e-11, False),
    (1e6, 1e6 + 1e-5, False),
    (1, 2, False),
    (True, 1, False),
    (0, False, False),
    (True, True, True),
    (None, None, True),
    (math.inf, math.inf, False),
    (math.nan, math.nan, False),
    ({'reason': 'undefined'}, {'reason': 'degenerate'}, False),
    ({'state': 'defined'}, {'state': 'undefined'}, False),
    ({'A': 1.0}, {'B': 1.0}, False),
    ([1.0, 2.0], [2.0, 1.0], False),
    ([1.0], [1.0, 2.0], False),
    ([1.0], [1], True),  # the same JSON number
])
def test_only_float_roundoff_is_ignored(old, new, same):
    assert same_fixture(old, new) is same


def test_freshness_reports_missing_invalid_and_stale_files(tmp_path, monkeypatch):
    data = {'format': fixtures.RECIPES_FORMAT, 'generatedBy': 'animageo test',
            'cases': [{'name': 'one', 'expect': {'value': 1.0, 'state': 'defined', 'passed': 50}}]}
    monkeypatch.setattr(fixtures, 'build_fixtures', lambda: {'one.json': data})
    path = tmp_path / 'one.json'
    assert fixtures.check_fixtures(tmp_path) == [str(path)]
    path.write_text('{', encoding='utf-8')
    assert fixtures.check_fixtures(tmp_path) == [str(path)]
    for key, value in [('value', 1.0 + 1e-11), ('state', 'undefined'), ('passed', 49)]:
        stale = copy.deepcopy(data)
        stale['cases'][0]['expect'][key] = value
        path.write_text(json.dumps(stale), encoding='utf-8')
        assert fixtures.check_fixtures(tmp_path) == [str(path)], key
    portable = copy.deepcopy(data)
    portable['cases'][0]['expect']['value'] = math.nextafter(1.0, math.inf)
    path.write_text(json.dumps(portable), encoding='utf-8')
    assert fixtures.check_fixtures(tmp_path) == []
