"""Reproducible GGB import scenes consumed by Python and TypeScript parity."""
import json

import pytest

from animageo.native import parity
from animageo.native._fixture_compare import same_fixture
from tests.native.conftest import NATIVE_DIR, REPO_ROOT
from tests.native.test_native_ggb_inline import eid, imported
from tests.native.test_native_ggb_texts import text_body

NAMES = ('ggb_text_math',)


def import_scene(name):
    body = text_body()
    changes = [{'n': ('number', 4.25), 'A': ('point', [-2., 5.])}, {'n': ('number', -2.)}]
    doc, items = imported(body)
    assert all(e['category'] == 'editable' for e in items.values())
    doc['documentId'] = name
    cases = [{'name': 'saved'}] + [
        {'name': f'changed-{n}', 'inputs': {eid(items, key): {'kind': kind_, 'value': value}
                                           for key, (kind_, value) in change.items()}}
        for n, change in enumerate(changes, 1)]
    return {'format': 'animageo-parity/v1', 'id': name, 'document': doc, 'cases': cases}


@pytest.mark.parametrize('name', NAMES)
def test_scene_reproduces_source_and_expected_fixture(name):
    scene = json.loads((REPO_ROOT / 'tests/native/import/scenes' / (name + '.json')).read_text())
    assert scene == import_scene(name)
    fixture = json.loads((NATIVE_DIR / 'parity/v1/ggb' / (name + '.json')).read_text())
    assert same_fixture(fixture, parity.generate_scene(scene))
    assert parity.verify_fixture(fixture) == []
