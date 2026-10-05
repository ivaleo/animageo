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
    'P': ['Polygon(Point(0, 0), Point(4, 0), Point(1, 3))',
          'Polygon(Point(-1, -1), Point(3, -2), Point(2, 2), Point(-2, 1))'],
    'v': ['Vector(Point(0, 0), Point(1, 0.5))', 'Vector(Point(1, 2), Point(-1, 0.5))'],
    'i': ['2', '3'],
    'm': ['Distance(Point(0, 0), Point(1.5, 0))', 'Distance(Point(1, 1), Point(3, 2))'],
    'A': ['AngleSize(0.7)', 'AngleSize(2.4)'],
}
VARIANTS['S'].append('CircleSector(Point(-1, 0), Point(1.5, -1), Point(-2, 2))')
VARIANTS['C'].append('CircleArc(Point(-1, 0), Point(1.5, -1), Point(-2, 2))')
OVERRIDE = {
    'tangent_pc': 'X1, X2 = Tangent(Point(6, 1), Circle(Point(1, 1), 2.5))',
    'tangent_pci': 'X = Tangent(Point(6, 1), Circle(Point(1, 1), 2.5), 2)',
    'polygon_ppi': 'X = Polygon(Point(0, 0), Point(1, 0), 5)',
    'locus_pp': 'k = Circle(Point(0, 0), 2)\nM = Point(k)\nT = Midpoint(M, Point(3, 0))\nX = Locus(T, M)',
}
# a locus is a curve: its value is not compared (decision 12 — differs, value_unchecked)
UNCHECKED_ROWS = {'locus_pp'}


def _row_scene(key, row, shift=0):
    """The scene of a row: ``shift = 0`` the general case, ``1`` another
    configuration (the next variant of every input; the other output of an
    indexed row)."""
    overrides = OTHER if shift else OVERRIDE
    if key in overrides:
        return overrides[key]
    used = {}
    args = []
    for n, ch in enumerate(key.rpartition('_')[2]):
        if ch == 'i' and row.get('index') and n == row['index']['input']:
            args.append(str(1 + shift))
            continue
        k = used.get(ch, 0)
        args.append(VARIANTS[ch][(k + shift) % len(VARIANTS[ch])])
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


# ── three cases per row: general, another configuration, degenerate (plan §3.10, 1.10.0a2) ──
#
# The general case is above. «Another configuration» takes the next variant of
# every input — for a byValue row the classic outputs meet the slots in
# another order (a sector, tangents), for an indexed row it is the other
# output. «Degenerate» keeps the inputs well-formed and puts them in a
# degenerate configuration (coincident or collinear points, parallel lines,
# a tangency, a zero factor or vector); a row without one names the reason.

OTHER = {
    'tangent_pc': 'X1, X2 = Tangent(Point(-3, 4), Circle(Point(0, 0), 2))',
    'tangent_pci': 'X = Tangent(Point(-3, 4), Circle(Point(0, 0), 2), 2)',
    'polygon_ppi': 'X = Polygon(Point(2, 1), Point(-1, 0), 7)',
    'locus_pp': 'k = Circle(Point(1, 1), 3)\nM = Point(k)\nT = Midpoint(M, Point(-2, 0))\nX = Locus(T, M)',
}
# the rows outside the generator: (general, another configuration)
OWN_SCENES = {
    'polygon': ('X = Polygon(Point(0, 0), Point(4, 0), Point(1, 3))',
                'X = Polygon(Point(-1, -1), Point(3, -2), Point(2, 2), Point(-2, 1))'),
    'point_ii': ('X = Point(0.3, 0.2)', 'X = Point(-2, 5)'),
    'angle_size_i': ('X = AngleSize(0.7)', 'X = AngleSize(5)'),
}

_K = 'Circle(Point(0, 0), 2)'
_LX = 'Line(Point(0, 0), Point(4, 0))'
_SX = 'Segment(Point(0, 0), Point(4, 0))'
_RX = 'Ray(Point(0, 0), Point(4, 0))'
_FLAT = 'Polygon(Point(0, 0), Point(1, 1), Point(2, 2))'
_TRI = 'Polygon(Point(0, 0), Point(4, 0), Point(1, 3))'
_ARC0 = 'CircleArc(Point(1, 1), Point(3, 1), Point(5, 1))'          # a zero angle
_SECT = 'CircleSector(Point(0, 0), Point(2, 0), Point(0, 2))'
_ZV = 'Vector(Point(2, 2), Point(2, 2))'
_ZM = 'Distance(Point(2, 2), Point(2, 2))'
_TOUCH = 'Point(-5, 2), Point(5, 2)'                                  # a line touching _K at (0, 2)
_FAR = 'Line(Point(-5, 9), Point(5, 9))'
_PAR = 'Point(0, 2), Point(4, 2)'                                     # parallel to _LX

