"""Typed import fixtures reproduce source files, refusal reports and states."""
import json

import pytest

from animageo.native import parity
from animageo.native._fixture_compare import same_fixture
from tests.native.ggb_expression_fixtures import NAMES, ROOT, build, same_archive


@pytest.mark.parametrize('name', NAMES)
def test_generated_source_and_parity(name):
    raw, scene, fixture = build(name)
    assert same_archive((ROOT / 'tests/native/import/expressions' / f'{name}.ggb').read_bytes(), raw)
    assert json.loads((ROOT / 'tests/native/import/scenes' / f'{name}.json').read_text()) == scene
    saved = json.loads((ROOT / 'animageo/native/parity/v1/ggb' / f'{name}.json').read_text())
    assert same_fixture(saved, fixture)
    assert parity.verify_fixture(saved) == []
