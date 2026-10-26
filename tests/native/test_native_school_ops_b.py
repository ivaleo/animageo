"""School constructions, circular segments and export caps (1.11.0rc12)."""
import math
import xml.etree.ElementTree as ET

import pytest

from animageo import native
from animageo.native.kernel.bridge import build_construction, from_classic
from animageo.native.kernel.paths import frame, point_at, project, distance_to_path
from animageo.native.kernel.relations import SplitMix64
from tests.native.conftest import DocBuilder, num, ref, ref_list


def call(b, name, args, type_, slot=None, element='result'):
    return b.op('op_' + element, name, args, [(slot or type_, element, type_)])


def triangle(name, points=((0, 0), (4, 0), (0, 3)), polygon=False):
    b = DocBuilder(registry_version='1.6')
    for k, xy in zip('ABC', points):
        b.free(k, *xy)
    b.polygon('T', 'A', 'B', 'C')
    args = {'polygon': ref('T')} if polygon else {k.lower(): ref(k) for k in 'ABC'}
    type_ = 'circle' if name == 'circle.nine_point' else 'line'
    return call(b, name, args, type_)


def value(b, element='result'):
    result = native.evaluate(b.doc).elements[element]
    assert result['state'] == 'defined', result
    return result['value']


def reason(b, expected):
    rec = native.evaluate(b.doc).elements['result']
    assert (rec['state'], rec['reason']) == ('undefined', expected), rec


def tangent(c2=(6, 0), radii=(2, 1), kind='external', index=0):
    b = DocBuilder(registry_version='1.6').free('O', 0, 0).free('P', *c2)
    for e, center, radius in zip(('c', 'd'), ('O', 'P'), radii):
        call(b, 'circle.center_radius', {'center': ref(center), 'radius': num(radius)}, 'circle', element=e)
    call(b, 'line.common_tangents', {'first': ref('c'), 'second': ref('d'),
                                    'kind': {'kind': 'string', 'value': kind}, 'index': num(index)}, 'line')
    return b


@pytest.mark.parametrize('polygon', [False, True])
def test_nine_point_and_euler_right_triangle(polygon):
    circle = value(triangle('circle.nine_point', polygon=polygon))
    assert circle['c'] == [1, 0.75]
    assert circle['r'] == 1.25
    line = value(triangle('line.euler', polygon=polygon))
    assert line['p'] == pytest.approx([0, 0])
    assert line['dir'] == pytest.approx([-0.8, -0.6])


@pytest.mark.parametrize('polygon', [False, True])
@pytest.mark.parametrize('points', [((0, 0), (2, 0), (4, 0)), ((1, 1), (1, 1), (1, 1))])
@pytest.mark.parametrize('name', ['circle.nine_point', 'line.euler'])
def test_degenerate_triangle(name, points, polygon):
    reason(triangle(name, points, polygon), 'collinear_points')


def test_equilateral_centers_and_tolerance():
    points = ((-1, 0), (1, 0), (0, math.sqrt(3)))
    reason(triangle('line.euler', points), 'coincident_points')
    circle = value(triangle('circle.nine_point', points))
    assert circle['c'] == pytest.approx([0, math.sqrt(3) / 3])
    assert circle['r'] == pytest.approx(1 / math.sqrt(3))
    # The undefined branch is based on kernel tolerance, not exact equality.
    reason(triangle('line.euler', ((-1, 0), (1, 0), (0, math.sqrt(3) + 1e-10))), 'coincident_points')
    assert value(triangle('line.euler', ((-1, 0), (1, 0), (0, math.sqrt(3) + 1e-5))))


@pytest.mark.parametrize('kind', ['external', 'internal'])
@pytest.mark.parametrize('index', [0, 1])
def test_common_tangent_geometry(kind, index):
    line = value(tangent(kind=kind, index=index))
    px, py = line['p']
    dx, dy = line['dir']
    assert math.hypot(dx, dy) == pytest.approx(1)
    assert px * dx + py * dy == pytest.approx(0)
    assert abs(px * dy - py * dx) == pytest.approx(2)
    assert abs((6 - px) * dy + py * dx) == pytest.approx(1)


def test_equal_radius_external_tangents():
    for i, y in enumerate((2, -2)):
        assert value(tangent(radii=(2, 2), index=i))['p'] == pytest.approx([0, y])