DEGENERATE = {
    'angle_ppp': 'X = Angle(Point(4, 1), Point(4, 1), Point(1, 3))',
    'angle_size_i': 'X = AngleSize(0)',
    'angular_bisector_ll': f'X1, X2 = AngularBisector({_LX}, Line({_PAR}))',
    'angular_bisector_ppp': 'X = AngularBisector(Point(1, 1), Point(1, 1), Point(4, 2))',
    'angular_bisector_ss': f'X1, X2 = AngularBisector({_SX}, Segment({_PAR}))',
    'arc_cpp': f'X = Arc({_K}, Point(2, 0), Point(2, 0))',
    'area_P': f'X = Area({_FLAT})',
    'centroid_P': f'X = Centroid({_FLAT})',
    'circle_arc_ppp': 'X = CircleArc(Point(1, 1), Point(1, 1), Point(1, 3))',
    'circle_pi': 'X = Circle(Point(1, 1), 0)',
    'circle_pm': f'X = Circle(Point(1, 1), {_ZM})',
    'circle_pp': 'X = Circle(Point(1, 1), Point(1, 1))',
    'circle_ppp': 'X = Circle(Point(0, 0), Point(1, 1), Point(2, 2))',
    'circle_ps': 'X = Circle(Point(1, 1), Segment(Point(2, 2), Point(2, 2)))',
    'circle_sector_ppA': 'X = CircleSector(Point(1, 1), Point(3, 1), AngleSize(0))',
    'circle_sector_ppi': 'X = CircleSector(Point(1, 1), Point(3, 1), 0)',
    'circle_sector_ppp': 'X = CircleSector(Point(1, 1), Point(1, 1), Point(1, 3))',
    'circular_arc_ppp': 'X = CircularArc(Point(1, 1), Point(1, 1), Point(1, 3))',
    'circular_sector_ppA': 'X = CircularSector(Point(1, 1), Point(3, 1), AngleSize(0))',
    'circular_sector_ppi': 'X = CircularSector(Point(1, 1), Point(3, 1), 0)',
    'circular_sector_ppp': 'X = CircularSector(Point(1, 1), Point(1, 1), Point(1, 3))',
    'circumcircle_arc_ppp': 'X = CircumcircleArc(Point(0, 0), Point(1, 1), Point(2, 2))',
    'circumcircle_sector_ppp': 'X = CircumcircleSector(Point(0, 0), Point(1, 1), Point(2, 2))',
    'circumcircular_arc_ppp': 'X = CircumcircularArc(Point(0, 0), Point(1, 1), Point(2, 2))',
    'circumcircular_sector_ppp': 'X = CircumcircularSector(Point(0, 0), Point(1, 1), Point(2, 2))',
    'closest_point_cp': f'X = ClosestPoint({_K}, Point(0, 0))',
    'closest_point_lp': f'X = ClosestPoint({_LX}, Point(1, 0))',
    'closest_point_rp': f'X = ClosestPoint({_RX}, Point(-2, 1))',
    'closest_point_sp': f'X = ClosestPoint({_SX}, Point(6, 1))',
    'dilate_Pip': f'X = Dilate({_TRI}, 0, Point(1, 1))',
    'dilate_Pmp': f'X = Dilate({_TRI}, {_ZM}, Point(1, 1))',
    'dilate_cip': f'X = Dilate({_K}, 0, Point(1, 1))',
    'dilate_cmp': f'X = Dilate({_K}, {_ZM}, Point(1, 1))',
    'dilate_lip': f'X = Dilate({_LX}, 0, Point(1, 1))',
    'dilate_lmp': f'X = Dilate({_LX}, {_ZM}, Point(1, 1))',
    'dilate_pip': 'X = Dilate(Point(3, 2), 0, Point(1, 1))',
    'dilate_pmp': f'X = Dilate(Point(3, 2), {_ZM}, Point(1, 1))',
    'dilate_sip': f'X = Dilate({_SX}, 0, Point(1, 1))',
    'dilate_smp': f'X = Dilate({_SX}, {_ZM}, Point(1, 1))',
    'distance_cp': f'X = Distance({_K}, Point(2, 0))',
    'distance_lp': f'X = Distance({_LX}, Point(1, 0))',
    'distance_pc': f'X = Distance(Point(2, 0), {_K})',
    'distance_pl': f'X = Distance(Point(1, 0), {_LX})',
    'distance_pp': 'X = Distance(Point(1, 1), Point(1, 1))',
    'distance_pr': f'X = Distance(Point(-2, 1), {_RX})',
    'distance_ps': f'X = Distance(Point(6, 0), {_SX})',
    'distance_rp': f'X = Distance({_RX}, Point(-2, 1))',
    'distance_sp': f'X = Distance({_SX}, Point(6, 0))',
    'incircle_ppp': 'X = Incircle(Point(0, 0), Point(1, 1), Point(2, 2))',
    'intersect_Sl': f'X1, X2 = Intersect({_SECT}, {_FAR})',
    'intersect_Sli': f'X = Intersect({_SECT}, {_FAR}, 1)',
    'intersect_cc': 'X1, X2 = Intersect(Circle(Point(0, 0), 2), Circle(Point(0, 0), 3))',
    'intersect_cci': 'X = Intersect(Circle(Point(0, 0), 2), Circle(Point(0, 0), 3), 1)',
    'intersect_cl': f'X1, X2 = Intersect({_K}, Line({_TOUCH}))',
    'intersect_cli': f'X = Intersect({_K}, Line({_TOUCH}), 2)',
    'intersect_cr': f'X1, X2 = Intersect({_K}, Ray({_TOUCH}))',
    'intersect_cri': f'X = Intersect({_K}, Ray({_TOUCH}), 2)',
    'intersect_cs': f'X1, X2 = Intersect({_K}, Segment({_TOUCH}))',
    'intersect_csi': f'X = Intersect({_K}, Segment({_TOUCH}), 2)',
    'intersect_lS': f'X1, X2 = Intersect({_FAR}, {_SECT})',
    'intersect_lSi': f'X = Intersect({_FAR}, {_SECT}, 1)',
    'intersect_lc': f'X1, X2 = Intersect(Line({_TOUCH}), {_K})',
    'intersect_lci': f'X = Intersect(Line({_TOUCH}), {_K}, 2)',
    'intersect_ll': f'X = Intersect({_LX}, Line({_PAR}))',
    'intersect_lr': f'X = Intersect({_LX}, Ray({_PAR}))',
    'intersect_ls': f'X = Intersect({_LX}, Segment({_PAR}))',
    'intersect_rc': f'X1, X2 = Intersect(Ray({_TOUCH}), {_K})',
    'intersect_rci': f'X = Intersect(Ray({_TOUCH}), {_K}, 2)',
    'intersect_rl': f'X = Intersect({_RX}, Line({_PAR}))',
    'intersect_rr': f'X = Intersect({_RX}, Ray({_PAR}))',
    'intersect_rs': f'X = Intersect({_RX}, Segment({_PAR}))',
    'intersect_sc': f'X1, X2 = Intersect(Segment({_TOUCH}), {_K})',
    'intersect_sci': f'X = Intersect(Segment({_TOUCH}), {_K}, 2)',
    'intersect_sl': f'X = Intersect({_SX}, Line({_PAR}))',
    'intersect_sr': f'X = Intersect({_SX}, Ray({_PAR}))',
    'intersect_ss': f'X = Intersect({_SX}, Segment({_PAR}))',
    'length_C': f'X = Length({_ARC0})',
    'length_s': 'X = Length(Segment(Point(1, 1), Point(1, 1)))',
    'length_v': f'X = Length({_ZV})',
    'line_bisector_pp': 'X = LineBisector(Point(1, 1), Point(1, 1))',
    'line_bisector_s': 'X = LineBisector(Segment(Point(1, 1), Point(1, 1)))',
    'line_pl': f'X = Line(Point(1, 0), {_LX})',
    'line_pp': 'X = Line(Point(1, 1), Point(1, 1))',
    'line_pr': f'X = Line(Point(1, 0), {_RX})',
    'line_ps': f'X = Line(Point(1, 0), {_SX})',
    'line_s': 'X = Line(Segment(Point(1, 1), Point(1, 1)))',
    'midpoint_pp': 'X = Midpoint(Point(1, 1), Point(1, 1))',
    'midpoint_s': 'X = Midpoint(Segment(Point(1, 1), Point(1, 1)))',
    'mirror_cl': f'X = Mirror({_K}, Line(Point(-1, -1), Point(1, 1)))',
    'mirror_cp': f'X = Mirror({_K}, Point(0, 0))',
    'mirror_ll': f'X = Mirror({_LX}, {_LX})',
    'mirror_lp': f'X = Mirror({_LX}, Point(1, 0))',
    'mirror_ls': f'X = Mirror({_LX}, {_SX})',
    'mirror_pl': f'X = Mirror(Point(1, 0), {_LX})',
    'mirror_pp': 'X = Mirror(Point(1, 1), Point(1, 1))',
    'mirror_ps': f'X = Mirror(Point(6, 0), {_SX})',
    'orthogonal_line_pl': f'X = OrthogonalLine(Point(1, 0), {_LX})',
    'orthogonal_line_pr': f'X = OrthogonalLine(Point(-1, 0), {_RX})',
    'orthogonal_line_ps': f'X = OrthogonalLine(Point(6, 0), {_SX})',
    'perimeter_P': f'X = Perimeter({_FLAT})',
    'perpendicular_bisector_pp': 'X = PerpendicularBisector(Point(1, 1), Point(1, 1))',
    'perpendicular_bisector_s': 'X = PerpendicularBisector(Segment(Point(1, 1), Point(1, 1)))',
    'perpendicular_line_pl': f'X = PerpendicularLine(Point(1, 0), {_LX})',
    'perpendicular_line_pr': f'X = PerpendicularLine(Point(-1, 0), {_RX})',
    'perpendicular_line_ps': f'X = PerpendicularLine(Point(6, 0), {_SX})',
    'point_C': f'X = Point({_ARC0})',
    'point_P': f'X = Point({_FLAT})',
    'point_pv': f'X = Point(Point(1, 1), {_ZV})',
    'point_r': 'X = Point(Ray(Point(1, 1), Point(1, 1)))',
    'point_s': 'X = Point(Segment(Point(1, 1), Point(1, 1)))',
    'polygon': f'X = {_FLAT}',
    'polygon_ppi': 'X = Polygon(Point(1, 1), Point(1, 1), 5)',
    'ray_pp': 'X = Ray(Point(1, 1), Point(1, 1))',
    'ray_pv': f'X = Ray(Point(1, 1), {_ZV})',
    'reflect_cl': f'X = Reflect({_K}, Line(Point(-1, -1), Point(1, 1)))',
    'reflect_cp': f'X = Reflect({_K}, Point(0, 0))',
    'reflect_ll': f'X = Reflect({_LX}, {_LX})',
    'reflect_lp': f'X = Reflect({_LX}, Point(1, 0))',
    'reflect_ls': f'X = Reflect({_LX}, {_SX})',
    'reflect_pl': f'X = Reflect(Point(1, 0), {_LX})',
    'reflect_pp': 'X = Reflect(Point(1, 1), Point(1, 1))',
    'reflect_ps': f'X = Reflect(Point(6, 0), {_SX})',
    'rotate_lAp': f'X = Rotate({_LX}, AngleSize(0), Point(1, 0))',
    'rotate_pAp': 'X = Rotate(Point(1, 1), AngleSize(0.7), Point(1, 1))',
    'rotate_pip': 'X = Rotate(Point(1, 1), 2, Point(1, 1))',
    'rotate_vAp': f'X = Rotate({_ZV}, AngleSize(0.7), Point(1, 1))',
    'segment_pp': 'X = Segment(Point(1, 1), Point(1, 1))',
    'semicircle_pp': 'X = Semicircle(Point(1, 1), Point(1, 1))',
    'tangent_pc': f'X1, X2 = Tangent(Point(2, 0), {_K})',
    'tangent_pci': f'X = Tangent(Point(2, 0), {_K}, 2)',
    'translate_cv': f'X = Translate({_K}, {_ZV})',
    'translate_pv': f'X = Translate(Point(1, 1), {_ZV})',
    'translate_sv': f'X = Translate({_SX}, {_ZV})',
    'vector_pp': 'X = Vector(Point(1, 1), Point(1, 1))',
}
_NO_CIRCLE = 'the only degenerate circle — radius 0 — is undefined in the classic, so the command never gets one'
NO_DEGENERACY = {
    'center_c': _NO_CIRCLE,
    'circumference_c': _NO_CIRCLE,
    'length_c': _NO_CIRCLE,
    'point_c': _NO_CIRCLE,
    'radius_c': _NO_CIRCLE,
    'point_l': 'a line through two coincident points is undefined in the classic, so Point(line) never gets one',
    'point_ii': 'a free point has no degenerate configuration',
    'locus_pp': 'a locus is never compared (decision 12): differs with value_unchecked in every configuration',
}
# Degenerate configurations where the classic and the kernel disagree. They are
# reported as differs — never editable — so «zero falsely editable» holds:
# at a tangency the classic gives one point (the second output is undefined),
# the kernel a double point; a zero factor, a zero vector of a ray, coincident
# points of a regular polygon or a semicircle — the classic builds a point-like
# figure, the kernel is undefined; parallel lines — the classic leaves both
# bisectors undefined, the kernel gives the midline; a flat polygon — the
# classic averages the vertices, the kernel's centroid is undefined.
DEGENERATE_DIFFERS = {
    'angle_ppp', 'angular_bisector_ll', 'angular_bisector_ss', 'centroid_P',
    'dilate_Pip', 'dilate_Pmp', 'dilate_lip', 'dilate_lmp', 'dilate_pip', 'dilate_pmp', 'dilate_sip', 'dilate_smp',
    'intersect_cl', 'intersect_cli', 'intersect_cr', 'intersect_cri', 'intersect_cs', 'intersect_csi',
    'intersect_lc', 'intersect_lci', 'intersect_rc', 'intersect_rci', 'intersect_sc', 'intersect_sci',
    'point_r', 'polygon_ppi', 'ray_pp', 'ray_pv', 'semicircle_pp', 'tangent_pc', 'tangent_pci',
}


