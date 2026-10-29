"""Reproducible GGB import scenes consumed by Python and TypeScript parity."""
import json

import pytest

from animageo.native import parity
from animageo.native._fixture_compare import same_fixture
from tests.native.conftest import NATIVE_DIR, REPO_ROOT
from tests.native.ggb_synth import command, point
from tests.native.ggb_imp5 import slider_body, labels_body, layers_body
from tests.native.test_native_ggb_conics import conic_branch_body, equation_body, regular_body
from tests.native.test_native_ggb_inline import eid, imported
from tests.native.test_native_ggb_texts import text_body

NAMES = ('ggb_text_math', 'ggb_conic_ellipse', 'ggb_conic_hyperbola', 'ggb_conic_parabola',
         'ggb_conic_equation', 'ggb_regular_outputs', 'ggb_axis_projection',
         'ggb_slider', 'ggb_labels', 'ggb_layers')


def import_scene(name):
    kind = name.rsplit('_', 1)[-1].capitalize()
    if name == 'ggb_slider':
        body = slider_body()
        changes = [{'n': ('number', -10.)}, {'n': ('number', 4.)}, {'n': ('number', 10.)}]
    elif name in ('ggb_labels', 'ggb_layers'):
        body = labels_body() if name == 'ggb_labels' else layers_body()
        changes = [{'B': ('point', [6., 0.])}, {'A': ('point', [-1., 2.])}]
    elif name == 'ggb_text_math':
        body = text_body()
        changes = [{'n': ('number', 4.25), 'A': ('point', [-2., 5.])}, {'n': ('number', -2.)}]
    elif name == 'ggb_conic_equation':
        body, changes = equation_body(), [{'a': ('number', 2.)}, {'a': ('number', 0.)}]
    elif name == 'ggb_regular_outputs':
        body = regular_body(True).replace(' a5="C" a6="D"', '').replace(point('C', 2., 2.), '').replace(point('D', 0., 2.), '')
        changes = [{'B': ('point', [3., 0.])}, {'B': ('point', [0., 2.])}]
    elif name == 'ggb_axis_projection':
        body = command('Point', ['xAxis'], ['P']) + point('P', 3., 0.)
        changes = [{'P': ('pathParameter', -2.)}, {'P': ('pathParameter', 5.)}]
    else:
        body = conic_branch_body(kind)
        y = 2. if kind == 'Hyperbola' else -1. if kind == 'Parabola' else 3.
        changes = [{'A': ('point', [-5., .5]), 'B': ('point', [5., .5])},
                   {'A': ('point', [-5., y]), 'B': ('point', [5., y])}]
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