@pytest.mark.parametrize('c2,kind,count', [((6, 0), 'external', 2), ((6, 0), 'internal', 2),
    ((2, 0), 'external', 2), ((2, 0), 'internal', 0), ((3, 0), 'internal', 1),
    ((1, 0), 'external', 1), ((1, 0), 'internal', 0), ((0.5, 0), 'external', 0),
    ((0.5, 0), 'internal', 0), ((0, 0), 'external', 0)])
def test_common_tangent_branch_counts(c2, kind, count):
    for index in (0, 1):
        b = tangent(c2, kind=kind, index=index)
        if index < count:
            value(b)
        else:
            reason(b, 'branch_absent')


@pytest.mark.parametrize('kind', ['external', 'internal'])
def test_coincident_circles(kind):
    reason(tangent((0, 0), (2, 2), kind), 'coincident')


@pytest.mark.parametrize('kind,index', [('other', 0), ('external', -1), ('internal', 0.5), ('external', 2)])
def test_invalid_tangent_selector(kind, index):
    reason(tangent(kind=kind, index=index), 'invalid_parameter')


@pytest.mark.parametrize('index,t,end', [(1, 0.25, [3, 0.75]), (2, 0.5, [0, 1.5]),
    (3, 1, [4, 0]), (1, -1, [4, 0]), (1, 2, [0, 3])])
def test_cevian_polygon(index, t, end):
    b = DocBuilder(registry_version='1.6').free('A', 0, 0).free('B', 4, 0).free('C', 0, 3)
    b.polygon('T', 'A', 'B', 'C')
    call(b, 'triangle.cevian', {'polygon': ref('T'), 'index': num(index), 't': num(t)}, 'segment', 'cevian')
    seg = value(b)
    assert seg['a'] == [[0, 0], [4, 0], [0, 3]][index - 1]
    assert seg['b'] == end
    assert seg['length'] == pytest.approx(math.dist(seg['a'], end))


def test_cevian_point_and_zero_length():
    b = DocBuilder(registry_version='1.6').free('A', 0, 0).free('B', 4, 0).free('C', 0, 3)
    b.segment('s', 'B', 'C').on_path('M', 's', 0.25)
    call(b, 'triangle.cevian', {'vertex': ref('A'), 'point': ref('M')}, 'segment', 'cevian')
    assert value(b)['b'] == [3, 0.75]
    b.doc['operations']['op_result']['args']['point'] = ref('A')
    reason(b, 'zero_length')


def segment_scene(sweep=math.pi / 2, from_circle=False):
    b = DocBuilder(registry_version='1.6').free('O', 0, 0).free('A', 2, 0)
    b.free('B', 2 * math.cos(sweep), 2 * math.sin(sweep))
    call(b, 'circle.center_radius', {'center': ref('O'), 'radius': num(2)}, 'circle', element='c')
    call(b, 'arc.on_circle', {'circle': ref('c'), 'a': ref('A'), 'b': ref('B')}, 'arc', element='arc')
    args = {'circle': ref('c'), 'a': ref('A'), 'b': ref('B')} if from_circle else {'arc': ref('arc')}
    call(b, 'sector.segment', args, 'circlesegment', 'segment')
    return b


@pytest.mark.parametrize('sweep', [0, math.pi / 2, math.pi, 3 * math.pi / 2])
@pytest.mark.parametrize('from_circle', [False, True])
def test_segment_measures(sweep, from_circle):
    b = segment_scene(sweep, from_circle)
    for op in ('area', 'perimeter', 'radius'):
        call(b, 'measure.' + op, {'of': ref('result')}, 'number', element=op)
    assert value(b)['a1'] == pytest.approx(sweep)
    assert value(b, 'area') == {'value': pytest.approx(2 * (sweep - math.sin(sweep))), 'unit': 'area'}
    assert value(b, 'perimeter') == {'value': pytest.approx(2 * sweep + 4 * abs(math.sin(sweep / 2))), 'unit': 'length'}
    assert value(b, 'radius')['value'] == 2