def _all_rows():
    from animageo.native.convert import dsl_map
    return {k: r for k, r in dsl_map().commands.items() if 'op' in r or 'free' in r}


def _outputs(code, key):
    doc, rep = native.from_construction(_constr(code), id_namespace=NS, mode='partial')
    outs = [e for e in rep['elements'] if e['name'].startswith('X')]
    assert outs and {e['signature'] for e in outs} == {key}, outs
    assert native.validate(native.load(doc)) == []
    return doc, outs


def test_every_row_has_three_cases():
    rows = _all_rows()
    generated = {k for k, _ in _op_rows()}
    assert set(rows) == generated | set(OWN_SCENES)
    assert set(DEGENERATE) | set(NO_DEGENERACY) == set(rows)
    assert not set(DEGENERATE) & set(NO_DEGENERACY)
    assert DEGENERATE_DIFFERS <= set(DEGENERATE)
    for key, row in _op_rows():
        assert _row_scene(key, row, 1) != _row_scene(key, row), key


@pytest.mark.parametrize('key', sorted(OWN_SCENES))
def test_the_rows_outside_the_generator(key):
    for code in OWN_SCENES[key]:
        _, outs = _outputs(code, key)
        assert all((e['category'], e['value_check']) == ('editable', 'passed') for e in outs)


