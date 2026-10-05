"""``native.from_construction``: the classic graph as a native document; keys and IDs (kernel stage L5, plan §3.3–§3.4)."""
import uuid

import pytest

from animageo import native
from animageo.geo.construction import Construction
from animageo.native.convert.keys import document_id, element_id
from animageo.native.convert.values import compare
from animageo.parsers.dsl import run

NS = uuid.UUID('0b7e7a43-34a1-4bd8-9f0e-3a4c2f6b9d21')

SCENE = """
A = Point(0, 0)
B = Point(4, 0)
C = Point(1, 3)
M = Midpoint(A, B)
k = Circle(M, C)
s = Segment(A, C)
t = Polygon(A, B, C)
r = Distance(A, B)
q = Circle(C, r)
g = Line(A, B)
E, F = Intersect(g, q)
"""


def _constr(code):
    c = Construction()
    run(c, code)
    return c


def _by_name(rep):
    return {e['name']: e for e in rep['elements']}


def test_a_scene_translates_whole():
    doc, rep = native.from_construction(_constr(SCENE), id_namespace=NS)
    assert rep['untranslated'] == [] and rep['warnings'] == []
    e = _by_name(rep)
    assert all(x['category'] == 'editable' and x['value_check'] == 'passed' for x in rep['elements'])
    assert e['M']['key'] == 'dsl:M' and e['M']['signature'] == 'midpoint_pp'
    assert e['M']['native_ids'] == [element_id(NS, 'dsl:M')]
    assert doc['documentId'] == document_id(NS)
    assert doc['bindings']['legacyNames'][e['M']['native_ids'][0]] == 'M'
    loaded = native.load(doc)
    assert native.validate(loaded) == []
    ev = native.evaluate(loaded)
    m = ev.elements[e['M']['native_ids'][0]]['value']
    assert (m['x'], m['y']) == pytest.approx((2.0, 0.0))
    # the intersection points keep the classic order (byValue)
    xs = sorted(ev.elements[e[n]['native_ids'][0]]['value']['x'] for n in ('E', 'F'))
    assert xs == pytest.approx([1 - (16 - 9) ** 0.5, 1 + (16 - 9) ** 0.5])
    # free inputs from the classic values
    assert doc['inputs'][e['C']['native_ids'][0]] == {'kind': 'point', 'value': [1.0, 3.0]}


def test_strict_and_partial():
    code = SCENE + 'h = Ellipse(A, B, C)\nP = Point(h)\nu = Segment(P, A)\n'
    with pytest.raises(native.ConvertError) as exc:
        native.from_construction(_constr(code), id_namespace=NS)
    assert {i['name'] for i in exc.value.items} == {'h', 'P', 'u'}
    doc, rep = native.from_construction(_constr(code), id_namespace=NS, mode='partial')
    e = _by_name(rep)
    assert (e['h']['category'], e['h']['reason']) == ('unsupported', 'no_registry_op')
    assert e['P']['category'] == e['u']['category'] == 'closure'
    assert e['u']['reason'] == 'depends_on_unsupported'
    assert {u['name'] for u in rep['untranslated']} == {'h', 'P', 'u'}
    assert all(not e[n]['native_ids'] for n in ('h', 'P', 'u'))
    assert native.validate(native.load(doc)) == []


def test_nothing_translates():
    doc, rep = native.from_construction(_constr('h = Ellipse(Point(0, 0), Point(2, 0), Point(0, 3))'),
                                        id_namespace=NS, mode='partial')
    assert doc is None or not any(x['category'] == 'editable' and x['name'] == 'h' for x in rep['elements'])


def test_custom_keys_and_origin():
    doc, rep = native.from_construction(_constr(SCENE), id_namespace=NS, key_of=lambda name: f'ggb:{name}_x',
                                        origin_of=lambda name: {'source': 'dsl', 'dslName': name})
    m = _by_name(rep)['M']
    assert m['key'] == 'ggb:M_x' and m['native_ids'] == [element_id(NS, 'ggb:M_x')]
    assert doc['elements'][m['native_ids'][0]]['origin'] == {'source': 'dsl', 'dslName': 'M'}
    assert native.validate(native.load(doc)) == []


def test_compare():
    assert compare({'kind': 'point', 'value': [0, 0]}, {'kind': 'point', 'value': [0, 1e-9]}, 1.0)[0] == 'passed'
    state, delta = compare({'kind': 'point', 'value': [0, 0]}, {'kind': 'point', 'value': [0, 0.1]}, 1.0)
    assert state == 'failed' and delta == pytest.approx(0.1)
    assert compare(None, {'kind': 'point', 'value': [0, 0]}, 1.0)[0] == 'not_checked'


# ── every row of the table on a general case (plan §3.10) ─────────────────

