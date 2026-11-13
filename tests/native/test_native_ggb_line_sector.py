"""GGB ``Intersect(sector, line)`` (OD-048): GeoGebra answers with the points of
the arc only. Native ``intersect.line_sector`` keeps its contract (arc and
radii); an imported GGB construction binds its saved points to ``arc.*`` slots,
in both argument orders, with and without a number."""
import pytest

from animageo import native
from tests.native.ggb_synth import command, element, ggb_bytes, point
from tests.native.test_native_l5_ggb import NS, _check

Y0 = 2.539521835886975
ARC = (1.2576304667184355, 3.7971523026054106)         # y = x + Y0 meets the arc here, the radius at (0, Y0)
RADIUS_AND_ARC = [(0.0, 2.0), (12 ** 0.5, 2.0)]        # y = 2: a point of the radius, a point of the arc


def scene(line_through, inputs, outputs, saved):
    (px, py), (qx, qy) = line_through
    a, b, c = py - qy, qx - px, px * qy - qx * py
    body = (point('O', 0., 0.) + point('A', 4., 0.) + point('B', 0., 4.)
            + command('CircularSector', ['O', 'A', 'B'], ['sec']) + element('conicpart', 'sec')
            + point('P', px, py) + point('Q', qx, qy) + command('Line', ['P', 'Q'], ['g'])
            + element('line', 'g', extra=f'<coords x="{a!r}" y="{b!r}" z="{c!r}"/>')
            + command('Intersect', inputs, outputs)
            + ''.join(point(n, *xy) for n, xy in zip(outputs, saved)))
    doc, rep = native.from_ggb(ggb_bytes(body), id_namespace=NS)
    _check(doc, rep)
    return doc, {e['ggb_name']: e for e in rep['elements']}


def slot_of(doc, items, name):
    return doc['elements'][items[name]['native_ids'][0]]['producer']['slot']


@pytest.mark.parametrize('inputs', [['sec', 'g'], ['g', 'sec'], ['sec', 'g', '1'], ['g', 'sec', '1']])
def test_a_crossing_of_the_arc_is_an_arc_point(inputs):
    doc, items = scene(((0., Y0), (1., Y0 + 1.)), inputs, ['C'], [ARC])
    assert items['C']['category'] == 'editable' and items['C']['value_check'] == 'passed'
    assert slot_of(doc, items, 'C').startswith('arc.')
    ev = native.evaluate(doc)
    value = ev.elements[items['C']['native_ids'][0]]['value']
    assert (value['x'], value['y']) == pytest.approx(ARC)


@pytest.mark.parametrize('inputs', [['sec', 'g'], ['g', 'sec'], ['sec', 'g', '1'], ['g', 'sec', '1']])
def test_the_point_on_a_radius_is_not_imported_as_the_answer(inputs):
    # the line y = 2 meets a radius at (0, 2) and the arc at (sqrt 12, 2); GeoGebra gives the arc point
    doc, items = scene(((-5., 2.), (5., 2.)), inputs, ['C'], [RADIUS_AND_ARC[1]])
    assert items['C']['category'] == 'editable' and items['C']['value_check'] == 'passed'
    assert slot_of(doc, items, 'C').startswith('arc.')


@pytest.mark.parametrize('inputs', [['sec', 'g'], ['g', 'sec']])
def test_a_line_through_the_centre_gives_the_arc_point_not_the_centre(inputs):
    # y = x meets both radii at the centre and the arc at (2 sqrt 2, 2 sqrt 2)
    doc, items = scene(((0., 0.), (1., 1.)), inputs, ['C'], [(2 * 2 ** 0.5, 2 * 2 ** 0.5)])
    assert items['C']['value_check'] == 'passed'
    assert slot_of(doc, items, 'C').startswith('arc.')