@pytest.mark.parametrize('key, row', _op_rows(), ids=[k for k, _ in _op_rows()])
def test_every_row_translates_another_configuration(key, row):
    doc, outs = _outputs(_row_scene(key, row, 1), key)
    expected = ('differs', 'value_unchecked') if key in UNCHECKED_ROWS else ('editable', None)
    assert all((e['category'], e.get('reason')) == expected for e in outs), outs
    slots = [doc['elements'][e['native_ids'][0]]['producer']['slot'] for e in outs]
    assert len(set(slots)) == len(slots)          # byValue: each classic output its own slot
    if isinstance(row.get('outputs'), dict) and 'byValue' in row['outputs']:
        ev = native.evaluate(native.load(doc))     # the slots were matched by a value, not by an undefined one
        assert all(ev.elements[e['native_ids'][0]]['state'] == 'defined' for e in outs)


@pytest.mark.parametrize('key', sorted(DEGENERATE))
def test_every_row_on_a_degenerate_configuration(key):
    _, outs = _outputs(DEGENERATE[key], key)
    for e in outs:
        assert e['category'] in ('editable', 'differs'), e
        assert (e['category'] == 'editable') == (e['value_check'] == 'passed'), e
    differs = any(e['category'] == 'differs' for e in outs)
    assert differs == (key in DEGENERATE_DIFFERS), outs