VARIANTS = {
    'p': ['Point(0.3, 0.2)', 'Point(4.1, 0.5)', 'Point(1.2, 3.3)', 'Point(5.2, 2.7)'],
    'c': ['Circle(Point(1, 1), 2.5)', 'Circle(Point(3, 1.5), 2)'],
    'l': ['Line(Point(-2, 0.5), Point(4, 1.7))', 'Line(Point(-1, 3), Point(3, -1.5))'],
    's': ['Segment(Point(-2, 1.2), Point(4, 0.3))', 'Segment(Point(-1, 3), Point(3, -1.5))'],
    'r': ['Ray(Point(-2, 2.0), Point(4, -1))', 'Ray(Point(-1, 3), Point(3, -1.5))'],
    'S': ['CircleSector(Point(1, 1), Point(3.5, 1), Point(1, 3.5))'],
    'C': ['CircleArc(Point(1, 1), Point(3.5, 1), Point(1, 3.5))'],
    'P': ['Polygon(Point(0, 0), Point(4, 0), Point(1, 3))'],
    'v': ['Vector(Point(0, 0), Point(1, 0.5))'],
    'i': ['2', '3'],
    'm': ['Distance(Point(0, 0), Point(1.5, 0))'],
    'A': ['AngleSize(0.7)'],
}
OVERRIDE = {
    'tangent_pc': 'X1, X2 = Tangent(Point(6, 1), Circle(Point(1, 1), 2.5))',
    'tangent_pci': 'X = Tangent(Point(6, 1), Circle(Point(1, 1), 2.5), 2)',
    'polygon_ppi': 'X = Polygon(Point(0, 0), Point(1, 0), 5)',
    'locus_pp': 'k = Circle(Point(0, 0), 2)\nM = Point(k)\nT = Midpoint(M, Point(3, 0))\nX = Locus(T, M)',
}
# a locus is a curve: its value is not compared (decision 12 — differs, value_unchecked)
UNCHECKED_ROWS = {'locus_pp'}


def _row_scene(key, row):
    if key in OVERRIDE:
        return OVERRIDE[key]
    used = {}
    args = []
    for n, ch in enumerate(key.rpartition('_')[2]):
        if ch == 'i' and row.get('index') and n == row['index']['input']:
            args.append('1')
            continue
        k = used.get(ch, 0)
        args.append(VARIANTS[ch][k % len(VARIANTS[ch])])
        used[ch] = k + 1
    out = row.get('outputs')
    target = 'X1, X2' if isinstance(out, dict) and 'byValue' in out and not row.get('index') else 'X'
    return f"{target} = {row['factory']}({', '.join(args)})"


def _op_rows():
    from animageo.native.convert import dsl_map
    return sorted((k, r) for k, r in dsl_map().commands.items() if 'op' in r and k != 'polygon')


@pytest.mark.parametrize('key, row', _op_rows(), ids=[k for k, _ in _op_rows()])
def test_every_row_translates_a_general_case(key, row):
    doc, rep = native.from_construction(_constr(_row_scene(key, row)), id_namespace=NS, mode='partial')
    outs = [e for e in rep['elements'] if e['name'].startswith('X')]
    assert outs and {e['signature'] for e in outs} == {key}
    expected = ('differs', 'value_unchecked') if key in UNCHECKED_ROWS else ('editable', None)
    assert all((e['category'], e.get('reason')) == expected for e in outs), outs
    assert native.validate(native.load(doc)) == []
    ops = {doc['operations'][doc['elements'][e['native_ids'][0]]['producer']['operationId']]['op'] for e in outs}
    assert ops == {row['op']}


@pytest.mark.parametrize('code, name', [
    # no intersection in the classic and in native: both undefined — the same value
    ('X = Intersect(Ray(Point(-2, 2.0), Point(4, 0.9)), Segment(Point(-2, 1.2), Point(4, 0.3)))', 'X'),
    ('X = Intersect(Line(Point(0, 0), Point(1, 0)), Line(Point(0, 1), Point(1, 1)))', 'X'),
    ('X = Intersect(Line(Point(-5, 9), Point(5, 9)), Circle(Point(0, 0), 2), 1)', 'X'),
    ('X = Tangent(Point(0.5, 0), Circle(Point(0, 0), 2), 1)', 'X'),
    ('X = Midpoint(Point(1, 1), Point(1, 1))', 'X'),
])
def test_degenerate_cases_agree(code, name):
    doc, rep = native.from_construction(_constr(code), id_namespace=NS, mode='partial')
    entry = _by_name(rep)[name]
    assert entry['category'] == 'editable' and entry['value_check'] == 'passed'


@pytest.mark.parametrize('code', [
    'k = Circle(Point(0, 0), 2)\nm = Circle(Point(2, 0), 2)\nE, F = Intersect(k, m)',
    'k = Circle(Point(0, 0), 2)\nm = Circle(Point(2, 0), 2)\nF, E = Intersect(m, k)',
    'g = Line(Point(-3, 1), Point(3, 1))\nk = Circle(Point(0, 0), 2)\nE, F = Intersect(k, g)',
    'k = Circle(Point(0, 0), 2)\nT1, T2 = Tangent(Point(5, 1), k)',
    'a = Line(Point(0, 0), Point(1, 0))\nb = Line(Point(0, 0), Point(1, 1))\nu, w = AngularBisector(a, b)',
])
def test_by_value_slots_follow_the_classic_outputs(code):
    c = _constr(code)
    doc, rep = native.from_construction(c, id_namespace=NS, mode='partial')
    ev = native.evaluate(native.load(doc))
    outs = [e for e in rep['elements'] if e.get('signature', '').startswith(('intersect', 'tangent', 'angular'))]
    assert len(outs) == 2 and all(e['category'] == 'editable' for e in outs)
    assert outs[0]['native_ids'] != outs[1]['native_ids']
    slots = {doc['elements'][e['native_ids'][0]]['producer']['slot'] for e in outs}
    assert len(slots) == 2
    for e in outs:
        assert ev.elements[e['native_ids'][0]]['state'] == 'defined'