def test_segment_boundary_projection_and_reflection():
    b = segment_scene()
    v = value(b)
    f = frame('circlesegment', v)
    assert point_at(f, 1.5) == pytest.approx({'x': 1, 'y': 1})
    assert point_at(f, 3.5) == point_at(f, 1.5)
    assert project(f, 0, 0, 1e-9) == pytest.approx(1.5)
    assert distance_to_path(0, 0, 'circlesegment', v) == pytest.approx(math.sqrt(2))
    b.on_path('P', 'result', 1.5)
    assert value(b, 'P') == pytest.approx({'x': 1, 'y': 1})
    b.line('l', 'O', 'A')
    call(b, 'transform.reflect_line', {'obj': ref('result'), 'line': ref('l')}, 'circlesegment', 'image', element='image')
    img = value(b, 'image')
    assert img['a1'] - img['a0'] == pytest.approx(math.pi / 2)
    assert native.run_checks(native.evaluate(b.doc)).ok


def test_segment_rejects_intersections_and_points_off_circle():
    b = segment_scene(from_circle=True)
    b.doc['inputs']['B']['value'] = [0, 3]
    reason(b, 'not_on_curve')
    b = segment_scene()
    b.line('l', 'O', 'A')
    call(b, 'intersect.line_circle', {'line': ref('l'), 'circle': ref('result')}, 'point', 'first', element='X')
    rec = native.evaluate(b.doc).elements['X']
    assert (rec['state'], rec['reason']) == ('error', 'type_mismatch')


@pytest.mark.parametrize('name', ['line.euler', 'circle.nine_point'])
def test_non_triangle_polygon(name):
    b = triangle(name)
    b.free('D', 4, 3)
    call(b, 'polygon.by_points', {'vertices': ref_list('A', 'B', 'D', 'C')}, 'polygon', element='Q')
    b.doc['operations']['op_result']['args'] = {'polygon': ref('Q')}
    reason(b, 'invalid_parameter')


@pytest.mark.parametrize('builder', [tangent, segment_scene, lambda: triangle('line.euler'), lambda: triangle('circle.nine_point')])
def test_serialization_bridge_and_commands(builder):
    b = builder()
    assert native.validate(b.doc) == []
    doc = native.load(native.dumps(b.doc))
    assert native.evaluate(doc).elements == native.evaluate(b.doc).elements
    construction, names = build_construction(doc)
    construction.rebuild(full=True)
    rec = native.evaluate(doc).elements['result']
    assert from_classic(rec['type'], construction.objectByName(names.by_id['result']).data) == rec['value']
    printed = native.print_commands(doc)
    assert printed.issues == []
    parsed = native.parse_commands(printed.text)
    assert parsed.issues == []


def test_seeded_general_common_tangents():
    rng = SplitMix64(12345)
    for _ in range(20):
        c2 = (5 + 4 * rng.random(), 4 * rng.random() - 2)
        for kind in ('external', 'internal'):
            for index in (0, 1):
                line = value(tangent(c2, kind=kind, index=index))
                for center, radius in [((0, 0), 2), (c2, 1)]:
                    x, y = center[0] - line['p'][0], center[1] - line['p'][1]
                    assert abs(x * line['dir'][1] - y * line['dir'][0]) == pytest.approx(radius)


def test_alternative_inputs_are_exclusive_and_string_parameters_typed():
    b = segment_scene()
    b.doc['operations']['op_result']['args']['circle'] = ref('c')
    assert native.validate(b.doc)
    assert native.evaluate(b.doc).elements['result']['reason'] == 'schema'
    b = tangent()
    b.doc['operations']['op_result']['args']['kind'] = num(0)
    assert native.evaluate(b.doc).elements['result']['reason'] == 'type_mismatch'


@pytest.mark.manim
def test_segment_exports_closed_chord_and_hatching(tmp_path):
    pytest.importorskip('manim')
    b = segment_scene()
    b.doc['appearance'] = {e: {'visible': False} for e in ('O', 'A', 'B', 'c', 'arc')}
    b.doc['appearance']['result'] = {'overrides': {'fill': '#ccddff', 'fill_pattern': 'hatch'}}
    for fmt in ('svg', 'png', 'pdf', 'tikz'):
        path = tmp_path / ('segment.' + fmt)
        native.render(b.doc, fmt=fmt, out=path)
        assert path.stat().st_size > 100
        if fmt == 'svg':
            paths = ET.parse(path).getroot().findall('.//{http://www.w3.org/2000/svg}path')
            assert any('C' in p.get('d', '') and ('L' in p.get('d', '') or 'Z' in p.get('d', '').upper()) for p in paths)
        if fmt == 'tikz':
            text = path.read_text()
            assert 'arc (' in text and '-- cycle' in text


