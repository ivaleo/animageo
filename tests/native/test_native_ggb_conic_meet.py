"""GGB ``Intersect`` of two conics, a conic and a circle or an arc → ``intersect.conic_conic``
(registry 1.8): the slots are bound by the saved values, the index too."""
import math

import pytest

from animageo import native
from animageo.native.convert.mapping import dsl_map
from tests.native.ggb_synth import command, point
from tests.native.test_native_ggb_conics import conic_body, matrix
from tests.native.test_native_ggb_inline import eid, imported
from tests.native.test_native_ggb_output_slots import circle

# x²/9 + y²/4 = 1 and x² + y² = 6.25: x² = 4.05, y² = 2.2
X = math.sqrt(4.05)
Y = math.sqrt(2.2)
SAVED = {'P': (X, Y), 'Q': (-X, Y), 'R': (-X, -Y), 'S': (X, -Y)}


def body(args, outputs):
    return (conic_body('Ellipse') + point('O', 0., 0.) + circle('k', 2.5)
            + command('Intersect', args, outputs) + ''.join(point(n, *SAVED[n]) for n in outputs))


@pytest.mark.parametrize('key', ['KK', 'KKi', 'Kc', 'Kci', 'cK', 'cKi', 'KC', 'KCi', 'CK', 'CKi'])
def test_the_map_sends_conic_pairs_to_conic_conic(key):
    row = dsl_map().commands['intersect_' + key]
    assert row['op'] == 'intersect.conic_conic'
    assert row['outputs'] == {'byValue': ['first', 'second', 'third', 'fourth']}
    assert row['args'] == ['first', 'second'] + ([None] if key.endswith('i') else [])
    assert row.get('index') == ({'input': 2, 'base': 1} if key.endswith('i') else None)
    assert 'intersect.conic_conic' not in dsl_map().ops_without_classic


@pytest.mark.parametrize('args', [['q', 'k'], ['k', 'q']])
def test_all_points_are_bound_by_value(args):
    doc, items = imported(body(args, ['P', 'Q', 'R', 'S']))
    assert all(e['category'] == 'editable' and e.get('value_check', 'passed') == 'passed' for e in items.values())
    producer = doc['operations'][doc['elements'][eid(items, 'P')]['producer']['operationId']]
    assert producer['op'] == 'intersect.conic_conic'
    assert doc['operationRegistryVersion'] == '1.8'
    assert native.validate(doc) == []
    ev = native.evaluate(doc)
    for name, (x, y) in SAVED.items():
        assert ev.elements[eid(items, name)]['value'] == pytest.approx(dict(x=x, y=y))


@pytest.mark.parametrize('args', [['q', 'c'], ['c', 'q']])
def test_the_bound_slots_follow_the_motion(args):
    # x²/9 + y²/4 = 1 and (x − 3)² + y² = 9: 5x² − 54x + 36 = 0
    x = (54 - math.sqrt(54 * 54 - 720)) / 10
    y = math.sqrt(6 * x - x * x)
    b = (conic_body('Ellipse') + point('C', 3., 0.) + command('Circle', ['C', '3'], ['c'])
         + matrix('c', [1, 1, 0, 0, -3, 0]) + command('Intersect', args, ['P', 'Q'])
         + point('P', x, -y) + point('Q', x, y))
    doc, items = imported(b)
    assert all(e['category'] == 'editable' for e in items.values())
    for cy in (0.1, 0.3, -0.2, 0.):
        ev = native.evaluate(doc, inputs={eid(items, 'C'): {'kind': 'point', 'value': [3., cy]}})
        p, q = (ev.elements[eid(items, n)]['value'] for n in ('P', 'Q'))
        assert p['y'] < 0 < q['y']


@pytest.mark.parametrize('n,name', [(1, 'P'), (2, 'R'), (4, 'S')])
def test_an_index_is_bound_by_the_saved_value(n, name):
    b = (conic_body('Ellipse') + point('O', 0., 0.) + circle('k', 2.5)
         + command('Intersect', ['q', 'k', str(n)], ['Z']) + point('Z', *SAVED[name]))
    doc, items = imported(b)
    assert items['Z']['category'] == 'editable'
    assert native.evaluate(doc).elements[eid(items, 'Z')]['value'] == pytest.approx(dict(zip('xy', SAVED[name])))


def test_two_conics():
    # x²/9 + y²/4 = 1 and x²/4 − y² = 1 (foci ±√5 through (2, 0)): x² = 7.2, y² = 0.8
    hyper = (command('Hyperbola', ['F', 'G', 'H'], ['h']) + matrix('h', [1, -4, -4, 0, 0, 0]))
    x2 = (1 + 1 / 4) / (1 / 9 + 1 / 16)
    x = math.sqrt(x2)
    y = math.sqrt(x2 / 4 - 1)
    b = (conic_body('Ellipse') + point('H', 2., 0.) + hyper
         + command('Intersect', ['q', 'h'], ['P', 'Q', 'R', 'S'])
         + point('P', x, y) + point('Q', -x, y) + point('R', -x, -y) + point('S', x, -y))
    doc, items = imported(b)
    assert all(e['category'] == 'editable' for e in items.values()), {k: (e['category'], e.get('reason'))
                                                                      for k, e in items.items()}
    ev = native.evaluate(doc)
    assert ev.elements[eid(items, 'R')]['value'] == pytest.approx(dict(x=-x, y=-y))