@pytest.mark.manim
@pytest.mark.parametrize('cap', ['round', 'square'])
def test_dash_and_tick_caps_keep_solid_caps(cap, tmp_path):
    pytest.importorskip('manim')
    from manim import CapStyleType
    from animageo.animageo import AnimaGeoScene
    b = DocBuilder(registry_version='1.6').free('A', 0, 0).free('B', 4, 0).free('C', 0, 1).free('D', 4, 1)
    b.segment('dashed', 'A', 'B').segment('solid', 'C', 'D')
    b.doc['appearance'] = {e: {'visible': False} for e in 'ABCD'}
    b.doc['appearance'].update({e: {'overrides': {'stroke_linecap': cap, 'tick_count': 2}} for e in ('dashed', 'solid')})
    b.doc['appearance']['dashed']['overrides']['stroke_dash_ratio'] = 0.5
    paint = native.resolve_paint(b.doc)['elements']
    assert paint['dashed']['stroke']['cap'] == 'butt'
    assert paint['solid']['stroke']['cap'] == cap
    scene = AnimaGeoScene()
    scene.loadDocument(b.doc)
    for e in ('dashed', 'solid'):
        leaves = scene.mobject('e_' + e).family_members_with_points()
        assert leaves[0].cap_style == (CapStyleType.BUTT if e == 'dashed' else getattr(CapStyleType, cap.upper()))
        assert all(leaf.cap_style == CapStyleType.BUTT for leaf in leaves[1:])
    out = tmp_path / 'caps.svg'
    native.render(b.doc, fmt='svg', out=out)
    paths = ET.parse(out).getroot().findall('.//{http://www.w3.org/2000/svg}path')
    dashed = [p for p in paths if p.get('stroke-dasharray')]
    assert dashed and all(p.get('stroke-linecap') == 'butt' for p in dashed)
    assert any(p.get('stroke-linecap') == cap for p in paths)
    out = tmp_path / 'caps.tex'
    native.render(b.doc, fmt='tikz', out=out)
    strokes = [line for line in out.read_text().splitlines() if '\\draw[' in line]
    assert all('line cap=round' not in line and 'line cap=rect' not in line for line in strokes if 'dash pattern=' in line)


def test_full_disc_segment_and_hatch_clipping():
    from animageo.hatch import hatch_segments
    from animageo.native.kernel.bridge import to_classic
    from animageo.geo.lib_elements import Element
    from animageo.label_anchor import nearest_point
    for sweep in (0, math.pi / 2, 3 * math.pi / 2, 2 * math.pi):
        v = {'c': [0, 0], 'r': 2, 'a0': 0, 'a1': sweep}
        obj = to_classic('circlesegment', v)
        assert from_classic('circlesegment', obj) == v
        lines = hatch_segments({'circlesegment': (0, 0, 2, 0, sweep)}, 0, 0.25)
        if sweep == 0:
            assert lines == []
        else:
            assert lines
        for x0, y0, x1, y1 in lines:
            a, b = (x0, y0), (x1, y1)
            for x, y in (a, b, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)):
                assert x*x + y*y <= 4 + 1e-9
                if sweep == math.pi / 2:
                    assert x + y >= 2 - 1e-9
        if sweep == math.pi / 2:
            assert nearest_point(Element('s', obj), [0, 0]) == pytest.approx([1, 1])


def test_new_checks_detect_geometrically_wrong_results():
    from animageo.native.kernel.checks import CHECKS
    from animageo.native.kernel.numeric import tolerances
    from animageo.native.kernel.values import Input
    tol = tolerances(20)
    args = {'first': Input('circle', {'c': [0, 0], 'r': 2}),
            'second': Input('circle', {'c': [6, 0], 'r': 1})}
    assert CHECKS[('line.common_tangents', 'tangent_both')](args, {'line': {'p': [0, 0], 'dir': [1, 0]}}, tol) == 2
    args = {k: Input('point', {'x': x, 'y': y}) for k, (x, y) in zip('abc', ((0, 0), (4, 0), (0, 3)))}
    assert CHECKS[('circle.nine_point', 'side_midpoints')](args, {'circle': {'c': [0, 0], 'r': 1}}, tol) > 1
